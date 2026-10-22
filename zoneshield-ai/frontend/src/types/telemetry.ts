/**
 * ZoneShield AI - Type Definitions & Contracts
 * Pure types matching backend OpenAPI/WebSocket specification and domain models.
 */

export type TrackClass = 'foreign' | 'legitimate' | 'lookalike' | 'debris' | 'unknown';

export type TrackStateMachine =
  | 'MONITORING'
  | 'TRACKING'
  | 'ASSESSING'
  | 'INTERCEPTING'
  | 'GATHERING_EVIDENCE'
  | 'AWAITING_HUMAN'
  | 'VERIFYING';

export type DecisionAction = 'monitor' | 'gather_evidence' | 'request_human' | 'intercept';
export type DecisionTier = '1' | '2' | 'human' | 'guardrail';
export type ReviewStatus = 'pending' | 'approved' | 'dismissed' | 'more_evidence' | 'expired';

export type GuardrailId = 'G1' | 'G2' | 'G3' | 'G4' | 'G5';

export interface GuardrailInfo {
  id: GuardrailId;
  name: string;
  description: string;
  threshold: string;
  status: 'armed' | 'pass' | 'veto';
  lastVetoMs?: number;
  lastVetoReason?: string;
}

export interface PipelineTimings {
  UndistortHomography: number;
  ROIDownscale: number;
  BackgroundSubtract: number;
  Morphology: number;
  Contours: number;
  Tracker: number;
  Predictor: number;
  [key: string]: number;
}

export interface TrackData {
  id: number;
  centroid: [number, number]; // [x_px, y_px] or [x_mm, y_mm]
  velocity: [number, number]; // [vx, vy]
  class: TrackClass | string;
  confidence: number;
  state?: TrackStateMachine;
  history?: [number, number][];
  bbox?: [number, number, number, number]; // [x, y, w, h]
  class_probs?: Record<string, number>;
  age_frames?: number;
}

export interface PredictionData {
  track_id: number;
  tti_ms: number | null;
  crosses_zone: boolean;
  at_jet_position_px?: [number, number];
  positions_mm?: [number, number][];
  uncertainty_px?: number;
}

export interface AgentToolCall {
  tool: 'request_more_frames' | 'intercept' | 'escalate_human';
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  timestamp_ms: number;
}

export interface DecisionData {
  id?: string;
  session_id?: string;
  track_id: number;
  state_from?: string;
  state_to?: string;
  action: DecisionAction;
  tier: DecisionTier | string;
  confidence_before?: number;
  confidence_after?: number;
  reason: string;
  t_ms?: number;
  tool_calls?: AgentToolCall[];
}

export interface ActuatorState {
  state: 'idle' | 'armed' | 'firing' | 'cooldown' | 'unknown' | 'disconnected';
  simulated: true; // Non-negotiable C1 constraint
  kill_switch: boolean;
  cooldown_remaining_ms?: number;
  last_fire_ms?: number;
}

export interface TelemetryMetrics {
  fps: number;
  compute_ms: number;
  active_tracks_count: number;
  dropped_frames: number;
}

export interface TelemetryMessage {
  type: 'telemetry' | 'frame' | 'actuator' | 'review_item';
  session_id: string;
  seq: number;
  t_capture_ms: number;
  metrics: TelemetryMetrics;
  pipeline_timings: PipelineTimings;
  tracks: TrackData[];
  predictions: PredictionData[];
  decisions: DecisionData[];
  actuator_state: ActuatorState;
}

export interface ReviewItemData {
  id: string;
  decision_id: string;
  track_id?: number;
  evidence_ids: string[];
  evidence_crops?: string[]; // URLs or base64
  recommendation: string;
  confidence?: number;
  deadline_ms: number;
  status: ReviewStatus;
  created_at_ms?: number;
  resolved_by?: string;
  resolved_at_ms?: number;
}

export interface ActuatorTimelineEvent {
  id: string;
  timestamp: number;
  type: 'simulated_fire' | 'veto' | 'cooldown' | 'kill_switch';
  guardrail?: GuardrailId;
  reason: string;
  track_id?: number;
  target?: [number, number];
  duration_ms?: number;
}

export interface SystemInfoData {
  product: string;
  version: string;
  opencv_version: string;
  cool_proof: {
    cool_active: boolean;
    has_neon: boolean;
    has_kleidicv: boolean;
    status: string;
    acceleration_engine: string;
    quick_threshold_ms?: number;
  };
  hardware: {
    architecture: string;
    is_arm64: boolean;
    system: string;
    processor: string;
    python_version: string;
    target_instance_family: string;
  };
  active_sessions: number;
  kill_switch_active: boolean;
  agent_mode: string;
}

export type ViewportMode = 'radar2d' | 'iso3d' | 'mog2';

export interface ViewportLayers {
  trajectories: boolean;
  uncertaintyCone: boolean;
  jetEnvelope: boolean;
  sensorGrid: boolean;
}

export type ConnectionState = 'live' | 'reconnecting' | 'offline';
