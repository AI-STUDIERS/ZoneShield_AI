"""FastAPI application for ZoneShield AI backend service.

Provides REST API (/api/v1) and WebSocket streaming endpoints (/ws/sessions/{id}/stream).
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import cv2
from fastapi import APIRouter, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.config import settings
from backend.models import (
    Calibration,
    Decision,
    ReviewItem,
    ReviewStatus,
    Session,
    SessionState,
    SourceConfig,
    SourceType,
)
from backend.storage import (
    AuditRepo,
    BenchmarkRepo,
    DecisionRepo,
    EvalRepo,
    EvidenceStore,
    ReviewRepo,
    SessionRepo,
    SQLiteStorage,
)
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_vision = _root / "vision"
for _p in (str(_root), str(_vision)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from zoneshield.framesource import SimulatorLive, VideoFile
from zoneshield.selfcheck import run_selfcheck
from backend.worker import SessionWorker

# Storage initialization
storage = SQLiteStorage(settings.db_path)
session_repo = SessionRepo(storage)
decision_repo = DecisionRepo(storage)
review_repo = ReviewRepo(storage)
audit_repo = AuditRepo(storage)
benchmark_repo = BenchmarkRepo(storage)
eval_repo = EvalRepo(storage)
evidence_store = EvidenceStore(settings.evidence_path)

# Active session workers
active_workers: dict[str, SessionWorker] = {}

# Global kill switch state
global_kill_switch: bool = False

app = FastAPI(
    title="ZoneShield AI API",
    version="0.1.0",
    description="Active Conveyor Threat Interception System with OpenCV 5 and AWS Graviton (COOL)",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api/v1")


# --- DTO Models ---
class CreateSessionRequest(BaseModel):
    name: str = "Live Production Belt"
    source_type: SourceType = SourceType.SIMULATOR
    scenario_id: Optional[str] = "S1"
    fps_target: int = 30


class ManualFireRequest(BaseModel):
    session_id: Optional[str] = None
    target_x: float = 300.0
    target_y: float = 250.0
    reason: str = "Manual operator test"
    force: bool = False


class ResolveReviewRequest(BaseModel):
    operator: str = "Operator-1"
    status: ReviewStatus = ReviewStatus.APPROVED
    reason: Optional[str] = "Visual inspection confirmed foreign contaminant"


class KillSwitchRequest(BaseModel):
    reason: str = "Emergency stop requested"


# --- SESSIONS ENDPOINTS ---
@api_router.post("/sessions", response_model=Session)
def create_session(req: CreateSessionRequest):
    session = Session(
        id=uuid4(),
        name=req.name,
        source=req.source_type,
        state=SessionState.READY,
        scenario_id=req.scenario_id,
    )
    session_repo.save(session)
    return session


@api_router.get("/sessions", response_model=list[Session])
def list_sessions():
    return session_repo.list_all()


@api_router.get("/sessions/{id}", response_model=Session)
def get_session(id: str):
    sess = session_repo.get(id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return sess


@api_router.post("/sessions/{id}/start")
def start_session(id: str):
    sess = session_repo.get(id)
    if not sess:
        try:
            sess_uuid = UUID(id)
        except Exception:
            sess_uuid = uuid4()
        sess = Session(
            id=sess_uuid,
            name=f"Production Session {str(id)[:8]}",
            source=SourceType.SIMULATOR,
            state=SessionState.READY,
        )
        session_repo.save(sess)
    
    sid = str(id)
    if sid in active_workers and active_workers[sid].is_running:
        return {"status": "already_running", "session_id": sid}
        
    # Create frame source
    if sess.source == SourceType.SIMULATOR:
        source = SimulatorLive(
            width=640,
            height=480,
            fps=30,
            seed=42,
            scenario={"speed": 1.0, "foreign_count": 3, "legit_count": 3},
        )
    else:
        source = SimulatorLive(width=640, height=480, fps=30, seed=101)

    worker = SessionWorker(
        session_id=sid,
        source=source,
        session_repo=session_repo,
        decision_repo=decision_repo,
        review_repo=review_repo,
        audit_repo=audit_repo,
        evidence_store=evidence_store,
        agent_mode=settings.agent_mode,
        bedrock_model_id=settings.bedrock_model_id,
        target_fps=settings.fps_target,
    )
    if global_kill_switch:
        worker.set_kill_switch(True)
    worker.start()
    active_workers[sid] = worker
    
    sess.state = SessionState.RUNNING
    session_repo.save(sess)
    return {"status": "started", "session_id": sid}


@api_router.post("/sessions/{id}/pause")
def pause_session(id: str):
    sid = str(id)
    if sid in active_workers:
        active_workers[sid].pause()
        sess = session_repo.get(id)
        if sess:
            sess.state = SessionState.PAUSED
            session_repo.save(sess)
        return {"status": "paused", "session_id": sid}
    raise HTTPException(status_code=404, detail="Active worker not found")


@api_router.post("/sessions/{id}/resume")
def resume_session(id: str):
    sid = str(id)
    if sid in active_workers:
        active_workers[sid].resume()
        sess = session_repo.get(id)
        if sess:
            sess.state = SessionState.RUNNING
            session_repo.save(sess)
        return {"status": "resumed", "session_id": sid}
    raise HTTPException(status_code=404, detail="Active worker not found")


@api_router.post("/sessions/{id}/stop")
def stop_session(id: str):
    sid = str(id)
    if sid in active_workers:
        active_workers[sid].stop()
        del active_workers[sid]
    sess = session_repo.get(id)
    if sess:
        sess.state = SessionState.STOPPED
        session_repo.save(sess)
    return {"status": "stopped", "session_id": sid}


@api_router.delete("/sessions/{id}")
def delete_session(id: str):
    sid = str(id)
    if sid in active_workers:
        active_workers[sid].stop()
        del active_workers[sid]
    session_repo.delete(id)
    return {"status": "deleted", "session_id": sid}


# --- DECISIONS & REVIEW ---
@api_router.get("/sessions/{id}/decisions")
def get_session_decisions(id: str, limit: int = 50):
    return decision_repo.list_by_session(id, limit=limit)


@api_router.get("/decisions/{id}")
def get_decision_detail(id: str):
    dec = decision_repo.get(id)
    if not dec:
        raise HTTPException(status_code=404, detail="Decision not found")
    return dec


@api_router.get("/review-queue")
def get_review_queue():
    return review_repo.list_pending()


@api_router.post("/review/{id}/resolve")
def resolve_review(id: str, req: ResolveReviewRequest):
    item = review_repo.get(id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    
    rev = ReviewItem(
        id=UUID(item["id"]),
        decision_id=UUID(item["decision_id"]),
        evidence_ids=json.loads(item["evidence_ids"]),
        recommendation=item["recommendation"],
        deadline_ms=item["deadline_ms"],
        status=req.status,
        resolved_by=req.operator,
        resolved_at_ms=time.perf_counter() * 1000.0,
    )
    review_repo.save(rev)
    return {"status": "resolved", "id": id, "resolution": req.status.value}


# --- ACTUATOR & SAFETY ---
@api_router.post("/actuator/manual-fire")
def manual_fire(req: ManualFireRequest):
    sid = req.session_id or (list(active_workers.keys())[0] if active_workers else None)
    if not sid or sid not in active_workers:
        raise HTTPException(status_code=400, detail="No active session worker to fire actuator")
    
    event = active_workers[sid].manual_fire((req.target_x, req.target_y))
    return {
        "status": "fired" if event.applied else "blocked",
        "applied": event.applied,
        "blocked_by": event.blocked_by_guardrail,
        "delay_ms": event.delay_ms,
    }


@api_router.post("/system/kill-switch")
def enable_kill_switch(req: KillSwitchRequest):
    global global_kill_switch
    global_kill_switch = True
    for worker in active_workers.values():
        worker.set_kill_switch(True)
    return {"status": "kill_switch_active", "all_actuators_disabled": True, "reason": req.reason}


@api_router.post("/system/kill-switch/reset")
def reset_kill_switch():
    global global_kill_switch
    global_kill_switch = False
    for worker in active_workers.values():
        worker.set_kill_switch(False)
    return {"status": "kill_switch_reset", "actuators_enabled": True}


# --- BENCHMARKS & EVALUATION ---
@api_router.get("/benchmarks")
def list_benchmarks():
    return benchmark_repo.list_all()


@api_router.get("/evaluation/runs")
def list_eval_runs():
    return eval_repo.list_all()


# --- SYSTEM DIAGNOSTICS & TELEMETRY ---
@api_router.get("/health")
def health():
    return {"status": "ok", "service": "ZoneShield AI"}


@api_router.get("/ready")
def ready():
    return {"status": "ready", "opencv": cv2.__version__, "cool_status": "configured"}


@api_router.get("/system/info")
def system_info():
    proof = run_selfcheck()
    return {
        "product": "ZoneShield AI",
        "version": "0.1.0",
        "opencv_version": cv2.__version__,
        "cool_proof": proof["cool"],
        "hardware": proof["hardware"],
        "active_sessions": len(active_workers),
        "kill_switch_active": global_kill_switch,
        "agent_mode": settings.agent_mode,
    }


@api_router.get("/metrics")
def get_metrics():
    """Prometheus-style telemetry metrics."""
    lines = [
        "# HELP zoneshield_active_sessions Number of running vision sessions",
        "# TYPE zoneshield_active_sessions gauge",
        f"zoneshield_active_sessions {len(active_workers)}",
        "# HELP zoneshield_kill_switch Actuator kill switch state (1=active, 0=normal)",
        "# TYPE zoneshield_kill_switch gauge",
        f"zoneshield_kill_switch {1 if global_kill_switch else 0}",
    ]
    for sid, w in active_workers.items():
        m = w.latest_metrics
        fps = m.get("fps", 0)
        compute = m.get("compute_ms", 0)
        tracks = m.get("active_tracks_count", 0)
        dropped = m.get("dropped_frames", 0)
        lines.append(f'zoneshield_fps{{session="{sid}"}} {fps}')
        lines.append(f'zoneshield_latency_ms{{session="{sid}"}} {compute}')
        lines.append(f'zoneshield_tracks{{session="{sid}"}} {tracks}')
        lines.append(f'zoneshield_dropped_frames{{session="{sid}"}} {dropped}')
    return PlainTextResponse("\n".join(lines) + "\n")


@api_router.get("/config")
def get_config():
    return {
        "env": settings.env,
        "agent_mode": settings.agent_mode,
        "fps_target": settings.fps_target,
        "opencv_major_required": settings.opencv_major_required,
        "num_threads": settings.num_threads,
        "db_backend": settings.db_backend,
    }


# --- WEBSOCKET STREAMING ---
@app.websocket("/ws/sessions/{id}/stream")
async def websocket_session_stream(websocket: WebSocket, id: str):
    await websocket.accept()
    sid = str(id)
    
    # If session doesn't have an active worker, start one automatically for convenience
    if sid not in active_workers:
        start_session(sid)
        
    worker = active_workers.get(sid)
    if not worker:
        await websocket.close(code=1008)
        return

    queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    worker.add_subscriber(queue)
    
    try:
        while True:
            msg = await queue.get()
            await websocket.send_json(msg)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        worker.remove_subscriber(queue)


# Mount router
app.include_router(api_router)

# Mount frontend directory for static assets if present
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
dist_dir = frontend_dir / "dist"
assets_dir = dist_dir / "assets"

assets_dir.mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
def index():
    """Serve cutting-edge vision frontend, with graceful fallback to tactical dashboard."""
    dist_index = dist_dir / "index.html"
    if dist_index.exists():
        return HTMLResponse(content=dist_index.read_text(encoding="utf-8"))
    legacy_file = frontend_dir / "legacy_dashboard.html"
    if legacy_file.exists():
        return HTMLResponse(content=legacy_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>ZoneShield AI Backend Ready</h1><p>Frontend static files loading...</p>")


@app.get("/legacy", response_class=HTMLResponse)
def legacy_dashboard():
    """Serve standalone tactical dashboard."""
    legacy_file = frontend_dir / "legacy_dashboard.html"
    if legacy_file.exists():
        return HTMLResponse(content=legacy_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Legacy Dashboard Not Found</h1>", status_code=404)

