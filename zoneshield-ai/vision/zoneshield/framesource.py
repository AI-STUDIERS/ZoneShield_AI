"""FrameSource interface and implementations.

Implements the interchangeable frame sources from the master spec:
- SimulatorLive: real-time synthetic conveyor (in-process)
- BrowserWebcam: browser getUserMedia -> WebSocket binary JPEG (backend)
- RTSP/HTTP-MJPEG: phone IP-camera app (backend)
- VideoFile: looped file for repeatable demos
"""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np


@dataclass(frozen=True)
class Frame:
    """A captured frame with metadata."""
    image: np.ndarray  # BGR uint8
    t_capture_ms: float  # monotonic capture timestamp in ms
    seq: int  # monotonically increasing sequence number
    source_id: str


class FrameSource(abc.ABC):
    """Abstract frame source. Substitutions must be frame-compatible."""

    @property
    @abc.abstractmethod
    def source_id(self) -> str:
        ...

    @abc.abstractmethod
    def read(self) -> Optional[Frame]:
        """Return the next frame, or None if the source is exhausted."""
        ...

    @abc.abstractmethod
    def restart(self) -> None:
        """Restart / reopen the source."""
        ...

    @abc.abstractmethod
    def close(self) -> None:
        """Release resources."""
        ...


class SimulatorLive(FrameSource):
    """Real-time synthetic conveyor rendered with OpenCV/NumPy.

    Produces a top-down view of a conveyor belt with scrolling texture,
    legitimate objects, foreign objects, lateral drift, noise, blur,
    lighting variation and occlusion. Fully seeded for reproducibility.
    """

    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        belt_speed_px_s: float = 120.0,
        fps: int = 30,
        seed: int = 42,
        scenario: Optional[dict] = None,
    ) -> None:
        self._width = width
        self._height = height
        self._belt_speed_px_s = belt_speed_px_s
        self._fps = fps
        self._frame_interval_s = 1.0 / fps
        self._seed = seed
        self._rng = np.random.default_rng(seed)
        self._scenario = scenario or {}
        self._seq = 0
        self._t_start = time.perf_counter()
        self._closed = False

        self._belt_texture = self._make_belt_texture()
        self._objects: list[dict] = []
        self._spawn_timer = 0.0
        self._ground_truth: list[dict] = []

        self._spawn_initial_objects()

    @property
    def source_id(self) -> str:
        return "simulator:live"

    def read(self) -> Optional[Frame]:
        if self._closed:
            return None
        dt = self._frame_interval_s
        self._step(dt)
        frame = self._render()
        t_capture_ms = time.perf_counter() * 1000.0
        frame_obj = Frame(
            image=frame,
            t_capture_ms=t_capture_ms,
            seq=self._seq,
            source_id=self.source_id,
        )
        self._seq += 1
        return frame_obj

    def restart(self) -> None:
        self._seq = 0
        self._t_start = time.perf_counter()
        self._rng = np.random.default_rng(self._seed)
        self._objects = []
        self._ground_truth = []
        self._spawn_initial_objects()

    def close(self) -> None:
        self._closed = True

    def ground_truth(self) -> list[dict]:
        return list(self._ground_truth)

    def _make_belt_texture(self) -> np.ndarray:
        tile = np.zeros((40, 40, 3), dtype=np.uint8)
        tile[:] = (40, 40, 40)
        tile[0:10, :] = (60, 60, 60)
        tile[30:40, :] = (60, 60, 60)
        noise = self._rng.integers(0, 30, size=tile.shape, dtype=np.uint8)
        tile = cv2.add(tile, noise)
        return tile

    def _draw_belt(self, canvas: np.ndarray, offset_px: float) -> None:
        tile_h, tile_w = self._belt_texture.shape[:2]
        y_off = int(offset_px) % tile_h
        for y in range(0, self._height, tile_h):
            yy = (y + y_off) % tile_h
            h = min(tile_h - yy, self._height - y)
            for x in range(0, self._width, tile_w):
                xx = x % tile_w
                w = min(tile_w - xx, self._width - x)
                canvas[y:y + h, x:x + w] = self._belt_texture[yy:yy + h, xx:xx + w]

    def _spawn_initial_objects(self) -> None:
        n_foreign = self._scenario.get("foreign_count", 2)
        n_legit = self._scenario.get("legit_count", 2)
        speed = self._scenario.get("speed", 1.0)
        for i in range(n_foreign):
            x = float(self._rng.integers(100, self._width - 100))
            y = float(-50 - i * 150)
            self._objects.append({
                "x": x, "y": y,
                "vx": float(self._rng.uniform(-5, 5) * speed),
                "vy": self._belt_speed_px_s * speed,
                "class": "foreign",
                "radius": float(self._rng.integers(18, 28)),
                "color": (int(self._rng.integers(0, 80)), int(self._rng.integers(150, 255)), int(self._rng.integers(0, 80))),
                "active": True,
            })
        for i in range(n_legit):
            x = float(self._rng.integers(100, self._width - 100))
            y = float(-50 - i * 150 - n_foreign * 150)
            self._objects.append({
                "x": x, "y": y,
                "vx": float(self._rng.uniform(-3, 3) * speed),
                "vy": self._belt_speed_px_s * speed * 0.9,
                "class": "legit",
                "radius": float(self._rng.integers(15, 22)),
                "color": (int(self._rng.integers(100, 200)), int(self._rng.integers(100, 200)), int(self._rng.integers(150, 255))),
                "active": True,
            })

    def _step(self, t_seconds: float) -> None:
        dt = self._frame_interval_s
        self._spawn_timer += dt
        if self._spawn_timer > 1.5:
            self._spawn_timer = 0.0
            if self._rng.random() < 0.6:
                x = float(self._rng.integers(150, self._width - 150))
                is_foreign = self._rng.random() < 0.4
                self._objects.append({
                    "x": x, "y": -30.0,
                    "vx": float(self._rng.uniform(-6, 6)),
                    "vy": self._belt_speed_px_s * (1.0 if is_foreign else 0.9),
                    "class": "foreign" if is_foreign else "legit",
                    "radius": float(self._rng.integers(15, 28)),
                    "color": (
                        int(self._rng.integers(0, 80)), int(self._rng.integers(150, 255)), int(self._rng.integers(0, 80))
                    ) if is_foreign else (
                        int(self._rng.integers(100, 200)), int(self._rng.integers(100, 200)), int(self._rng.integers(150, 255))
                    ),
                    "active": True,
                })
        for obj in self._objects:
            if not obj["active"]:
                continue
            obj["x"] += obj["vx"] * dt
            obj["y"] += obj["vy"] * dt
        for obj in self._objects:
            if obj["y"] > self._height + 50:
                obj["active"] = False

    def _render(self) -> np.ndarray:
        canvas = np.zeros((self._height, self._width, 3), dtype=np.uint8)
        canvas[:] = (20, 20, 20)
        offset = (self._seq * self._belt_speed_px_s / self._fps) % 40
        self._draw_belt(canvas, offset)
        zone = np.array([[200, 150], [400, 150], [400, 250], [200, 250]], dtype=np.int32)
        cv2.polylines(canvas, [zone], isClosed=True, color=(0, 255, 255), thickness=2)
        cv2.putText(canvas, "SHIELD ZONE", (210, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        cv2.line(canvas, (300, 280), (300, 200), (0, 0, 255), 2)
        cv2.putText(canvas, "INTERCEPTOR", (290, 290), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
        gt_frame = {"frame": self._seq, "objects": []}
        for obj in self._objects:
            if not obj["active"]:
                continue
            cx, cy = int(obj["x"]), int(obj["y"])
            r = int(obj["radius"])
            color = obj["color"]
            cv2.circle(canvas, (cx, cy), r, color, -1)
            cv2.circle(canvas, (cx, cy), r, (255, 255, 255), 1)
            intervention_required = obj["class"] == "foreign"
            gt_frame["objects"].append({
                "class": obj["class"],
                "position_px": [cx, cy],
                "radius_px": r,
                "intervention_required": intervention_required,
                "seq": self._seq,
            })
        self._ground_truth.append(gt_frame)
        cv2.putText(canvas, f"Frame: {self._seq}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        return canvas


class VideoFile(FrameSource):
    """Video file source, looped for repeatable demos."""

    def __init__(self, path: str, loop: bool = True) -> None:
        self._path = path
        self._loop = loop
        self._cap: Optional[cv2.VideoCapture] = None
        self._seq = 0
        self._source_id = f"video:{path}"
        self._open()

    @property
    def source_id(self) -> str:
        return self._source_id

    def _open(self) -> None:
        if self._cap is not None:
            self._cap.release()
        self._cap = cv2.VideoCapture(self._path)
        self._seq = 0

    def read(self) -> Optional[Frame]:
        if self._cap is None or not self._cap.isOpened():
            return None
        ret, frame = self._cap.read()
        if not ret:
            if self._loop:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._cap.read()
                if not ret:
                    return None
            else:
                return None
        t_capture_ms = time.perf_counter() * 1000.0
        result = Frame(image=frame, t_capture_ms=t_capture_ms, seq=self._seq, source_id=self.source_id)
        self._seq += 1
        return result

    def restart(self) -> None:
        if self._cap:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self._seq = 0

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None