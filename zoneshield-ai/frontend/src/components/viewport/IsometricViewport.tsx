import React, { useRef, useEffect, useState } from 'react';
import { telemetryStore } from '../../store/telemetryStore';
import { Rotate3D, ZoomIn, ZoomOut, RefreshCw } from 'lucide-react';
import type { TrackData } from '../../types/telemetry';

export const IsometricViewport: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const [pitch, setPitch] = useState(55); // Degrees tilt
  const [yaw, setYaw] = useState(45); // Degrees rotation
  const [zoom, setZoom] = useState(1.0);
  const isDraggingRef = useRef(false);
  const lastMouseRef = useRef({ x: 0, y: 0 });

  // Mouse handlers for 3D orbit
  const handleMouseDown = (e: React.MouseEvent) => {
    isDraggingRef.current = true;
    lastMouseRef.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDraggingRef.current) return;
    const dx = e.clientX - lastMouseRef.current.x;
    const dy = e.clientY - lastMouseRef.current.y;
    lastMouseRef.current = { x: e.clientX, y: e.clientY };

    setYaw(prev => (prev + dx * 0.5) % 360);
    setPitch(prev => Math.min(85, Math.max(20, prev - dy * 0.5)));
  };

  const handleMouseUp = () => {
    isDraggingRef.current = false;
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.08 : 0.92;
    setZoom(prev => Math.min(2.5, Math.max(0.6, prev * factor)));
  };

  const resetCamera = () => {
    setPitch(55);
    setYaw(45);
    setZoom(1.0);
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    let animId: number;

    const render = () => {
      const rect = container.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const w = rect.width;
      const h = rect.height;

      if (canvas.width !== Math.floor(w * dpr) || canvas.height !== Math.floor(h * dpr)) {
        canvas.width = Math.floor(w * dpr);
        canvas.height = Math.floor(h * dpr);
        canvas.style.width = `${w}px`;
        canvas.style.height = `${h}px`;
      }

      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      ctx.save();
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, w, h);

      // Deep dark background
      ctx.fillStyle = '#05070d';
      ctx.fillRect(0, 0, w, h);

      const radPitch = (pitch * Math.PI) / 180;
      const radYaw = (yaw * Math.PI) / 180;

      // Project 3D point (x, y on belt, z altitude) to 2D screen
      const project = (x: number, y: number, z: number): [number, number] => {
        // Center belt at origin
        const cx = x - 320;
        const cy = y - 240;
        const cz = z;

        // Yaw rotation around Z axis
        const x1 = cx * Math.cos(radYaw) - cy * Math.sin(radYaw);
        const y1 = cx * Math.sin(radYaw) + cy * Math.cos(radYaw);

        // Pitch rotation around X axis
        const x2 = x1;
        const y2 = y1 * Math.cos(radPitch) - cz * Math.sin(radPitch);

        // Scale and translate to center of viewport
        const screenX = w / 2 + x2 * zoom * 0.95;
        const screenY = h / 2 + y2 * zoom * 0.95;
        return [screenX, screenY];
      };

      // 1. Draw 3D Conveyor Deck (640mm x 480mm)
      const p00 = project(0, 0, 0);
      const p10 = project(640, 0, 0);
      const p11 = project(640, 480, 0);
      const p01 = project(0, 480, 0);

      // Belt plane gradient fill
      const beltGrad = ctx.createLinearGradient(p00[0], p00[1], p01[0], p01[1]);
      beltGrad.addColorStop(0, '#0a0f1d');
      beltGrad.addColorStop(1, '#0f172a');
      ctx.fillStyle = beltGrad;
      ctx.beginPath();
      ctx.moveTo(p00[0], p00[1]);
      ctx.lineTo(p10[0], p10[1]);
      ctx.lineTo(p11[0], p11[1]);
      ctx.lineTo(p01[0], p01[1]);
      ctx.closePath();
      ctx.fill();

      // Belt plane outline
      ctx.strokeStyle = 'rgba(0, 242, 255, 0.35)';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Conveyor Grid Ribs
      ctx.strokeStyle = 'rgba(0, 242, 255, 0.08)';
      ctx.lineWidth = 1;
      for (let y = 0; y <= 480; y += 60) {
        const left = project(0, y, 0);
        const right = project(640, y, 0);
        ctx.beginPath();
        ctx.moveTo(left[0], left[1]);
        ctx.lineTo(right[0], right[1]);
        ctx.stroke();
      }

      // 2. Guide Rails (extruded extruded height = 24mm)
      const railH = 24;
      const leftRailBottom0 = project(0, 0, 0);
      const leftRailBottom1 = project(0, 480, 0);
      const leftRailTop0 = project(0, 0, railH);
      const leftRailTop1 = project(0, 480, railH);

      ctx.fillStyle = 'rgba(30, 41, 59, 0.8)';
      ctx.beginPath();
      ctx.moveTo(leftRailBottom0[0], leftRailBottom0[1]);
      ctx.lineTo(leftRailBottom1[0], leftRailBottom1[1]);
      ctx.lineTo(leftRailTop1[0], leftRailTop1[1]);
      ctx.lineTo(leftRailTop0[0], leftRailTop0[1]);
      ctx.closePath();
      ctx.fill();
      ctx.strokeStyle = 'rgba(0, 242, 255, 0.3)';
      ctx.stroke();

      // 3. 3D Jet Cone Volume (centered at x=300mm, y=250mm, apex at z=80mm)
      const jetApex = project(300, 250, 90);
      const coneLeft = project(260, 250, 0);
      const coneRight = project(340, 250, 0);

      // Radial cone volume fill
      ctx.fillStyle = 'rgba(0, 242, 255, 0.12)';
      ctx.beginPath();
      ctx.moveTo(jetApex[0], jetApex[1]);
      ctx.lineTo(coneLeft[0], coneLeft[1]);
      ctx.lineTo(coneRight[0], coneRight[1]);
      ctx.closePath();
      ctx.fill();

      ctx.strokeStyle = 'rgba(0, 242, 255, 0.45)';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // 4. Extruded 3D Track Markers
      const frame = telemetryStore.getLatestFrameSnapshot();
      const tracks: TrackData[] = frame?.tracks || [];

      tracks.forEach(track => {
        const tx = track.centroid[0];
        const ty = track.centroid[1];
        const isForeign = track.class === 'foreign';
        const color = isForeign ? '#ef4444' : '#22c55e';

        const ground = project(tx, ty, 0);
        const top = project(tx, ty, 20);

        // Ground drop shadow
        ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
        ctx.beginPath();
        ctx.ellipse(ground[0], ground[1], 12 * zoom, 6 * zoom, 0, 0, Math.PI * 2);
        ctx.fill();

        // Extruded elevation stalk
        ctx.strokeStyle = `${color}88`;
        ctx.lineWidth = 2;
        ctx.setLineDash([2, 2]);
        ctx.beginPath();
        ctx.moveTo(ground[0], ground[1]);
        ctx.lineTo(top[0], top[1]);
        ctx.stroke();
        ctx.setLineDash([]);

        // Extruded 3D Cuboid / Cylinder Marker
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(top[0], top[1], 8 * zoom, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Label Tag
        ctx.fillStyle = 'rgba(5, 7, 13, 0.85)';
        ctx.fillRect(top[0] + 12, top[1] - 14, 80, 16);
        ctx.strokeStyle = color;
        ctx.strokeRect(top[0] + 12, top[1] - 14, 80, 16);

        ctx.fillStyle = '#f8fafc';
        ctx.font = 'bold 9px "JetBrains Mono"';
        ctx.fillText(`#${track.id} ${track.class.toUpperCase()}`, top[0] + 16, top[1] - 3);
      });

      ctx.restore();
      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [pitch, yaw, zoom]);

  return (
    <div
      ref={containerRef}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onWheel={handleWheel}
      className="relative flex-1 w-full h-full min-h-[360px] overflow-hidden bg-[#05070d] rounded-lg border border-white/8 select-none cursor-grab active:cursor-grabbing"
    >
      <canvas ref={canvasRef} className="absolute inset-0" />

      {/* Floating 3D Camera Controls */}
      <div className="absolute bottom-3 left-3 flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-slate-900/90 border border-white/10 backdrop-blur-md text-xs font-mono text-slate-300">
        <div className="flex items-center gap-1 text-[11px] text-cyan-400">
          <Rotate3D className="w-3.5 h-3.5" />
          <span>ORBIT CAMERA</span>
        </div>
        <span className="text-slate-600">|</span>
        <button
          onClick={() => setZoom(prev => Math.min(2.5, prev * 1.15))}
          title="Zoom In"
          className="p-1 hover:text-cyan-300"
        >
          <ZoomIn className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => setZoom(prev => Math.max(0.6, prev * 0.85))}
          title="Zoom Out"
          className="p-1 hover:text-cyan-300"
        >
          <ZoomOut className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={resetCamera}
          title="Reset Camera Orientation"
          className="p-1 hover:text-cyan-300"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
        <span className="text-[10px] text-slate-500 ml-1">
          {Math.round(yaw)}° / {Math.round(pitch)}° ({Math.round(zoom * 100)}%)
        </span>
      </div>
    </div>
  );
};
