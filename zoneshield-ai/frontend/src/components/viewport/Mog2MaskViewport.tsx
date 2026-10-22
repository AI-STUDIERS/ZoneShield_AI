import React, { useRef, useEffect } from 'react';
import { useTelemetryStore } from '../../store/useStore';
import { Eye, Info } from 'lucide-react';

export const Mog2MaskViewport: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const tracks = useTelemetryStore(state => state.tracks);
  const pipelineTimings = useTelemetryStore(state => state.pipelineTimings);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const rect = container.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const w = rect.width;
    const h = rect.height;

    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.save();
    ctx.scale(dpr, dpr);

    // High-contrast binary mask styling (pure black background, white blobs)
    ctx.fillStyle = '#05070d';
    ctx.fillRect(0, 0, w, h);

    const scaleX = w / 640;
    const scaleY = h / 480;

    // Render MOG2 segmented foreground blobs from track detections
    tracks.forEach(track => {
      const cx = track.centroid[0] * scaleX;
      const cy = track.centroid[1] * scaleY;
      const bw = (track.bbox ? track.bbox[2] : 36) * scaleX;
      const bh = (track.bbox ? track.bbox[3] : 36) * scaleY;

      // Draw white foreground mask blob with Gaussian morphological boundary
      const grad = ctx.createRadialGradient(cx, cy, 2, cx, cy, Math.max(bw, bh) * 0.6);
      grad.addColorStop(0, '#ffffff');
      grad.addColorStop(0.7, '#f1f5f9');
      grad.addColorStop(1, '#05070d');

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, cy, Math.max(bw, bh) * 0.6, 0, Math.PI * 2);
      ctx.fill();

      // Contour edge
      ctx.strokeStyle = '#00f2ff';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(cx, cy, Math.max(bw, bh) * 0.6, 0, Math.PI * 2);
      ctx.stroke();
    });

    ctx.restore();
  }, [tracks]);

  return (
    <div
      ref={containerRef}
      className="relative flex-1 w-full h-full min-h-[360px] overflow-hidden bg-[#05070d] rounded-lg border border-white/8 select-none flex flex-col"
    >
      <canvas ref={canvasRef} className="absolute inset-0" />

      {/* Mask Info Tag */}
      <div className="absolute top-3 left-3 flex items-center gap-2 px-3 py-1.5 rounded-lg bg-black/80 border border-white/10 backdrop-blur-md text-xs font-mono text-slate-300">
        <Eye className="w-4 h-4 text-cyan-400" />
        <span className="font-semibold text-white">OPENCV 5 MOG2 FOREGROUND MASK</span>
        <span className="text-slate-600">|</span>
        <span className="text-slate-400">
          History=50, VarThresh=16 ({pipelineTimings.BackgroundSubtract.toFixed(2)}ms)
        </span>
      </div>

      {tracks.length === 0 && (
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-slate-500 font-mono text-xs gap-2">
          <Info className="w-6 h-6 text-slate-600" />
          <span>AWAITING MOVING CONVEYOR TARGETS TO GENERATE MASK</span>
        </div>
      )}
    </div>
  );
};
