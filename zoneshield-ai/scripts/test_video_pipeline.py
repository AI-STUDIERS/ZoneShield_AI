"""Test runner for ZoneShield AI pipeline on real MP4 test videos.

Runs the complete closed-loop pipeline:
Ingest -> OpenCV 5 Preprocessing -> MOG2 -> Contours -> Classify ->
Kalman Tracker -> Trajectory Predictor -> Decision Engine -> Guardrails -> Simulated Actuator.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import cv2
import numpy as np

# Ensure vision and root are on sys.path
_root = Path(__file__).resolve().parent.parent
_vision = _root / "vision"
for _p in (str(_root), str(_vision)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from zoneshield.actuator import SimulatedActuator
from zoneshield.agent import MockAgent
from zoneshield.decision import DecisionEngine
from zoneshield.framesource import VideoFile
from zoneshield.guardrails import FireRequest, check_all_guardrails
from zoneshield.pipeline import (
    BackgroundSubtract,
    Classify,
    Contours,
    Morphology,
    PipelineContext,
    Predictor,
    ROIDownscale,
    Tracker,
    UndistortHomography,
)


def run_video_test(video_path: str | Path, video_name: str) -> dict[str, Any]:
    print(f"\n{'='*70}")
    print(f" Testing Video: {video_name}")
    print(f" Path: {video_path}")
    print(f"{'='*70}")

    source = VideoFile(str(video_path), loop=False)

    # Initialize vision stages
    homography = UndistortHomography()
    roi = ROIDownscale(scale=2.0)
    bg = BackgroundSubtract(history=50, var_threshold=16.0)
    morph = Morphology(kernel_px=5)
    contours_stage = Contours(min_area_px=100)
    classify_stage = Classify()
    tracker = Tracker(dt=1.0 / 30.0)
    predictor = Predictor(dt=1.0 / 30.0)
    agent = MockAgent()
    decision_engine = DecisionEngine(agent_client=agent, t_intercept=0.75, t_ambiguous_low=0.40)
    actuator = SimulatedActuator(delay_ms=80.0, jitter_ms=10.0, cone_angle_deg=25.0, cooldown_ms=400.0)

    # Metrics collectors
    frame_count = 0
    total_detections = 0
    stage_timings: dict[str, list[float]] = {
        "UndistortHomography": [],
        "ROIDownscale": [],
        "BackgroundSubtract": [],
        "Morphology": [],
        "Contours": [],
        "Classify": [],
        "Tracker": [],
        "Predictor": [],
        "DecisionEngine": [],
    }
    total_latencies: list[float] = []

    unique_track_ids = set()
    track_classes: dict[int, str] = {}
    track_max_conf: dict[int, float] = {}

    decisions_summary: dict[str, int] = {"intercept": 0, "monitor": 0, "gather_evidence": 0, "request_human": 0}
    guardrail_vetoes: dict[str, int] = {"G1": 0, "G2": 0, "G3": 0, "G4": 0, "G5": 0}
    actuations_applied = 0
    actuations_blocked = 0
    intercepted_tracks = set()

    t_start_wall = time.perf_counter()

    while True:
        frame_obj = source.read()
        if frame_obj is None:
            break

        frame_count += 1
        t_frame_start = time.perf_counter()

        # 1. Perception
        ctx = PipelineContext(frame=frame_obj.image, t_capture_ms=frame_obj.t_capture_ms, seq=frame_obj.seq)
        ctx = homography.process(ctx)
        ctx = roi.process(ctx)
        ctx = bg.process(ctx)
        ctx = morph.process(ctx)
        ctx = contours_stage.process(ctx)
        ctx = classify_stage.process(ctx)

        total_detections += len(ctx.detections)

        # 2. Tracking
        t_t0 = time.perf_counter()
        tracks = tracker.update(ctx.detections)
        ctx.stage_timings["Tracker"] = (time.perf_counter() - t_t0) * 1000.0

        for trk in tracks:
            tid = trk["id"]
            unique_track_ids.add(tid)
            track_classes[tid] = trk.get("class", "ambiguous")
            conf = trk.get("confidence", 0.0)
            track_max_conf[tid] = max(track_max_conf.get(tid, 0.0), conf)

        # 3. Trajectory Prediction
        t_p0 = time.perf_counter()
        target_line_y = 220.0  # Normalized for 360p height
        predictions = predictor.predict(tracks, horizons_ms=[100, 250, 500], target_line_y_px=target_line_y)
        ctx.stage_timings["Predictor"] = (time.perf_counter() - t_p0) * 1000.0

        pred_by_track = {p["track_id"]: p for p in predictions}

        # 4. Decision Engine
        t_d0 = time.perf_counter()
        for trk in tracks:
            tid = trk["id"]
            pred = pred_by_track.get(tid, {})
            conf = trk.get("confidence", 0.0)
            tti = pred.get("tti_ms")
            crosses = pred.get("crosses_zone", False)
            at_jet = pred.get("at_jet_position_px")

            # Check jet alignment around interceptor center (x=320 for 640-width)
            jet_center_x = 320.0
            jet_half_width = 50.0
            pred_x = at_jet[0] if at_jet else trk["centroid"][0]
            jet_aligned = abs(pred_x - jet_center_x) <= jet_half_width

            dec = decision_engine.evaluate(
                session_id=video_name,
                track_id=tid,
                confidence=conf,
                class_probs=trk.get("class_probs", {}),
                tti_ms=tti,
                crosses_zone=crosses,
                jet_aligned=jet_aligned,
                thresholds={"t_intercept": 0.75, "t_ambiguous_low": 0.40},
            )

            decisions_summary[dec.action] = decisions_summary.get(dec.action, 0) + 1

            # 5. Guardrails & Actuation
            if dec.action == "intercept" and tid not in intercepted_tracks:
                act_state = actuator.state()
                req = FireRequest(
                    tti_ms=tti or 0.0,
                    actuation_delay_ms=80.0,
                    min_tti_margin_ms=150.0,
                    predicted_x_at_jet=pred_x,
                    jet_cone_center_x=jet_center_x,
                    jet_cone_half_width=jet_half_width,
                    confidence=conf,
                    t_ambiguous_low=0.40,
                    last_fire_ms=act_state.get("last_fire_ms", 0.0),
                    now_ms=time.perf_counter() * 1000.0,
                    cooldown_ms=400.0,
                    kill_switch_enabled=act_state.get("kill_switch", False),
                )
                veto = check_all_guardrails(req)
                if not veto.blocked:
                    actuator.arm()
                    event = actuator.fire(frame_obj.t_capture_ms, (pred_x, target_line_y))
                    if event.applied:
                        actuations_applied += 1
                        intercepted_tracks.add(tid)
                    else:
                        actuations_blocked += 1
                else:
                    actuations_blocked += 1
                    if veto.guardrail:
                        guardrail_vetoes[veto.guardrail] = guardrail_vetoes.get(veto.guardrail, 0) + 1

        ctx.stage_timings["DecisionEngine"] = (time.perf_counter() - t_d0) * 1000.0

        t_frame_end = time.perf_counter()
        total_latencies.append((t_frame_end - t_frame_start) * 1000.0)

        for st_name, val in ctx.stage_timings.items():
            if st_name in stage_timings:
                stage_timings[st_name].append(val)

    source.close()
    wall_duration = time.perf_counter() - t_start_wall

    arr_lat = np.array(total_latencies) if total_latencies else np.array([0.0])
    mean_lat = float(np.mean(arr_lat))
    throughput_fps = float(frame_count / wall_duration) if wall_duration > 0 else 0.0

    report = {
        "video": video_name,
        "frames_processed": frame_count,
        "wall_time_s": round(wall_duration, 3),
        "pipeline_fps": round(throughput_fps, 1),
        "mean_latency_ms": round(mean_lat, 2),
        "p50_latency_ms": round(float(np.percentile(arr_lat, 50)), 2),
        "p95_latency_ms": round(float(np.percentile(arr_lat, 95)), 2),
        "total_detections": total_detections,
        "unique_tracks": len(unique_track_ids),
        "track_ids": sorted(list(unique_track_ids)),
        "track_classes": track_classes,
        "track_max_conf": {k: round(v, 2) for k, v in track_max_conf.items()},
        "decisions_summary": decisions_summary,
        "intercepted_tracks": sorted(list(intercepted_tracks)),
        "actuations_applied": actuations_applied,
        "actuations_blocked": actuations_blocked,
        "guardrail_vetoes": guardrail_vetoes,
        "per_stage_latency_ms": {
            k: round(float(np.mean(v)), 2) for k, v in stage_timings.items() if v
        },
    }

    print(f" Frames Processed:   {report['frames_processed']}")
    print(f" Processing Speed:   {report['pipeline_fps']} FPS (Mean Latency: {report['mean_latency_ms']} ms)")
    print(f" Unique Tracks:      {report['unique_tracks']} objects identified {report['track_ids']}")
    print(f" Track Class Profile:{report['track_classes']}")
    print(f" Decisions Count:    {report['decisions_summary']}")
    print(f" Actuations Fired:   {report['actuations_applied']}")
    print(f" Actuations Blocked: {report['actuations_blocked']} (Guardrails: {report['guardrail_vetoes']})")
    print(f" Intercepted Tracks: {report['intercepted_tracks']}")
    print(f" Per-Stage Mean (ms):{report['per_stage_latency_ms']}")
    print(f"{'='*70}")

    return report


def main() -> None:
    test_dir = Path("docs/test_videos")
    all_videos = sorted(test_dir.glob("*.mp4"))
    if not all_videos:
        print(f"Error: No videos found in {test_dir}!")
        return

    all_results = {}
    for vpath in all_videos:
        filename = vpath.name
        all_results[filename] = run_video_test(vpath, filename)

    out_json = Path("reports/test_videos_evaluation.json")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print(f"\nFull test evaluation saved to {out_json}")


if __name__ == "__main__":
    main()
