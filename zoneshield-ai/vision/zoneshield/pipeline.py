"""Vision pipeline stages.

Each stage implements process(ctx) -> ctx with per-stage timing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np


@dataclass
class PipelineContext:
    """Mutable context passed through pipeline stages."""
    frame: np.ndarray
    t_capture_ms: float
    seq: int
    stage_timings: dict[str, float] = field(default_factory=dict)
    homography: Optional[object] = None
    roi_frame: Optional[np.ndarray] = None
    fg_mask: Optional[np.ndarray] = None
    contours: list = field(default_factory=list)
    detections: list[dict] = field(default_factory=list)
    tracks: list[dict] = field(default_factory=list)
    predictions: list[dict] = field(default_factory=list)
    risk_assessments: list[dict] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)
    dropped_frames: int = 0

    def stage_time(self, name: str, start_ms: float) -> None:
        self.stage_timings[name] = time.perf_counter() * 1000.0 - start_ms


class Stage:
    """Base pipeline stage."""

    def process(self, ctx: PipelineContext) -> PipelineContext:
        start = time.perf_counter() * 1000.0
        ctx = self._process(ctx)
        ctx.stage_time(self.__class__.__name__, start)
        return ctx

    def _process(self, ctx: PipelineContext) -> PipelineContext:
        raise NotImplementedError


class UndistortHomography(Stage):
    """Apply homography to undistort and map image -> world coordinates."""

    def __init__(self, homography: Optional[object] = None) -> None:
        self._H = homography

    def _process(self, ctx: PipelineContext) -> PipelineContext:
        if self._H is not None and ctx.frame is not None:
            ctx.homography = self._H
            ctx.frame = cv2.warpPerspective(
                ctx.frame, self._H, (ctx.frame.shape[1], ctx.frame.shape[0])
            )
        return ctx


class ROIDownscale(Stage):
    """Extract region of interest and downscale for faster processing."""

    def __init__(self, scale: float = 2.0) -> None:
        self._scale = scale

    def _process(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.frame is None:
            return ctx
        h, w = ctx.frame.shape[:2]
        new_w = max(1, int(w / self._scale))
        new_h = max(1, int(h / self._scale))
        ctx.roi_frame = cv2.resize(ctx.frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return ctx


class BackgroundSubtract(Stage):
    """Background subtraction using MOG2."""

    def __init__(self, history: int = 50, var_threshold: float = 16.0, detect_shadows: bool = False) -> None:
        self._bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=history, varThreshold=var_threshold, detectShadows=detect_shadows
        )

    def _process(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.roi_frame is None:
            return ctx
        ctx.fg_mask = self._bg_subtractor.apply(ctx.roi_frame)
        return ctx


class Morphology(Stage):
    """Morphological operations to clean up foreground mask."""

    def __init__(self, kernel_px: int = 5) -> None:
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_px, kernel_px))

    def _process(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.fg_mask is None:
            return ctx
        ctx.fg_mask = cv2.morphologyEx(ctx.fg_mask, cv2.MORPH_OPEN, self._kernel)
        ctx.fg_mask = cv2.morphologyEx(ctx.fg_mask, cv2.MORPH_CLOSE, self._kernel)
        return ctx


class Contours(Stage):
    """Extract contours from foreground mask."""

    def __init__(self, min_area_px: int = 100) -> None:
        self._min_area = min_area_px

    def _process(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.fg_mask is None:
            return ctx
        contours, _ = cv2.findContours(ctx.fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        ctx.contours = []
        for c in contours:
            area = cv2.contourArea(c)
            if area >= self._min_area:
                x, y, w, h = cv2.boundingRect(c)
                cx = x + w / 2.0
                cy = y + h / 2.0
                ctx.contours.append({
                    "bbox": [x, y, w, h],
                    "centroid": [cx, cy],
                    "area": float(area),
                })
        if ctx.roi_frame is not None and ctx.frame is not None:
            scale_x = ctx.frame.shape[1] / ctx.roi_frame.shape[1]
            scale_y = ctx.frame.shape[0] / ctx.roi_frame.shape[0]
            for det in ctx.contours:
                det["bbox"] = [
                    v * scale_x if i % 2 == 0 else v * scale_y for i, v in enumerate(det["bbox"])
                ]
                det["centroid"] = [det["centroid"][0] * scale_x, det["centroid"][1] * scale_y]
                det["area"] = det["area"] * scale_x * scale_y
        ctx.detections = ctx.contours
        return ctx


class Classify(Stage):
    """Classify detections as foreign/legit/ambiguous using OpenCV 5 DNN or classical fallback."""

    def __init__(self, model_path: Optional[str] = "data/classifier.onnx") -> None:
        self._model_path = model_path
        self._net: Optional[cv2.dnn.Net] = None
        self._dnn_initialized = False

    def _init_dnn(self) -> None:
        if self._dnn_initialized:
            return
        self._dnn_initialized = True
        if self._model_path:
            import os
            if os.path.isfile(self._model_path):
                try:
                    self._net = cv2.dnn.readNetFromONNX(str(self._model_path))
                except Exception:
                    self._net = None

    def _process(self, ctx: PipelineContext) -> PipelineContext:
        self._init_dnn()
        frame = ctx.frame if ctx.frame is not None else ctx.roi_frame

        for det in ctx.detections:
            x, y, w, h = [int(v) for v in det["bbox"]]
            cx, cy = int(det["centroid"][0]), int(det["centroid"][1])

            if frame is None:
                det["class_probs"] = {"legit": 0.33, "foreign": 0.33, "ambiguous": 0.34}
                det["class"] = "ambiguous"
                det["confidence"] = 0.0
                continue

            classified_by_dnn = False
            if self._net is not None and w >= 8 and h >= 8:
                x1 = max(0, x)
                y1 = max(0, y)
                x2 = min(frame.shape[1], x + w)
                y2 = min(frame.shape[0], y + h)
                crop = frame[y1:y2, x1:x2]

                if crop.size > 0 and crop.shape[0] >= 4 and crop.shape[1] >= 4:
                    try:
                        blob = cv2.dnn.blobFromImage(
                            crop,
                            scalefactor=1.0 / 255.0,
                            size=(32, 32),
                            mean=(0, 0, 0),
                            swapRB=False,
                            crop=False,
                        )
                        self._net.setInput(blob)
                        out = self._net.forward()
                        probs = out[0]
                        f_prob = float(probs[0])
                        l_prob = float(probs[1])
                        a_prob = float(probs[2])
                        total = f_prob + l_prob + a_prob
                        if total > 0:
                            f_norm = f_prob / total
                            l_norm = l_prob / total
                            a_norm = a_prob / total
                            det["class_probs"] = {"foreign": f_norm, "legit": l_norm, "ambiguous": a_norm}
                            if f_norm >= l_norm and f_norm >= a_norm:
                                det["class"] = "foreign"
                                det["confidence"] = f_norm
                            elif l_norm >= f_norm and l_norm >= a_norm:
                                det["class"] = "legit"
                                det["confidence"] = l_norm
                            else:
                                det["class"] = "ambiguous"
                                det["confidence"] = a_norm
                            det["dnn_accelerated"] = True
                            classified_by_dnn = True
                    except Exception:
                        classified_by_dnn = False

            if not classified_by_dnn:
                if 0 <= cy < frame.shape[0] and 0 <= cx < frame.shape[1]:
                    b, g, r = int(frame[cy, cx, 0]), int(frame[cy, cx, 1]), int(frame[cy, cx, 2])
                else:
                    b, g, r = 128, 128, 128

                foreign_score = max(0, g - max(r, b)) / 255.0
                legit_score = max(0, b - max(r, g)) / 255.0
                total = foreign_score + legit_score
                if total < 0.1:
                    det["class_probs"] = {"legit": 0.33, "foreign": 0.33, "ambiguous": 0.34}
                    det["class"] = "ambiguous"
                    det["confidence"] = 0.34
                else:
                    f_norm = foreign_score / total
                    l_norm = legit_score / total
                    det["class_probs"] = {"foreign": f_norm, "legit": l_norm, "ambiguous": 1.0 - f_norm - l_norm}
                    if f_norm > l_norm:
                        det["class"] = "foreign"
                        det["confidence"] = f_norm
                    else:
                        det["class"] = "legit"
                        det["confidence"] = l_norm
                det["dnn_accelerated"] = False

        return ctx


class Tracker:
    """Kalman filter based multi-object tracker."""

    def __init__(self, dt: float = 1.0 / 30.0) -> None:
        self._dt = dt
        self._tracks: dict[int, dict] = {}
        self._next_id = 0
        self._process_noise = np.diag([0.1, 0.1, 0.5, 0.5]) ** 2
        self._measurement_noise = np.diag([2.0, 2.0]) ** 2

    def _new_track(self, centroid: np.ndarray) -> int:
        track_id = self._next_id
        self._next_id += 1
        cx = float(centroid[0, 0])
        cy = float(centroid[1, 0])
        state = np.array([[cx], [cy], [0.0], [0.0]], dtype=float)
        cov = np.eye(4) * 10.0
        self._tracks[track_id] = {
            "id": track_id,
            "state": state,
            "cov": cov,
            "age": 0,
            "hits": 1,
            "misses": 0,
            "centroid": centroid.copy(),
            "velocity": np.array([[0.0], [0.0]], dtype=float),
            "class_probs": {"legit": 0.33, "foreign": 0.33, "ambiguous": 0.34},
            "confidence": 0.0,
            "occlusion": False,
        }
        return track_id

    def update(self, detections: list[dict], class_probs_map: Optional[dict[int, dict]] = None) -> list[dict]:
        class_probs_map = class_probs_map or {}
        updated_ids = set()

        track_ids = list(self._tracks.keys())
        n_tracks = len(track_ids)
        n_dets = len(detections)

        matches: list[tuple[int, int]] = []
        unmatched_dets = list(range(n_dets))

        # Hungarian algorithm matching if scipy is available and both tracks and detections exist
        used_hungarian = False
        if n_tracks > 0 and n_dets > 0:
            try:
                from scipy.optimize import linear_sum_assignment
                cost_matrix = np.zeros((n_dets, n_tracks), dtype=float)
                for d_idx, det in enumerate(detections):
                    d_c = np.array(det["centroid"], dtype=float)
                    for t_idx, tid in enumerate(track_ids):
                        t_c = self._tracks[tid]["state"][0:2].flatten()
                        cost_matrix[d_idx, t_idx] = float(np.linalg.norm(d_c - t_c))

                row_ind, col_ind = linear_sum_assignment(cost_matrix)
                for r, c in zip(row_ind, col_ind):
                    if cost_matrix[r, c] < 50.0:
                        matches.append((r, track_ids[c]))
                        if r in unmatched_dets:
                            unmatched_dets.remove(r)
                used_hungarian = True
            except Exception:
                used_hungarian = False

        if not used_hungarian:
            for d_idx, det in enumerate(detections):
                det_centroid = np.array(det["centroid"], dtype=float).reshape(2, 1)
                best_id = None
                best_dist = float("inf")
                for tid, track in self._tracks.items():
                    if tid in updated_ids:
                        continue
                    dist = float(np.linalg.norm(det_centroid - track["state"][0:2]))
                    if dist < best_dist and dist < 50.0:
                        best_dist = dist
                        best_id = tid
                if best_id is not None:
                    matches.append((d_idx, best_id))
                    if d_idx in unmatched_dets:
                        unmatched_dets.remove(d_idx)

        for d_idx, tid in matches:
            det = detections[d_idx]
            det_centroid = np.array(det["centroid"], dtype=float).reshape(2, 1)
            track = self._tracks[tid]
            state_pred, cov_pred = self._kalman_predict(track["state"], track["cov"])
            state_upd, cov_upd = self._kalman_update(state_pred, cov_pred, det_centroid)
            track["state"] = state_upd
            track["cov"] = cov_upd
            track["centroid"] = state_upd[0:2].flatten()
            track["velocity"] = state_upd[2:4].flatten()
            track["age"] += 1
            track["hits"] += 1
            track["misses"] = 0
            cp = class_probs_map.get(tid, det.get("class_probs", {}))
            if cp:
                track["class_probs"] = cp
                det_class = det.get("class", "foreign" if cp.get("foreign", 0) > cp.get("legit", 0) else "legit")
                track["class"] = det_class
                track["confidence"] = det.get("confidence", max(cp.get("foreign", 0), cp.get("legit", 0)))
            updated_ids.add(tid)

        for d_idx in unmatched_dets:
            det = detections[d_idx]
            det_centroid = np.array(det["centroid"], dtype=float).reshape(2, 1)
            tid = self._new_track(det_centroid)
            self._tracks[tid]["age"] = 1
            cp = class_probs_map.get(tid, det.get("class_probs", {}))
            if cp:
                self._tracks[tid]["class_probs"] = cp
                det_class = det.get("class", "foreign" if cp.get("foreign", 0) > cp.get("legit", 0) else "legit")
                self._tracks[tid]["class"] = det_class
                self._tracks[tid]["confidence"] = det.get("confidence", max(cp.get("foreign", 0), cp.get("legit", 0)))
            updated_ids.add(tid)

        active_tracks = []
        for tid, track in list(self._tracks.items()):
            if tid not in updated_ids:
                track["misses"] += 1
                state_pred, cov_pred = self._kalman_predict(track["state"], track["cov"])
                track["state"] = state_pred
                track["cov"] = cov_pred
                track["centroid"] = state_pred[0:2].flatten()
                track["velocity"] = state_pred[2:4].flatten()
                track["age"] += 1

            if track["misses"] <= 5:
                active_tracks.append({
                    "id": track["id"],
                    "centroid": track["centroid"].flatten().tolist(),
                    "velocity": track["velocity"].flatten().tolist(),
                    "age": track["age"],
                    "hits": track["hits"],
                    "misses": track["misses"],
                    "class": track.get("class", "ambiguous"),
                    "class_probs": track.get("class_probs", {"legit": 0.33, "foreign": 0.33, "ambiguous": 0.34}),
                    "confidence": track.get("confidence", 0.0),
                    "occlusion": track.get("occlusion", False),
                })

        self._tracks = {tid: t for tid, t in self._tracks.items() if t["misses"] <= 5}
        return active_tracks

    def _kalman_predict(self, state: np.ndarray, cov: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        dt = self._dt
        F = np.array([[1, 0, dt, 0], [0, 1, 0, dt], [0, 0, 1, 0], [0, 0, 0, 1]])
        state_pred = F @ state
        cov_pred = F @ cov @ F.T + self._process_noise
        return state_pred, cov_pred

    def _kalman_update(self, state_pred: np.ndarray, cov_pred: np.ndarray, meas: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]])
        z = meas.reshape(2, 1)
        y = z - H @ state_pred
        S = H @ cov_pred @ H.T + self._measurement_noise
        K = cov_pred @ H.T @ np.linalg.inv(S)
        state_upd = state_pred + K @ y
        I = np.eye(4)
        cov_upd = (I - K @ H) @ cov_pred
        return state_upd, cov_upd

    def get_tracks(self) -> list[dict]:
        return [
            {
                "id": t["id"],
                "centroid": t["centroid"].flatten().tolist(),
                "velocity": t["velocity"].flatten().tolist(),
                "class": t.get("class", "ambiguous"),
                "class_probs": t.get("class_probs", {}),
                "confidence": t.get("confidence", 0.0),
            }
            for t in self._tracks.values()
        ]


class Predictor:
    """Trajectory predictor using constant-velocity model."""

    def __init__(self, dt: float = 1.0 / 30.0) -> None:
        self._dt = dt

    def predict(
        self,
        tracks: list[dict],
        horizons_ms: list[int],
        target_line_y_px: float,
    ) -> list[dict]:
        predictions = []
        for track in tracks:
            x, y = track["centroid"]
            vx, vy = track["velocity"]
            positions = []
            uncertainties = []
            for h_ms in horizons_ms:
                h_s = h_ms / 1000.0
                px = x + vx * h_s
                py = y + vy * h_s
                unc = 2.0 * (1.0 + h_s)
                positions.append([px, py])
                uncertainties.append(unc)

            tti = self._tti_ms((x, y), (vx, vy), target_line_y_px)
            crosses_zone = tti is not None and 0 < tti < 2000

            at_jet_x = None
            if tti is not None and tti > 0:
                at_jet_x = x + vx * (tti / 1000.0)

            predictions.append({
                "track_id": track["id"],
                "horizons_ms": horizons_ms,
                "positions_px": positions,
                "uncertainty_px": uncertainties,
                "tti_ms": tti,
                "crosses_zone": crosses_zone,
                "at_jet_position_px": [at_jet_x, target_line_y_px] if at_jet_x is not None else None,
            })
        return predictions

    @staticmethod
    def _tti_ms(position_px: tuple[float, float], velocity_px_s: tuple[float, float], target_line_y_px: float) -> float | None:
        _, y = position_px
        _, vy = velocity_px_s
        if vy <= 0:
            return None
        distance_px = target_line_y_px - y
        if distance_px < 0:
            return 0.0
        return (distance_px / vy) * 1000.0