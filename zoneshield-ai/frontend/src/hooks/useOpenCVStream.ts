import { useState, useEffect, useRef } from 'react';
import type { Detection, TelemetryData, SourceType, PipelineParameters } from '../types/vision';

// Standard 17-point COCO skeleton connections
export const SKELETON_BONES: [string, string][] = [
  ['nose', 'left_eye'], ['nose', 'right_eye'],
  ['left_eye', 'left_ear'], ['right_eye', 'right_ear'],
  ['left_shoulder', 'right_shoulder'],
  ['left_shoulder', 'left_elbow'], ['left_elbow', 'left_wrist'],
  ['right_shoulder', 'right_elbow'], ['right_elbow', 'right_wrist'],
  ['left_shoulder', 'left_hip'], ['right_shoulder', 'right_hip'],
  ['left_hip', 'right_hip'],
  ['left_hip', 'left_knee'], ['left_knee', 'left_ankle'],
  ['right_hip', 'right_knee'], ['right_knee', 'right_ankle']
];

export function useOpenCVStream(
  sourceType: SourceType,
  videoFile: File | null,
  params: PipelineParameters,
  isPlaying: boolean
) {
  const [telemetry, setTelemetry] = useState<TelemetryData>({
    sourceFps: 30,
    processedFps: 60,
    totalLatencyMs: 14.2,
    captureLatencyMs: 3.1,
    modelLatencyMs: 8.5,
    renderLatencyMs: 2.6,
    activeModel: 'YOLOv8x-Pose / TensorRT',
    resolution: '1280x720 @ 60Hz',
    objectCounts: { total: 0, persons: 0, objects: 0, anomalies: 0 },
    droppedFrames: 0,
    timestamp: Date.now()
  });

  const [detections, setDetections] = useState<Detection[]>([]);
  const [opticalFlowVectors, setOpticalFlowVectors] = useState<{ x: number; y: number; vx: number; vy: number }[]>([]);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const animFrameRef = useRef<number | null>(null);

  // Synthetic moving target states
  const syntheticTargetsRef = useRef([
    { id: 101, x: 220, y: 160, vx: 2.2, vy: 1.1, cls: 'person', conf: 0.94, color: '#06b6d4' },
    { id: 102, x: 580, y: 280, vx: -1.8, vy: 1.4, cls: 'threat_pest', conf: 0.89, color: '#ef4444' },
    { id: 103, x: 400, y: 380, vx: 1.2, vy: -1.0, cls: 'conveyor_component', conf: 0.92, color: '#10b981' },
    { id: 104, x: 740, y: 190, vx: -2.0, vy: -0.8, cls: 'anomaly_debris', conf: 0.82, color: '#f59e0b' }
  ]);

  // Optical flow grid initialization
  useEffect(() => {
    const vectors: { x: number; y: number; vx: number; vy: number }[] = [];
    for (let x = 60; x <= 1200; x += 90) {
      for (let y = 60; y <= 660; y += 90) {
        vectors.push({ x, y, vx: 0, vy: 0 });
      }
    }
    setOpticalFlowVectors(vectors);
  }, []);

  // Handle MediaStream / Webcam
  useEffect(() => {
    if (sourceType === 'webcam') {
      navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 } })
        .then((stream) => {
          mediaStreamRef.current = stream;
          if (videoRef.current) {
            videoRef.current.srcObject = stream;
            videoRef.current.play().catch(() => {});
          }
        })
        .catch((err) => {
          console.warn("Webcam access unavailable, falling back to simulated stream:", err);
        });

      return () => {
        if (mediaStreamRef.current) {
          mediaStreamRef.current.getTracks().forEach(t => t.stop());
          mediaStreamRef.current = null;
        }
      };
    } else if (sourceType === 'video_file' && videoFile) {
      const url = URL.createObjectURL(videoFile);
      if (videoRef.current) {
        videoRef.current.srcObject = null;
        videoRef.current.src = url;
        videoRef.current.loop = true;
        if (isPlaying) videoRef.current.play().catch(() => {});
      }
      return () => URL.revokeObjectURL(url);
    }
  }, [sourceType, videoFile]);

  // Handle WebSocket Connection
  useEffect(() => {
    if (sourceType === 'websocket_stream') {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host || 'localhost:8000';
      const ws = new WebSocket(`${proto}//${host}/ws/sessions/00000000-0000-0000-0000-000000000001/stream`);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'frame' && msg.payload) {
            const p = msg.payload;
            if (p.metrics) {
              setTelemetry(prev => ({
                ...prev,
                sourceFps: p.metrics.fps || 30,
                totalLatencyMs: p.metrics.compute_ms || 12.0,
                droppedFrames: p.metrics.dropped_frames || 0,
                timestamp: Date.now()
              }));
            }
          }
        } catch {}
      };

      return () => {
        ws.close();
      };
    }
  }, [sourceType]);

  // Simulation / Inference Loop (60 FPS)
  useEffect(() => {
    let frameCounter = 0;
    let fpsTimer = performance.now();

    const loop = (currentTime: number) => {
      if (!isPlaying) {
        animFrameRef.current = requestAnimationFrame(loop);
        return;
      }

      frameCounter++;
      if (currentTime - fpsTimer >= 500) {
        const measuredFps = Math.round((frameCounter * 1000) / (currentTime - fpsTimer));
        frameCounter = 0;
        fpsTimer = currentTime;
        setTelemetry(prev => ({ ...prev, processedFps: Math.min(60, measuredFps) }));
      }

      // Update synthetic targets
      const t = currentTime / 1000;
      const updatedTargets: Detection[] = syntheticTargetsRef.current.map((tgt, idx) => {
        let nx = tgt.x + tgt.vx * 1.5;
        let ny = tgt.y + tgt.vy * 1.5;

        // Bounce within 1280x720
        if (nx < 80 || nx > 1180) tgt.vx *= -1;
        if (ny < 80 || ny > 640) tgt.vy *= -1;

        nx = Math.max(80, Math.min(1180, nx));
        ny = Math.max(80, Math.min(640, ny));

        tgt.x = nx;
        tgt.y = ny;

        const isPerson = tgt.cls === 'person';
        const isAnomaly = tgt.cls.includes('anomaly') || tgt.cls.includes('threat');

        // Pose Keypoints generation for person
        let keypoints = undefined;
        if (isPerson) {
          const bob = Math.sin(t * 4 + idx) * 4;
          keypoints = [
            { x: nx, y: ny - 65 + bob, confidence: 0.95, part: 'nose' },
            { x: nx - 6, y: ny - 70 + bob, confidence: 0.93, part: 'left_eye' },
            { x: nx + 6, y: ny - 70 + bob, confidence: 0.93, part: 'right_eye' },
            { x: nx - 14, y: ny - 68 + bob, confidence: 0.88, part: 'left_ear' },
            { x: nx + 14, y: ny - 68 + bob, confidence: 0.88, part: 'right_ear' },
            { x: nx - 28, y: ny - 40 + bob, confidence: 0.92, part: 'left_shoulder' },
            { x: nx + 28, y: ny - 40 + bob, confidence: 0.92, part: 'right_shoulder' },
            { x: nx - 42, y: ny - 10 + Math.sin(t * 5) * 8, confidence: 0.89, part: 'left_elbow' },
            { x: nx + 42, y: ny - 10 - Math.sin(t * 5) * 8, confidence: 0.89, part: 'right_elbow' },
            { x: nx - 52, y: ny + 15 + Math.sin(t * 5) * 12, confidence: 0.86, part: 'left_wrist' },
            { x: nx + 52, y: ny + 15 - Math.sin(t * 5) * 12, confidence: 0.86, part: 'right_wrist' },
            { x: nx - 18, y: ny + 20, confidence: 0.91, part: 'left_hip' },
            { x: nx + 18, y: ny + 20, confidence: 0.91, part: 'right_hip' },
            { x: nx - 22, y: ny + 65 + Math.sin(t * 3) * 6, confidence: 0.88, part: 'left_knee' },
            { x: nx + 22, y: ny + 65 - Math.sin(t * 3) * 6, confidence: 0.88, part: 'right_knee' },
            { x: nx - 25, y: ny + 110 + Math.sin(t * 3) * 8, confidence: 0.84, part: 'left_ankle' },
            { x: nx + 25, y: ny + 110 - Math.sin(t * 3) * 8, confidence: 0.84, part: 'right_ankle' },
          ];
        }

        // Polygon mask for segmented object
        const maskPolygon: [number, number][] = [
          [nx - 45, ny - 35],
          [nx + 45, ny - 35],
          [nx + 55, ny + 35],
          [nx - 55, ny + 35],
        ];

        const trajectoryPoints: [number, number][] = [
          [nx - tgt.vx * 20, ny - tgt.vy * 20],
          [nx - tgt.vx * 10, ny - tgt.vy * 10],
          [nx, ny],
          [nx + tgt.vx * 15, ny + tgt.vy * 15],
          [nx + tgt.vx * 30, ny + tgt.vy * 30],
        ];

        return {
          id: tgt.id,
          class: tgt.cls,
          confidence: tgt.conf,
          bbox: {
            x: isPerson ? nx - 60 : nx - 40,
            y: isPerson ? ny - 80 : ny - 40,
            w: isPerson ? 120 : 80,
            h: isPerson ? 200 : 80
          },
          color: tgt.color,
          trackId: tgt.id,
          velocity: [tgt.vx * 30, tgt.vy * 30] as [number, number],
          keypoints,
          maskPolygon: !isPerson ? maskPolygon : undefined,
          trajectory: trajectoryPoints,
          ttiMs: isAnomaly ? Math.max(40, Math.round(180 - Math.sin(t * 2) * 90)) : undefined,
          isAnomaly
        };
      });

      // Filter by confidence threshold parameter
      const filtered = updatedTargets.filter(d => d.confidence >= params.confidenceThreshold);
      setDetections(filtered);

      // Update optical flow vectors with sine wave drift
      setOpticalFlowVectors(prev => prev.map((v, i) => ({
        ...v,
        vx: Math.cos(t * 2 + i * 0.2) * 14,
        vy: Math.sin(t * 2 + i * 0.2) * 14
      })));

      // Update counts
      const persons = filtered.filter(d => d.class === 'person').length;
      const anomalies = filtered.filter(d => d.isAnomaly).length;
      const objects = filtered.length - persons;

      setTelemetry(prev => ({
        ...prev,
        objectCounts: {
          total: filtered.length,
          persons,
          objects,
          anomalies
        },
        timestamp: Date.now()
      }));

      animFrameRef.current = requestAnimationFrame(loop);
    };

    animFrameRef.current = requestAnimationFrame(loop);
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [isPlaying, params.confidenceThreshold]);

  return {
    videoRef,
    detections,
    opticalFlowVectors,
    telemetry
  };
}
