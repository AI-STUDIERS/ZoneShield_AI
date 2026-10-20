"""Vision worker and session execution runner.

Coordinates:
- FrameSource ingestion
- FrameRingBuffer (latest-frame retention, bounded latency)
- OpenCV 5 pipeline (ROI, BG subtract, morphology, contours, classify)
- Tracker (Kalman filter)
- Predictor (TTI & trajectory projection)
- Decision Engine (Tier 1 policy & Tier 2 agent orchestration)
- Simulated Actuator with guardrails (G1-G5)
- Outcome verification & review queue
- PubSub event bus for WebSocket clients
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID, uuid4

import cv2
import numpy as np

from backend.frame_ring_buffer import FrameRingBuffer
from backend.models import (
    ActuationEvent,
    AuditEvent,
    Decision,
    DecisionAction,
    DecisionTier,
    OutcomeRecord,
    ReviewItem,
    ReviewStatus,
    Session,
    SessionState,
)
from backend.storage import (
    AuditRepo,
    DecisionRepo,
    EvidenceStore,
    ReviewRepo,
    SessionRepo,
)
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_vision = _root / "vision"
for _p in (str(_root), str(_vision)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from zoneshield.actuator import SimulatedActuator
from zoneshield.agent import BedrockAgentClient, MockAgent
from zoneshield.decision import DecisionEngine, TrackState
from zoneshield.framesource import FrameSource, SimulatorLive, VideoFile
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

logger = logging.getLogger("zoneshield.worker")


class SessionWorker:
    """Worker process/thread for a single active ZoneShield AI session."""

    def __init__(
        self,
        session_id: str,
        source: FrameSource,
        session_repo: SessionRepo,
        decision_repo: DecisionRepo,
        review_repo: ReviewRepo,
        audit_repo: AuditRepo,
        evidence_store: EvidenceStore,
        agent_mode: str = "mock",
        bedrock_model_id: Optional[str] = None,
        target_fps: int = 30,
        subscribers: Optional[list[asyncio.Queue]] = None,
    ) -> None:
        self.session_id = session_id
        self.source = source
        self.session_repo = session_repo
        self.decision_repo = decision_repo
        self.review_repo = review_repo
        self.audit_repo = audit_repo
        self.evidence_store = evidence_store
        self.target_fps = target_fps
        self.subscribers: list[asyncio.Queue] = subscribers or []
        
        # Pipeline primitives
        self.ring_buffer = FrameRingBuffer(capacity=2)
        self.homography_stage = UndistortHomography()
        self.roi_stage = ROIDownscale(scale=2.0)
        self.bg_stage = BackgroundSubtract(history=50, var_threshold=16.0)
        self.morph_stage = Morphology(kernel_px=5)
        self.contour_stage = Contours(min_area_px=100)
        self.classify_stage = Classify()
        self.tracker = Tracker(dt=1.0 / target_fps)
        self.predictor = Predictor(dt=1.0 / target_fps)
        
        # Agent & Decision
        if agent_mode == "bedrock" and bedrock_model_id:
            self.agent_client = BedrockAgentClient(model_id=bedrock_model_id)
        else:
            self.agent_client = MockAgent()
            
        self.decision_engine = DecisionEngine(
            agent_client=self.agent_client,
            t_intercept=0.75,
            t_ambiguous_low=0.40,
            actuation_delay_ms=80.0,
            min_tti_margin_ms=150.0,
        )
        self.actuator = SimulatedActuator(
            delay_ms=80.0,
            jitter_ms=10.0,
            cone_angle_deg=25.0,
            jet_range_px=120.0,
            cooldown_ms=400.0,
        )
        
        # Control & State
        self.is_running = False
        self.is_paused = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.seq = 0
        self.dropped_frames = 0
        self.active_tracks: list[dict] = []
        self.latest_predictions: list[dict] = []
        self.latest_metrics: dict[str, Any] = {}
        self.intercepted_tracks: set[int] = set()

    def start(self) -> None:
        with self._lock:
            if self.is_running:
                return
            self.is_running = True
            self.is_paused = False
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def pause(self) -> None:
        self.is_paused = True

    def resume(self) -> None:
        self.is_paused = False

    def stop(self) -> None:
        self.is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self.source.close()

    def set_kill_switch(self, enabled: bool) -> None:
        self.actuator.kill_switch(enabled)
        self.audit_repo.append(
            AuditEvent(
                id=uuid4(),
                actor="operator",
                action="kill_switch",
                entity_type="actuator",
                entity_id=self.session_id,
                details={"kill_switch": enabled},
            )
        )

    def manual_fire(self, target_px: tuple[float, float]) -> ActuationEvent:
        event = self.actuator.fire(time.perf_counter() * 1000.0, target_px)
        self.audit_repo.append(
            AuditEvent(
                id=uuid4(),
                actor="human_operator",
                action="manual_fire",
                entity_type="actuator",
                entity_id=self.session_id,
                details={"target_px": list(target_px), "applied": event.applied},
            )
        )
        return event

    def add_subscriber(self, q: asyncio.Queue) -> None:
        with self._lock:
            self.subscribers.append(q)

    def remove_subscriber(self, q: asyncio.Queue) -> None:
        with self._lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def _broadcast_sync(self, msg: dict[str, Any]) -> None:
        with self._lock:
            dead_subs = []
            for sub in self.subscribers:
                try:
                    if sub.full():
                        try:
                            sub.get_nowait()
                        except Exception:
                            pass
                    sub.put_nowait(msg)
                except Exception:
                    dead_subs.append(sub)
            for ds in dead_subs:
                if ds in self.subscribers:
                    self.subscribers.remove(ds)

    def _run_loop(self) -> None:
        logger.info(f"SessionWorker {self.session_id} loop started.")
        frame_interval_s = 1.0 / self.target_fps
        target_line_y = 250.0  # Default interceptor line y-coordinate
        
        while self.is_running:
            t0 = time.perf_counter()
            if self.is_paused:
                time.sleep(0.05)
                continue

            frame_data = self.source.read()
            if frame_data is None:
                # Source exhausted (e.g. video finished without loop)
                time.sleep(0.05)
                continue

            self.seq = frame_data.seq
            t_cap = frame_data.t_capture_ms
            image = frame_data.image

            # 1. Pipeline execution
            ctx = PipelineContext(frame=image, t_capture_ms=t_cap, seq=self.seq)
            ctx = self.homography_stage.process(ctx)
            ctx = self.roi_stage.process(ctx)
            ctx = self.bg_stage.process(ctx)
            ctx = self.morph_stage.process(ctx)
            ctx = self.contour_stage.process(ctx)
            ctx = self.classify_stage.process(ctx)

            # 2. Tracking update
            t_track_start = time.perf_counter()
            tracks = self.tracker.update(ctx.detections)
            ctx.stage_timings["Tracker"] = (time.perf_counter() - t_track_start) * 1000.0
            self.active_tracks = tracks

            # 3. Trajectory projection & TTI
            t_pred_start = time.perf_counter()
            predictions = self.predictor.predict(
                tracks=tracks,
                horizons_ms=[100, 250, 500],
                target_line_y_px=target_line_y,
            )
            ctx.stage_timings["Predictor"] = (time.perf_counter() - t_pred_start) * 1000.0
            self.latest_predictions = predictions

            # 4. Decision Engine assessment per track
            pred_by_track = {p["track_id"]: p for p in predictions}
            decisions_this_frame = []
            
            for trk in tracks:
                tid = trk["id"]
                pred = pred_by_track.get(tid, {})
                conf = trk.get("confidence", 0.0)
                tti = pred.get("tti_ms")
                crosses = pred.get("crosses_zone", False)
                at_jet = pred.get("at_jet_position_px")
                
                # Check jet alignment (is x inside jet cone around interceptor?)
                jet_center_x = 300.0
                jet_half_width = 40.0
                pred_x = at_jet[0] if at_jet else trk["centroid"][0]
                jet_aligned = abs(pred_x - jet_center_x) <= jet_half_width

                dec = self.decision_engine.evaluate(
                    session_id=self.session_id,
                    track_id=tid,
                    confidence=conf,
                    class_probs=trk.get("class_probs", {}),
                    tti_ms=tti,
                    crosses_zone=crosses,
                    jet_aligned=jet_aligned,
                    thresholds={"t_intercept": 0.75, "t_ambiguous_low": 0.40},
                )
                
                # If intercept decided and not already intercepted
                if dec.action == "intercept" and tid not in self.intercepted_tracks:
                    # Final guardrail evaluation
                    act_state = self.actuator.state()
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
                        self.actuator.arm()
                        target_pt = (pred_x, target_line_y)
                        event = self.actuator.fire(t_cap, target_pt)
                        if event.applied:
                            self.intercepted_tracks.add(tid)
                            self._broadcast_sync({
                                "type": "actuator",
                                "session_id": self.session_id,
                                "seq": self.seq,
                                "payload": {
                                    "track_id": tid,
                                    "applied": True,
                                    "target": target_pt,
                                    "state": "firing",
                                },
                            })
                    else:
                        logger.warning(f"Guardrail {veto.guardrail} blocked intercept: {veto.reason}")

                # Save decision & broadcast
                dec_model = Decision(
                    id=uuid4(),
                    session_id=UUID(self.session_id) if "-" in self.session_id else uuid4(),
                    track_id=tid,
                    state_from=dec.state_from.value,
                    state_to=dec.state_to.value,
                    action=DecisionAction(dec.action),
                    tier=DecisionTier.TIER1 if dec.tier == "1" else DecisionTier.TIER2,
                    confidence_before=dec.confidence_before,
                    confidence_after=dec.confidence_after,
                    reason=dec.reason,
                    evidence_ids=[],
                    t_ms=t_cap,
                )
                self.decision_repo.save(dec_model)
                decisions_this_frame.append(dec_model.model_dump(mode="json"))

                # Review queue escalation
                if dec.action == "request_human":
                    rev = ReviewItem(
                        id=uuid4(),
                        decision_id=dec_model.id,
                        evidence_ids=[],
                        recommendation=f"Escalate track #{tid} for human inspection (conf={conf:.2f})",
                        deadline_ms=t_cap + 10000.0,
                        status=ReviewStatus.PENDING,
                    )
                    self.review_repo.save(rev)
                    self._broadcast_sync({
                        "type": "review_item",
                        "session_id": self.session_id,
                        "seq": self.seq,
                        "payload": rev.model_dump(mode="json"),
                    })

            # Broadcast live state update to frontend subscribers
            dt_compute = (time.perf_counter() - t0) * 1000.0
            fps_live = 1000.0 / max(1.0, dt_compute)
            metrics = {
                "fps": round(fps_live, 1),
                "compute_ms": round(dt_compute, 2),
                "stage_timings": {k: round(v, 2) for k, v in ctx.stage_timings.items()},
                "active_tracks_count": len(tracks),
                "dropped_frames": self.ring_buffer.dropped_frames,
                "actuator_state": self.actuator.state(),
            }
            self.latest_metrics = metrics

            # Encode frame to JPEG for streaming (1 in 2 frames for network efficiency)
            if self.seq % 2 == 0:
                _, jpeg_bytes = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 70])
                self._broadcast_sync({
                    "type": "frame",
                    "session_id": self.session_id,
                    "seq": self.seq,
                    "t_capture_ms": t_cap,
                    "payload": {
                        "tracks": tracks,
                        "predictions": predictions,
                        "decisions": decisions_this_frame,
                        "metrics": metrics,
                        "jpeg_b64": jpeg_bytes.tobytes().hex(),
                    },
                })

            # Sleep to maintain target FPS
            elapsed = time.perf_counter() - t0
            sleep_time = frame_interval_s - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        logger.info(f"SessionWorker {self.session_id} loop finished.")
