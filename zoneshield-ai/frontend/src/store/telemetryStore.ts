import type {
  ActuatorState,
  ActuatorTimelineEvent,
  ConnectionState,
  DecisionData,
  GuardrailId,
  GuardrailInfo,
  PipelineTimings,
  PredictionData,
  ReviewItemData,
  SystemInfoData,
  TelemetryMessage,
  TelemetryMetrics,
  TrackData,
  ViewportLayers,
  ViewportMode,
} from '../types/telemetry';

export type TabId = 'telemetry' | 'trace' | 'review' | 'selfcheck';

export interface ActuatorBurst {
  id: string;
  trackId?: number;
  targetX: number;
  targetY: number;
  timestamp: number;
  active: boolean;
}

export interface RollingAverageMetrics {
  avgFps: number;
  avgComputeMs: number;
  deltaFps: number;
  deltaComputeMs: number;
}

export interface StoreState {
  // Session & Connection
  sessionId: string;
  sessionState: 'ready' | 'running' | 'paused' | 'stopped';
  connectionState: ConnectionState;
  reconnectAttempt: number;
  nextRetrySeconds: number;
  lastFrameTimestamp: number;
  isMockMode: boolean;
  debugMode: boolean;

  // Viewport & UI Configuration
  viewportMode: ViewportMode;
  activeTab: TabId;
  layers: ViewportLayers;
  highlightedTrackId: number | null;
  audioEnabled: boolean;

  // Real-time Metrics & Timings
  metrics: TelemetryMetrics;
  rollingAverages: RollingAverageMetrics;
  pipelineTimings: PipelineTimings;
  latencyHistory: number[]; // Ring buffer (last 120 samples)

  // Live Entities
  tracks: TrackData[];
  predictions: PredictionData[];
  decisions: DecisionData[];
  reviewQueue: ReviewItemData[];
  actuatorState: ActuatorState;
  bursts: ActuatorBurst[];

  // Guardrails & Timeline
  guardrails: Record<GuardrailId, GuardrailInfo>;
  actuatorTimeline: ActuatorTimelineEvent[]; // Last 60s events

  // Self-Check Data
  systemInfo: SystemInfoData | null;

  // Action Counters
  simulatedThreatsCount: number;
}

type Listener = () => void;

class TelemetryStore {
  private state: StoreState;
  private listeners: Set<Listener> = new Set();
  private transientFrame: TelemetryMessage | null = null;
  private fpsBuffer: number[] = [];
  private computeBuffer: number[] = [];
  private lastUiPushTimestamp = 0;

  constructor() {
    const isMock = typeof window !== 'undefined' && window.location.search.includes('mock=1');
    const isDebug = typeof window !== 'undefined' && window.location.search.includes('debug=1');

    this.state = {
      sessionId: '00000000-0000-0000-0000-000000000001',
      sessionState: 'ready',
      connectionState: 'reconnecting',
      reconnectAttempt: 0,
      nextRetrySeconds: 0,
      lastFrameTimestamp: 0,
      isMockMode: isMock,
      debugMode: isDebug,

      viewportMode: 'radar2d',
      activeTab: 'telemetry',
      layers: {
        trajectories: true,
        uncertaintyCone: true,
        jetEnvelope: true,
        sensorGrid: true,
      },
      highlightedTrackId: null,
      audioEnabled: true,

      metrics: {
        fps: 0,
        compute_ms: 0,
        active_tracks_count: 0,
        dropped_frames: 0,
      },
      rollingAverages: {
        avgFps: 0,
        avgComputeMs: 0,
        deltaFps: 0,
        deltaComputeMs: 0,
      },
      pipelineTimings: {
        UndistortHomography: 0.0,
        ROIDownscale: 0.0,
        BackgroundSubtract: 0.0,
        Morphology: 0.0,
        Contours: 0.0,
        Tracker: 0.0,
        Predictor: 0.0,
      },
      latencyHistory: new Array(120).fill(0),

      tracks: [],
      predictions: [],
      decisions: [],
      reviewQueue: [],
      actuatorState: {
        state: 'unknown', // Fail-safe default
        simulated: true, // Non-negotiable C1
        kill_switch: false,
      },
      bursts: [],

      guardrails: {
        G1: {
          id: 'G1',
          name: 'TTI Margin',
          description: 'Minimum Time-to-Intercept threshold (>= 230ms)',
          threshold: '>= 230 ms',
          status: 'armed',
        },
        G2: {
          id: 'G2',
          name: 'Jet Cone Alignment',
          description: 'Trajectory must align within jet dispersion cone (260-340mm)',
          threshold: '260 - 340 mm',
          status: 'armed',
        },
        G3: {
          id: 'G3',
          name: 'Ambiguity Floor',
          description: 'Tier 1 confidence threshold (>= 0.40)',
          threshold: '>= 0.40 conf',
          status: 'armed',
        },
        G4: {
          id: 'G4',
          name: 'Cooldown Period',
          description: 'Mandatory simulated pneumatic recovery (400ms)',
          threshold: '400 ms',
          status: 'armed',
        },
        G5: {
          id: 'G5',
          name: 'Emergency Stop',
          description: 'Hardware kill-switch interlock',
          threshold: 'ACTIVE / OFF',
          status: 'armed',
        },
      },
      actuatorTimeline: [],
      systemInfo: null,
      simulatedThreatsCount: 0,
    };
  }

