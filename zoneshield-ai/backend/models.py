"""ZoneShield AI domain models (Pydantic v2, fully typed, versioned).

Models from backend spec section 3:
Session, SourceConfig, Calibration, FrameMeta, Track, Prediction,
RiskAssessment, Decision, AgentTrace, ToolCall, Evidence, ReviewItem,
ActuationEvent, OutcomeRecord, BenchmarkRun, EvalRun, AuditEvent.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class SessionState(str, Enum):
    CREATING = "creating"
    CALIBRATING = "calibrating"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ARCHIVED = "archived"


class SourceType(str, Enum):
    SIMULATOR = "simulator"
    WEBCAM = "webcam"
    RTSP = "rtsp"
    FILE = "file"


class DecisionAction(str, Enum):
    MONITOR = "monitor"
    GATHER_EVIDENCE = "gather_evidence"
    REQUEST_HUMAN = "request_human"
    INTERCEPT = "intercept"


class DecisionTier(str, Enum):
    TIER1 = "1"
    TIER2 = "2"
    HUMAN = "human"
    GUARDRAIL = "guardrail"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DISMISSED = "dismissed"
    MORE_EVIDENCE = "more_evidence"
    EXPIRED = "expired"


class ActuatorState(str, Enum):
    IDLE = "idle"
    ARMED = "armed"
    FIRING = "firing"
    COOLDOWN = "cooldown"


class Session(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    name: str
    source: SourceType
    state: SessionState = SessionState.CREATING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    config_hash: Optional[str] = None
    scenario_id: Optional[str] = None
    calibration_id: Optional[str] = None


class SourceConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    type: SourceType
    uri: Optional[str] = None
    fps_target: int = 30
    resolution: Optional[str] = None


class Calibration(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    image_points: list[list[float]]
    world_points_mm: list[list[float]]
    homography: list[list[float]]
    shield_zone_polygon_mm: list[list[float]]
    interceptor_line_mm: float
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FrameMeta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    session_id: UUID
    seq: int
    t_capture_ms: float
    t_received_ms: float = Field(default_factory=lambda: datetime.utcnow().timestamp() * 1000)
    width: int
    height: int


class Track(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    bbox: list[float]
    centroid_mm: list[float]
    velocity_mm_s: list[float]
    covariance: list[list[float]]
    class_probs: dict[str, float]
    confidence: float
    occlusion: bool = False
    age_frames: int = 0


class Prediction(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    track_id: int
    horizon_ms: list[int]
    positions_mm: list[list[float]]
    uncertainty_mm: list[float]
    tti_ms: Optional[float] = None
    crosses_zone: bool = False
    at_jet_position_mm: Optional[list[float]] = None


class RiskAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    track_id: int
    confidence: float
    score_components: dict[str, float]
    timing_feasible: bool
    jet_alignment_ok: bool


class Decision(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    track_id: int
    state_from: str
    state_to: str
    action: DecisionAction
    tier: DecisionTier
    confidence_before: float
    confidence_after: Optional[float] = None
    reason: str
    evidence_ids: list[UUID] = Field(default_factory=list)
    trace_id: Optional[UUID] = None
    t_ms: float = 0.0


class ToolCall(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    args: dict
    result_summary: str
    evidence_ids: list[UUID] = Field(default_factory=list)
    confidence_delta: float = 0.0
    t_ms: float = 0.0


class AgentTrace(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    decision_id: UUID
    steps: list[ToolCall] = Field(default_factory=list)
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    model_id: str
    latency_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0


class Evidence(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    kind: str
    uri: str
    t_ms: float
    track_id: int


class ReviewItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    decision_id: UUID
    evidence_ids: list[UUID] = Field(default_factory=list)
    recommendation: str
    deadline_ms: float
    status: ReviewStatus = ReviewStatus.PENDING
    resolved_by: Optional[str] = None
    resolved_at_ms: Optional[float] = None


class ActuationEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    track_id: int
    t_fire_ms: float
    delay_ms: float
    applied: bool
    in_cone: bool
    blocked_by_guardrail: Optional[str] = None


class OutcomeRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    actuation_id: Optional[UUID] = None
    track_id: int
    left_zone_path: bool = False
    verified_at_ms: float = Field(default_factory=lambda: datetime.utcnow().timestamp() * 1000)


class BenchmarkRun(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    config: str
    env_fingerprint: dict
    cool_proof: Optional[dict] = None
    results_uri: Optional[str] = None
    status: str = "running"
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None


class EvalRun(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    suite: str
    seeds: list[int]
    metrics: dict
    confusion: Optional[dict] = None
    failure_cases: list[dict] = Field(default_factory=list)
    status: str = "running"


class AuditEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    t_ms: float = Field(default_factory=lambda: datetime.utcnow().timestamp() * 1000)
    actor: str
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    details: dict = Field(default_factory=dict)