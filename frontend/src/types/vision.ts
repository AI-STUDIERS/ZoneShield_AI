export type SourceType = 'webcam' | 'video_file' | 'websocket_stream' | 'synthetic_feed';

export interface BoundingBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Keypoint {
  x: number;
  y: number;
  confidence: number;
  part: string;
}

export interface SkeletonConnection {
  from: string;
  to: string;
  color?: string;
}

export interface Detection {
  id: string | number;
  class: string;
  confidence: number;
  bbox: BoundingBox;
  color: string;
  trackId?: number;
  velocity?: [number, number];
  keypoints?: Keypoint[];
  trajectory?: [number, number][];
  ttiMs?: number;
  isAnomaly?: boolean;
  maskPolygon?: [number, number][];
}

export interface TelemetryData {
  sourceFps: number;
  processedFps: number;
  totalLatencyMs: number;
  captureLatencyMs: number;
  modelLatencyMs: number;
  renderLatencyMs: number;
  activeModel: string;
  resolution: string;
  objectCounts: {
    total: number;
    persons: number;
    objects: number;
    anomalies: number;
  };
  droppedFrames: number;
  timestamp: number;
}

export interface PipelineLayers {
  boxes: boolean;
  labels: boolean;
  skeletons: boolean;
  trajectories: boolean;
  heatmaps: boolean;
  opticalFlow: boolean;
  masks: boolean;
  jetCone: boolean;
}

export interface PipelineParameters {
  confidenceThreshold: number; // 0.00 - 1.00
  nmsThreshold: number; // 0.00 - 1.00
  contrast: number; // 0.5 - 2.5
  brightness: number; // -100 - 100
  cannyLow: number; // 0 - 255
  cannyHigh: number; // 0 - 255
  blurKernel: number; // 0, 3, 5, 7, 9
  hsvMin: [number, number, number];
  hsvMax: [number, number, number];
  layers: PipelineLayers;
  preset: 'standard' | 'high_sensitivity' | 'edge_focus';
}

export interface DetectionEvent {
  id: string;
  timestamp: string;
  trackId: number | string;
  class: string;
  confidence: number;
  thumbnailUrl?: string;
  actionTaken?: string;
  isThreat?: boolean;
}