  public getState(): StoreState {
    return this.state;
  }

  public subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notify() {
    this.listeners.forEach(fn => fn());
  }

  /**
   * Fast-path telemetry ingest. Stores the raw frame directly for 60 FPS canvas loop.
   * Throttles React state notifications to ~4-5 Hz to preserve DOM performance.
   */
  public ingestTelemetry(msg: TelemetryMessage) {
    this.transientFrame = msg;
    const now = Date.now();

    // Update ring buffer for sparklines
    const computeMs = msg.metrics?.compute_ms || 0;
    const fps = msg.metrics?.fps || 0;

    const newHistory = [...this.state.latencyHistory.slice(1), computeMs];
    this.state.latencyHistory = newHistory;

    // Rolling 10s averages
    this.fpsBuffer.push(fps);
    if (this.fpsBuffer.length > 60) this.fpsBuffer.shift();
    this.computeBuffer.push(computeMs);
    if (this.computeBuffer.length > 60) this.computeBuffer.shift();

    const avgFps = this.fpsBuffer.reduce((a, b) => a + b, 0) / this.fpsBuffer.length;
    const avgCompute = this.computeBuffer.reduce((a, b) => a + b, 0) / this.computeBuffer.length;

    // Check for actuator burst events
    if (msg.actuator_state?.state === 'firing') {
      const activeTrack = msg.tracks?.find(t => t.class === 'foreign');
      const burstId = `burst_${now}_${Math.random().toString(36).substring(2, 6)}`;
      this.state.bursts.push({
        id: burstId,
        trackId: activeTrack?.id,
        targetX: activeTrack?.centroid[0] || 300,
        targetY: activeTrack?.centroid[1] || 250,
        timestamp: now,
        active: true,
      });

      // Keep only recent 5 bursts
      if (this.state.bursts.length > 5) {
        this.state.bursts.shift();
      }

      // Record actuator timeline event (strictly labeled simulated)
      this.addTimelineEvent({
        id: burstId,
        timestamp: now,
        type: 'simulated_fire',
        reason: 'Simulated air-jet deflection trigger (C1)',
        track_id: activeTrack?.id,
      });

      this.state.simulatedThreatsCount += 1;
    }

    // Check decisions for guardrail vetoes or new entries
    if (msg.decisions && msg.decisions.length > 0) {
      msg.decisions.forEach(dec => {
        // Look for veto reason
        if (dec.reason && dec.reason.toLowerCase().includes('veto')) {
          let vetoGuardrail: GuardrailId = 'G1';
          if (dec.reason.includes('G2') || dec.reason.toLowerCase().includes('cone')) vetoGuardrail = 'G2';
          else if (dec.reason.includes('G3') || dec.reason.toLowerCase().includes('ambiguity')) vetoGuardrail = 'G3';
          else if (dec.reason.includes('G4') || dec.reason.toLowerCase().includes('cooldown')) vetoGuardrail = 'G4';
          else if (dec.reason.includes('G5') || dec.reason.toLowerCase().includes('kill')) vetoGuardrail = 'G5';

          this.flashGuardrailVeto(vetoGuardrail, dec.reason);
        }
      });

      // Merge decisions into state (prepend, keep max 100)
      const existingIds = new Set(this.state.decisions.map(d => `${d.track_id}_${d.action}_${d.reason}`));
      const newDecisions = msg.decisions.filter(d => !existingIds.has(`${d.track_id}_${d.action}_${d.reason}`));
      if (newDecisions.length > 0) {
        this.state.decisions = [...newDecisions, ...this.state.decisions].slice(0, 100);
      }
    }

    // Fail-safe check on actuator state
    const cleanActuatorState: ActuatorState = {
      state: msg.actuator_state?.state || 'idle',
      simulated: true,
      kill_switch: !!msg.actuator_state?.kill_switch,
      cooldown_remaining_ms: msg.actuator_state?.cooldown_remaining_ms,
      last_fire_ms: msg.actuator_state?.last_fire_ms,
    };

    // Update state fields
    this.state.lastFrameTimestamp = now;
    this.state.metrics = msg.metrics || this.state.metrics;
    this.state.pipelineTimings = msg.pipeline_timings || this.state.pipelineTimings;
    this.state.tracks = msg.tracks || [];
    this.state.predictions = msg.predictions || [];
    this.state.actuatorState = cleanActuatorState;
    this.state.rollingAverages = {
      avgFps: Math.round(avgFps * 10) / 10,
      avgComputeMs: Math.round(avgCompute * 10) / 10,
      deltaFps: Math.round((fps - avgFps) * 10) / 10,
      deltaComputeMs: Math.round((computeMs - avgCompute) * 10) / 10,
    };

    // Rate-limit React updates to ~220ms (approx 4.5 Hz)
    if (now - this.lastUiPushTimestamp >= 220) {
      this.lastUiPushTimestamp = now;
      this.notify();
    }
  }

