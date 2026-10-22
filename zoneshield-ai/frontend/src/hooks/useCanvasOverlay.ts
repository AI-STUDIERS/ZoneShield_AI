import { useEffect, useRef, useState, useCallback } from 'react';
import type { Detection, PipelineParameters } from '../types/vision';
import { SKELETON_BONES } from './useOpenCVStream';

export function useCanvasOverlay(
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
  videoRef: React.RefObject<HTMLVideoElement | null>,
  detections: Detection[],
  opticalFlowVectors: { x: number; y: number; vx: number; vy: number }[],
  params: PipelineParameters,
  isWipeMode: boolean
) {
  // Pan and Zoom Matrix State
  const [zoom, setZoom] = useState(1.0);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const panStartRef = useRef({ x: 0, y: 0 });

  // Wipe Split Screen X position (in percent, 0 to 100)
  const [wipePercent, setWipePercent] = useState(50);
  const [isDraggingWipe, setIsDraggingWipe] = useState(false);

  // Zoom / Pan Mouse Handlers
  const handleWheel = useCallback((e: WheelEvent) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
    setZoom(prev => Math.min(4.0, Math.max(0.6, prev * zoomFactor)));
  }, []);

  const handleMouseDown = useCallback((e: MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const wipePixelX = (wipePercent / 100) * rect.width;

    // If clicking near wipe line in wipe mode, start dragging wipe
    if (isWipeMode && Math.abs(mouseX - wipePixelX) < 18) {
      setIsDraggingWipe(true);
      return;
    }

    // Otherwise start panning
    setIsPanning(true);
    panStartRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  }, [canvasRef, isWipeMode, wipePercent, pan]);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();

    if (isDraggingWipe) {
      const mouseX = e.clientX - rect.left;
      const pct = Math.max(5, Math.min(95, (mouseX / rect.width) * 100));
      setWipePercent(pct);
      return;
    }

    if (isPanning) {
      setPan({
        x: e.clientX - panStartRef.current.x,
        y: e.clientY - panStartRef.current.y
      });
    }
  }, [canvasRef, isDraggingWipe, isPanning]);

  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
    setIsDraggingWipe(false);
  }, []);

  const handleDoubleClick = useCallback(() => {
    setZoom(1.0);
    setPan({ x: 0, y: 0 });
  }, []);

  // Attach event listeners
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    canvas.addEventListener('wheel', handleWheel, { passive: false });
    canvas.addEventListener('mousedown', handleMouseDown);
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    canvas.addEventListener('dblclick', handleDoubleClick);

    return () => {
      canvas.removeEventListener('wheel', handleWheel);
      canvas.removeEventListener('mousedown', handleMouseDown);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      canvas.removeEventListener('dblclick', handleDoubleClick);
    };
  }, [canvasRef, handleWheel, handleMouseDown, handleMouseMove, handleMouseUp, handleDoubleClick]);

  // Main Render Loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;

    const render = () => {
      const w = canvas.width;
      const h = canvas.height;
      const video = videoRef.current;

      ctx.clearRect(0, 0, w, h);

      ctx.save();
      // Apply Matrix Transform (Pan & Zoom)
      ctx.translate(w / 2 + pan.x, h / 2 + pan.y);
      ctx.scale(zoom, zoom);
      ctx.translate(-w / 2, -h / 2);

      // 1. Draw Video Frame (or synthetic background if video empty)
      if (video && video.readyState >= 2) {
        ctx.drawImage(video, 0, 0, w, h);
      } else {
        // High-tech dark conveyor inspection bay background
        ctx.fillStyle = '#0a0f1d';
        ctx.fillRect(0, 0, w, h);

        // Moving tread texture
        const offset = (Date.now() / 18) % 36;
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.08)';
        ctx.lineWidth = 2;
        for (let y = offset; y < h; y += 36) {
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(w, y);
          ctx.stroke();
        }

        // Conveyor Belt Guide Rails
        ctx.fillStyle = '#1e293b';
        ctx.fillRect(0, 0, 24, h);
        ctx.fillRect(w - 24, 0, 24, h);

        // Laser Interceptor Gate Line
        ctx.strokeStyle = '#ef4444';
        ctx.lineWidth = 3;
        ctx.shadowColor = '#ef4444';
        ctx.shadowBlur = 12;
        ctx.beginPath();
        ctx.moveTo(80, h * 0.65);
        ctx.lineTo(w - 80, h * 0.65);
        ctx.stroke();
        ctx.shadowBlur = 0;
      }

      // If Wipe Split Screen Mode: create clipping region for processed annotations
      const wipeBoundaryX = (wipePercent / 100) * w;

      if (isWipeMode) {
        ctx.save();
        ctx.beginPath();
        ctx.rect(wipeBoundaryX, 0, w - wipeBoundaryX, h);
        ctx.clip();
      }

      // 2. Optical Flow Vector Layer
      if (params.layers.opticalFlow) {
        ctx.strokeStyle = '#06b6d4';
        ctx.lineWidth = 1.5;
        opticalFlowVectors.forEach(v => {
          ctx.beginPath();
          ctx.moveTo(v.x, v.y);
          ctx.lineTo(v.x + v.vx, v.y + v.vy);
          ctx.stroke();

          // Arrow head
          ctx.fillStyle = '#06b6d4';
          ctx.beginPath();
          ctx.arc(v.x + v.vx, v.y + v.vy, 2, 0, Math.PI * 2);
          ctx.fill();
        });
      }

      // 3. Heatmap Density Layer
      if (params.layers.heatmaps) {
        detections.forEach(d => {
          const cx = d.bbox.x + d.bbox.w / 2;
          const cy = d.bbox.y + d.bbox.h / 2;
          const radius = Math.max(d.bbox.w, d.bbox.h) * 0.9;
          const grad = ctx.createRadialGradient(cx, cy, 5, cx, cy, radius);
          grad.addColorStop(0, 'rgba(239, 68, 68, 0.45)');
          grad.addColorStop(0.5, 'rgba(245, 158, 11, 0.25)');
          grad.addColorStop(1, 'transparent');

          ctx.fillStyle = grad;
          ctx.beginPath();
          ctx.arc(cx, cy, radius, 0, Math.PI * 2);
          ctx.fill();
        });
      }

      // 4. Segmentation Masks
      if (params.layers.masks) {
        detections.forEach(d => {
          if (d.maskPolygon) {
            ctx.fillStyle = `${d.color}33`; // 20% opacity
            ctx.strokeStyle = d.color;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(d.maskPolygon[0][0], d.maskPolygon[0][1]);
            for (let i = 1; i < d.maskPolygon.length; i++) {
              ctx.lineTo(d.maskPolygon[i][0], d.maskPolygon[i][1]);
            }
            ctx.closePath();
            ctx.fill();
            ctx.stroke();
          }
        });
      }

      // 5. Pose Skeletons & Keypoints
      if (params.layers.skeletons) {
        detections.forEach(d => {
          if (d.keypoints && d.keypoints.length > 0) {
            const kpMap = new Map(d.keypoints.map(k => [k.part, k]));

            // Draw Bones
            ctx.strokeStyle = '#10b981';
            ctx.lineWidth = 3;
            SKELETON_BONES.forEach(([from, to]) => {
              const k1 = kpMap.get(from);
              const k2 = kpMap.get(to);
              if (k1 && k2 && k1.confidence > 0.6 && k2.confidence > 0.6) {
                ctx.beginPath();
                ctx.moveTo(k1.x, k1.y);
                ctx.lineTo(k2.x, k2.y);
                ctx.stroke();
              }
            });

            // Draw Keypoint Nodes
            d.keypoints.forEach(k => {
              if (k.confidence > 0.5) {
                ctx.fillStyle = k.confidence > 0.8 ? '#00f0ff' : '#f59e0b';
                ctx.beginPath();
                ctx.arc(k.x, k.y, 4, 0, Math.PI * 2);
                ctx.fill();
                ctx.strokeStyle = '#ffffff';
                ctx.lineWidth = 1;
                ctx.stroke();
              }
            });
          }
        });
      }

      // 6. Trajectory Breadcrumbs
      if (params.layers.trajectories) {
        detections.forEach(d => {
          if (d.trajectory && d.trajectory.length > 1) {
            ctx.strokeStyle = d.color;
            ctx.lineWidth = 2;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.moveTo(d.trajectory[0][0], d.trajectory[0][1]);
            for (let i = 1; i < d.trajectory.length; i++) {
              ctx.lineTo(d.trajectory[i][0], d.trajectory[i][1]);
            }
            ctx.stroke();
            ctx.setLineDash([]);
          }
        });
      }

      // 7. Bounding Boxes & Precision Reticles
      if (params.layers.boxes) {
        detections.forEach(d => {
          const { x, y, w, h } = d.bbox;

          // Corner Reticles
          const cornerLen = 14;
          ctx.strokeStyle = d.color;
          ctx.lineWidth = 2.5;

          // Top Left
          ctx.beginPath();
          ctx.moveTo(x, y + cornerLen);
          ctx.lineTo(x, y);
          ctx.lineTo(x + cornerLen, y);
          ctx.stroke();

          // Top Right
          ctx.beginPath();
          ctx.moveTo(x + w - cornerLen, y);
          ctx.lineTo(x + w, y);
          ctx.lineTo(x + w, y + cornerLen);
          ctx.stroke();

          // Bottom Left
          ctx.beginPath();
          ctx.moveTo(x, y + h - cornerLen);
          ctx.lineTo(x, y + h);
          ctx.lineTo(x + cornerLen, y + h);
          ctx.stroke();

          // Bottom Right
          ctx.beginPath();
          ctx.moveTo(x + w - cornerLen, y + h);
          ctx.lineTo(x + w, y + h);
          ctx.lineTo(x + w, y + h - cornerLen);
          ctx.stroke();

          // Subtle box fill
          ctx.fillStyle = `${d.color}18`;
          ctx.fillRect(x, y, w, h);

          // Class Label Badge
          if (params.layers.labels) {
            const labelText = `${d.class.toUpperCase()} [${Math.round(d.confidence * 100)}%]`;
            ctx.font = 'bold 11px "JetBrains Mono", monospace';
            const textWidth = ctx.measureText(labelText).width;

            ctx.fillStyle = 'rgba(9, 13, 22, 0.88)';
            ctx.fillRect(x, y - 22, textWidth + 12, 20);
            ctx.strokeStyle = d.color;
            ctx.lineWidth = 1;
            ctx.strokeRect(x, y - 22, textWidth + 12, 20);

            ctx.fillStyle = '#f8fafc';
            ctx.fillText(labelText, x + 6, y - 8);

            // TTI Tag if anomaly
            if (d.ttiMs) {
              const ttiText = `TTI: ${d.ttiMs}ms`;
              ctx.fillStyle = '#ef4444';
              ctx.fillRect(x + w - 75, y - 22, 75, 20);
              ctx.fillStyle = '#ffffff';
              ctx.font = 'bold 10px "JetBrains Mono", monospace';
              ctx.fillText(ttiText, x + w - 70, y - 8);
            }
          }
        });
      }

      if (isWipeMode) {
        ctx.restore(); // Restore clip region
      }

      // Draw Wipe Divider Bar in Wipe Mode
      if (isWipeMode) {
        ctx.strokeStyle = '#00f0ff';
        ctx.lineWidth = 2.5;
        ctx.shadowColor = '#00f0ff';
        ctx.shadowBlur = 10;
        ctx.beginPath();
        ctx.moveTo(wipeBoundaryX, 0);
        ctx.lineTo(wipeBoundaryX, h);
        ctx.stroke();
        ctx.shadowBlur = 0;

        // Wipe Drag Handle Icon
        ctx.fillStyle = '#00f0ff';
        ctx.beginPath();
        ctx.arc(wipeBoundaryX, h / 2, 14, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = '#050811';
        ctx.font = 'bold 10px "JetBrains Mono"';
        ctx.fillText('⬌', wipeBoundaryX - 6, h / 2 + 4);

        // Labels
        ctx.fillStyle = 'rgba(9, 13, 22, 0.8)';
        ctx.fillRect(wipeBoundaryX - 90, 16, 75, 22);
        ctx.fillStyle = '#94a3b8';
        ctx.font = '10px "JetBrains Mono"';
        ctx.fillText('RAW FEED', wipeBoundaryX - 80, 31);

        ctx.fillStyle = 'rgba(9, 13, 22, 0.8)';
        ctx.fillRect(wipeBoundaryX + 15, 16, 100, 22);
        ctx.fillStyle = '#00f0ff';
        ctx.fillText('OPENCV VISION', wipeBoundaryX + 25, 31);
      }

      ctx.restore();
      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [canvasRef, videoRef, detections, opticalFlowVectors, params, isWipeMode, wipePercent, zoom, pan]);

  return {
    zoom,
    pan,
    setZoom,
    setPan,
    wipePercent,
    setWipePercent,
    resetView: handleDoubleClick
  };
}
