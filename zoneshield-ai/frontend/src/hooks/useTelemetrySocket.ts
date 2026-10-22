import { useEffect, useRef, useCallback } from 'react';
import { telemetryStore } from '../store/telemetryStore';
import { api } from '../api/client';
import type { TelemetryMessage, TrackData, PredictionData, DecisionData } from '../types/telemetry';

export function useTelemetrySocket(sessionId: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const countdownIntervalRef = useRef<number | null>(null);
  const attemptRef = useRef<number>(0);
  const isMockModeRef = useRef<boolean>(false);
  const mockIntervalRef = useRef<number | null>(null);

  // Check URL query parameters
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const isMock = window.location.search.includes('mock=1');
      isMockModeRef.current = isMock;
    }
  }, []);

  const cleanupTimers = () => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }
  };

  // Re-synchronize data on connection restore
  const resyncRestData = useCallback(async () => {
    try {
      const [queue, decisions, info] = await Promise.allSettled([
        api.getReviewQueue(),
        api.getDecisions(sessionId, 50),
        api.getSystemInfo(),
      ]);

      if (queue.status === 'fulfilled') {
        telemetryStore.setReviewQueue(queue.value);
      }
      if (decisions.status === 'fulfilled' && decisions.value.length > 0) {
        telemetryStore.setDecisions(decisions.value);
      }
      if (info.status === 'fulfilled') {
        telemetryStore.setSystemInfo(info.value);
      }
    } catch {}
  }, [sessionId]);

  // Dev-only Mock Stream Simulator (?mock=1)
  const startMockStream = useCallback(() => {
    let seq = 1000;
    let foreignY = 50;
    let legitY = 120;
    let legit2Y = 280;

    mockIntervalRef.current = window.setInterval(() => {
      seq += 1;
      const now = Date.now();

      // Advance simulated conveyor items (belt speed ~120 px/s -> ~4 px/frame at 30Hz)
      foreignY = (foreignY + 4) % 480;
      legitY = (legitY + 3.8) % 480;
      legit2Y = (legit2Y + 4.1) % 480;

      const ttiForeign = Math.max(0, Math.round(((250 - foreignY) / 120) * 1000));
      const atJetPos: [number, number] = [300 + (Math.sin(seq / 15) * 8), 250];

      // Simulated tracks
      const tracks: TrackData[] = [
        {
          id: 4,
          centroid: [298.4 + Math.sin(seq / 10) * 2, foreignY],
          velocity: [0.4, 120.0],
          class: 'foreign',
          confidence: 0.94,
          state: foreignY < 180 ? 'TRACKING' : (foreignY < 235 ? 'ASSESSING' : (foreignY < 255 ? 'INTERCEPTING' : 'VERIFYING')),
          bbox: [298.4 - 18, foreignY - 18, 36, 36],
        },
        {
          id: 7,
          centroid: [180.2, legitY],
          velocity: [0.0, 118.0],
          class: 'legitimate',
          confidence: 0.98,
          state: 'MONITORING',
          bbox: [180.2 - 22, legitY - 22, 44, 44],
        },
        {
          id: 9,
          centroid: [440.0, legit2Y],
          velocity: [0.2, 122.0],
          class: 'legitimate',
          confidence: 0.91,
          state: 'MONITORING',
          bbox: [440.0 - 20, legit2Y - 20, 40, 40],
        },
      ];

      const predictions: PredictionData[] = [
        {
          track_id: 4,
          tti_ms: foreignY <= 250 ? ttiForeign : null,
          crosses_zone: true,
          at_jet_position_px: atJetPos,
          uncertainty_px: 12 + (foreignY < 250 ? (250 - foreignY) * 0.08 : 4),
        },
      ];

      const isFiring = foreignY >= 244 && foreignY <= 252;
      const decisions: DecisionData[] = [];

      if (foreignY >= 235 && foreignY <= 245) {
        decisions.push({
          track_id: 4,
          action: 'intercept',
          tier: '1',
          state_from: 'ASSESSING',
          state_to: 'INTERCEPTING',
          confidence_before: 0.94,
          confidence_after: 0.94,
          reason: 'Tier 1 high-confidence foreign object on collision course with Shield Zone (conf >= 0.75, TTI >= 230ms)',
          t_ms: now,
        });
      }

      // Random compute timing oscillation
      const computeMs = Math.round((3.2 + Math.random() * 1.8) * 100) / 100;

      const mockMsg: TelemetryMessage = {
        type: 'telemetry',
        session_id: sessionId,
        seq,
        t_capture_ms: now,
        metrics: {
          fps: 30.0,
          compute_ms: computeMs,
          active_tracks_count: tracks.length,
          dropped_frames: 0,
        },
        pipeline_timings: {
          UndistortHomography: 0.0,
          ROIDownscale: 0.18,
          BackgroundSubtract: 2.35,
          Morphology: 0.24,
          Contours: 0.08,
          Tracker: 0.02,
          Predictor: 0.01,
        },
        tracks,
        predictions,
        decisions,
        actuator_state: {
          state: isFiring ? 'firing' : (foreignY > 252 && foreignY < 270 ? 'cooldown' : 'armed'),
          simulated: true,
          kill_switch: telemetryStore.getState().actuatorState.kill_switch,
          cooldown_remaining_ms: (foreignY > 252 && foreignY < 270) ? Math.round((270 - foreignY) * 20) : 0,
        },
      };

      telemetryStore.ingestTelemetry(mockMsg);
      telemetryStore.setConnectionState('live');
    }, 33);
  }, [sessionId]);

  // Real WebSocket Connector with Backoff + Jitter
  const connect = useCallback(() => {
    cleanupTimers();

    // If mock mode is active, do not connect real socket
    if (isMockModeRef.current) {
      startMockStream();
      return;
    }

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host || 'localhost:8000';
    const wsUrl = `${proto}//${host}/ws/sessions/${sessionId}/stream`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        attemptRef.current = 0;
        telemetryStore.setConnectionState('live');
        resyncRestData();
      };

      ws.onmessage = (event) => {
        try {
          const raw = JSON.parse(event.data);
          if (!raw) return;

          // Normalize message variants from backend worker
          let normalizedMsg: TelemetryMessage | null = null;

          if (raw.type === 'telemetry') {
            normalizedMsg = raw as TelemetryMessage;
          } else if (raw.type === 'frame' && raw.payload) {
            const p = raw.payload;
            const metrics = p.metrics || {};
            const stageTimings = metrics.stage_timings || {
              UndistortHomography: 0.0,
              ROIDownscale: 0.11,
              BackgroundSubtract: 2.50,
              Morphology: 0.27,
              Contours: 0.06,
              Tracker: 0.02,
              Predictor: 0.01,
            };

            normalizedMsg = {
              type: 'telemetry',
              session_id: raw.session_id || sessionId,
              seq: raw.seq || 0,
              t_capture_ms: raw.t_capture_ms || Date.now(),
              metrics: {
                fps: metrics.fps || 30.0,
                compute_ms: metrics.compute_ms || 3.5,
                active_tracks_count: metrics.active_tracks_count || (p.tracks ? p.tracks.length : 0),
                dropped_frames: metrics.dropped_frames || 0,
              },
              pipeline_timings: stageTimings,
              tracks: p.tracks || [],
              predictions: p.predictions || [],
              decisions: p.decisions || [],
              actuator_state: metrics.actuator_state || {
                state: 'armed',
                simulated: true,
                kill_switch: false,
              },
            };
          } else if (raw.type === 'actuator' && raw.payload) {
            // Actuator event update
            const curState = telemetryStore.getState().actuatorState;
            const snapshot = telemetryStore.getLatestFrameSnapshot();
            if (snapshot) {
              telemetryStore.ingestTelemetry({
                ...snapshot,
                actuator_state: {
                  ...curState,
                  state: raw.payload.state || 'firing',
                  simulated: true,
                },
              });
            }
          } else if (raw.type === 'review_item' && raw.payload) {
            // New human review item escalation
            const curQueue = telemetryStore.getState().reviewQueue;
            telemetryStore.setReviewQueue([raw.payload, ...curQueue]);
          }

          if (normalizedMsg) {
            telemetryStore.ingestTelemetry(normalizedMsg);
          }
        } catch (err) {
          console.warn('[ZoneShield WS] Frame dropped due to parsing error:', err);
        }
      };

      ws.onerror = () => {
        // Handled in onclose
      };

      ws.onclose = () => {
        wsRef.current = null;
        attemptRef.current += 1;

        // Exponential backoff with jitter: min(15, 1 * 1.5^attempt + rand(0, 1))
        const backoffBase = Math.min(15, Math.pow(1.5, attemptRef.current));
        const jitter = Math.random() * 0.8;
        const retryDelaySec = Math.max(1, Math.round(backoffBase + jitter));

        let remainingSec = retryDelaySec;
        telemetryStore.setConnectionState('reconnecting', {
          attempt: attemptRef.current,
          nextRetry: remainingSec,
        });

        countdownIntervalRef.current = window.setInterval(() => {
          remainingSec -= 1;
          if (remainingSec <= 0) {
            if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current);
          } else {
            telemetryStore.setConnectionState('reconnecting', {
              attempt: attemptRef.current,
              nextRetry: remainingSec,
            });
          }
        }, 1000);

        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, retryDelaySec * 1000);
      };
    } catch {
      // Reconnect fallback
      reconnectTimeoutRef.current = window.setTimeout(connect, 3000);
    }
  }, [sessionId, resyncRestData, startMockStream]);

  // Manual trigger to retry immediately
  const retryNow = useCallback(() => {
    cleanupTimers();
    attemptRef.current = 0;
    connect();
  }, [connect]);

  useEffect(() => {
    connect();

    return () => {
      cleanupTimers();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (mockIntervalRef.current) {
        clearInterval(mockIntervalRef.current);
        mockIntervalRef.current = null;
      }
    };
  }, [connect]);

  return { retryNow };
}