  /**
   * Synchronous accessor for the 60 FPS HTML5 Canvas render loop.
   */
  public getLatestFrameSnapshot(): TelemetryMessage | null {
    return this.transientFrame;
  }

  public setConnectionState(
    conn: ConnectionState,
    opts?: { attempt?: number; nextRetry?: number }
  ) {
    this.state.connectionState = conn;
    if (opts?.attempt !== undefined) this.state.reconnectAttempt = opts.attempt;
    if (opts?.nextRetry !== undefined) this.state.nextRetrySeconds = opts.nextRetry;

    // Fail-safe requirement: if disconnected/reconnecting, actuator state must become UNKNOWN
    if (conn !== 'live') {
      this.state.actuatorState = {
        state: 'unknown',
        simulated: true,
        kill_switch: this.state.actuatorState.kill_switch,
      };
    }

    this.notify();
  }

  public setSessionState(sessionState: 'ready' | 'running' | 'paused' | 'stopped') {
    this.state.sessionState = sessionState;
    this.notify();
  }

  public setViewportMode(mode: ViewportMode) {
    this.state.viewportMode = mode;
    this.notify();
  }

  public setActiveTab(tab: TabId) {
    this.state.activeTab = tab;
    this.notify();
  }

  public toggleLayer(key: keyof ViewportLayers) {
    this.state.layers = {
      ...this.state.layers,
      [key]: !this.state.layers[key],
    };
    this.notify();
  }

  public setHighlightedTrackId(id: number | null) {
    this.state.highlightedTrackId = id;
    this.notify();
  }

  public toggleAudio() {
    this.state.audioEnabled = !this.state.audioEnabled;
    this.notify();
  }

  public setKillSwitchState(active: boolean, reason = 'Operator triggered emergency stop') {
    this.state.actuatorState = {
      ...this.state.actuatorState,
      kill_switch: active,
      state: active ? 'idle' : this.state.actuatorState.state,
    };

    // Update G5 guardrail status
    this.state.guardrails.G5 = {
      ...this.state.guardrails.G5,
      status: active ? 'veto' : 'pass',
      lastVetoReason: active ? reason : undefined,
    };

    this.addTimelineEvent({
      id: `kill_${Date.now()}`,
      timestamp: Date.now(),
      type: 'kill_switch',
      guardrail: 'G5',
      reason: active ? `Kill Switch Engaged: ${reason}` : 'Kill Switch Cleared and Reset',
    });

    this.notify();
  }

  public flashGuardrailVeto(id: GuardrailId, reason: string) {
    const now = Date.now();
    this.state.guardrails[id] = {
      ...this.state.guardrails[id],
      status: 'veto',
      lastVetoMs: now,
      lastVetoReason: reason,
    };

    this.addTimelineEvent({
      id: `veto_${now}_${id}`,
      timestamp: now,
      type: 'veto',
      guardrail: id,
      reason,
    });

    // Auto restore to armed after 3 seconds
    setTimeout(() => {
      if (this.state.guardrails[id].status === 'veto' && id !== 'G5') {
        this.state.guardrails[id] = {
          ...this.state.guardrails[id],
          status: 'pass',
        };
        this.notify();
      }
    }, 3000);

    this.notify();
  }

  public addTimelineEvent(event: ActuatorTimelineEvent) {
    // Keep last 60 seconds of events
    const cutoff = Date.now() - 60000;
    this.state.actuatorTimeline = [
      event,
      ...this.state.actuatorTimeline.filter(e => e.timestamp >= cutoff),
    ].slice(0, 50);
  }

  public setReviewQueue(items: ReviewItemData[]) {
    this.state.reviewQueue = items;
    this.notify();
  }

  public resolveReviewItem(id: string, resolution: ReviewItemData['status']) {
    this.state.reviewQueue = this.state.reviewQueue.map(item => {
      if (item.id === id) {
        return {
          ...item,
          status: resolution,
          resolved_at_ms: Date.now(),
        };
      }
      return item;
    });
    this.notify();
  }

  public setDecisions(decisions: DecisionData[]) {
    this.state.decisions = decisions;
    this.notify();
  }

  public setSystemInfo(info: SystemInfoData) {
    this.state.systemInfo = info;
    this.notify();
  }
}

export const telemetryStore = new TelemetryStore();
