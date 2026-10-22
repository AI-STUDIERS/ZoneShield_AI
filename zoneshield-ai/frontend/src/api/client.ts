import type {
  DecisionData,
  ReviewItemData,
  SystemInfoData,
} from '../types/telemetry';

const API_BASE = '/api/v1';

export interface ManualFireResult {
  status: 'fired' | 'blocked';
  applied: boolean;
  blocked_by?: string;
  delay_ms?: number;
}

export interface KillSwitchResult {
  status: string;
  all_actuators_disabled: boolean;
  reason?: string;
}

export const api = {
  // Sessions
  async startSession(sessionId: string, videoFile?: string): Promise<{ status: string; session_id: string }> {
    const url = videoFile
      ? `${API_BASE}/sessions/${sessionId}/start?video_file=${encodeURIComponent(videoFile)}`
      : `${API_BASE}/sessions/${sessionId}/start`;
    const res = await fetch(url, { method: 'POST' });
    if (!res.ok) throw new Error(`Failed to start session: ${res.statusText}`);
    return res.json();
  },

  async pauseSession(sessionId: string): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/pause`, { method: 'POST' });
    if (!res.ok) throw new Error(`Failed to pause session: ${res.statusText}`);
    return res.json();
  },

  async resumeSession(sessionId: string): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/resume`, { method: 'POST' });
    if (!res.ok) throw new Error(`Failed to resume session: ${res.statusText}`);
    return res.json();
  },

  async stopSession(sessionId: string): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/stop`, { method: 'POST' });
    if (!res.ok) throw new Error(`Failed to stop session: ${res.statusText}`);
    return res.json();
  },

  // Decisions
  async getDecisions(sessionId: string, limit = 50): Promise<DecisionData[]> {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/decisions?limit=${limit}`);
    if (!res.ok) return [];
    return res.json();
  },

  // Review Queue
  async getReviewQueue(): Promise<ReviewItemData[]> {
    const res = await fetch(`${API_BASE}/review-queue`);
    if (!res.ok) return [];
    const items = await res.json();
    return items.map((item: any) => ({
      ...item,
      evidence_ids: typeof item.evidence_ids === 'string' ? JSON.parse(item.evidence_ids) : (item.evidence_ids || []),
    }));
  },

  async resolveReview(
    id: string,
    status: 'APPROVED' | 'DISMISSED' | 'MORE_EVIDENCE',
    operator = 'Operator-1',
    reason = 'Manual review validation'
  ): Promise<{ status: string; id: string; resolution: string }> {
    const res = await fetch(`${API_BASE}/review/${id}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        status: status.toLowerCase(),
        operator,
        reason,
      }),
    });
    if (!res.ok) throw new Error(`Failed to resolve review item: ${res.statusText}`);
    return res.json();
  },

  // Actuator & Safety Controls
  async manualFire(sessionId: string, targetX = 300.0, targetY = 250.0, reason = 'Operator manual fire test'): Promise<ManualFireResult> {
    const res = await fetch(`${API_BASE}/actuator/manual-fire`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        target_x: targetX,
        target_y: targetY,
        reason,
      }),
    });
    if (!res.ok) throw new Error(`Manual fire failed: ${res.statusText}`);
    return res.json();
  },

  async engageKillSwitch(reason = 'Emergency stop invoked by operator'): Promise<KillSwitchResult> {
    const res = await fetch(`${API_BASE}/system/kill-switch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason }),
    });
    if (!res.ok) throw new Error(`Kill switch invocation failed: ${res.statusText}`);
    return res.json();
  },

  async resetKillSwitch(): Promise<{ status: string; actuators_enabled: boolean }> {
    const res = await fetch(`${API_BASE}/system/kill-switch/reset`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(`Kill switch reset failed: ${res.statusText}`);
    return res.json();
  },

  // Diagnostics & Info
  async getSystemInfo(): Promise<SystemInfoData> {
    const res = await fetch(`${API_BASE}/system/info`);
    if (!res.ok) throw new Error(`Failed to fetch system info: ${res.statusText}`);
    return res.json();
  },

  async getMetrics(): Promise<string> {
    const res = await fetch(`${API_BASE}/metrics`);
    if (!res.ok) throw new Error(`Failed to fetch metrics: ${res.statusText}`);
    return res.text();
  },

  // Media & Video Datasets
  async getVideos(): Promise<Array<{ name: string; filename: string; size_kb: number; is_image?: boolean; media_type?: 'image' | 'video' }>> {
    const res = await fetch(`${API_BASE}/videos`);
    if (!res.ok) return [];
    return res.json();
  },

  async uploadMedia(file: File): Promise<{ status: string; filename: string; is_image: boolean; size_kb: number; media_type: 'image' | 'video' }> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Upload failed');
    }
    return res.json();
  },
};
