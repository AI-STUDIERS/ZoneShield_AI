import React, { useRef, useEffect } from 'react';
import { useTelemetryStore } from '../../store/useStore';
import { telemetryStore, type ActuatorBurst } from '../../store/telemetryStore';
import type { TrackData, PredictionData } from '../../types/telemetry';

export const CanvasViewport: React.FC = () => {
  const staticCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const dynamicCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const connectionState = useTelemetryStore(state => state.connectionState);
  const layers = useTelemetryStore(state => state.layers);
  const highlightedTrackId = useTelemetryStore(state => state.highlightedTrackId);

  // Position interpolation & track history buffers
  const trackHistoriesRef = useRef<Map<number, [number, number][]>>(new Map());
  const interpPositionsRef = useRef<Map<number, { current: [number, number]; target: [number, number] }>>(new Map());

  // 1. Static Canvas Rendering (tactical grid, rails, jet line at y=250, shield zone, mm scale)
  useEffect(() => {
    const canvas = staticCanvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const renderStatic = () => {
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
      ctx.scale(dpr, dpr);

      // Deep dark tactical background
      ctx.fillStyle = '#05070d';
      ctx.fillRect(0, 0, w, h);

      if (!layers.sensorGrid) return;

      // Coordinate scaling: map conveyor world (640 x 480 mm) to canvas w x h
      const scaleX = w / 640;
      const scaleY = h / 480;

      // Faint Tactical Grid (every 40mm)
      ctx.strokeStyle = 'rgba(0, 242, 255, 0.05)';
      ctx.lineWidth = 1;
      for (let x = 0; x <= 640; x += 40) {
        ctx.beginPath();
        ctx.moveTo(x * scaleX, 0);
        ctx.lineTo(x * scaleX, h);
        ctx.stroke();
      }
      for (let y = 0; y <= 480; y += 40) {
        ctx.beginPath();
        ctx.moveTo(0, y * scaleY);
        ctx.lineTo(w, y * scaleY);
        ctx.stroke();
      }

      // Conveyor Rails (guide rails on left and right)
      ctx.fillStyle = 'rgba(15, 23, 42, 0.7)';
      ctx.fillRect(0, 0, 28 * scaleX, h);
      ctx.fillRect(w - 28 * scaleX, 0, 28 * scaleX, h);

      ctx.strokeStyle = 'rgba(0, 242, 255, 0.18)';
      ctx.lineWidth = 1.5;
      ctx.strokeRect(0, 0, 28 * scaleX, h);
      ctx.strokeRect(w - 28 * scaleX, 0, 28 * scaleX, h);

      // Belt direction chevron arrows
      ctx.strokeStyle = 'rgba(0, 242, 255, 0.12)';
      ctx.lineWidth = 2;
      [80, 180, 280, 380].forEach(cy => {
        const y = cy * scaleY;
        const cx = w / 2;
        ctx.beginPath();
        ctx.moveTo(cx - 30, y - 8);
        ctx.lineTo(cx, y + 8);
        ctx.lineTo(cx + 30, y - 8);
        ctx.stroke();
      });

      // Jet Line at y = 250 mm
      const jetY = 250 * scaleY;
      ctx.strokeStyle = 'rgba(0, 242, 255, 0.45)';
      ctx.lineWidth = 2;
      ctx.setLineDash([8, 6]);
      ctx.beginPath();
      ctx.moveTo(28 * scaleX, jetY);
      ctx.lineTo(w - 28 * scaleX, jetY);
      ctx.stroke();
      ctx.setLineDash([]);

      // Interceptor Air-Jet Orifice Marker (center at x=300mm)
      const jetX = 300 * scaleX;
      ctx.fillStyle = '#00f2ff';
      ctx.beginPath();
      ctx.arc(jetX, jetY, 5, 0, Math.PI * 2);
      ctx.fill();

      // Jet Line Micro-label
      ctx.font = 'bold 10px "JetBrains Mono", monospace';
      ctx.fillStyle = '#00f2ff';
      ctx.fillText('JET INTERCEPT LINE (y = 250 mm)', 36 * scaleX, jetY - 6);

      // Jet Dispersion Cone Envelope (G2: 260 - 340 mm)
      if (layers.jetEnvelope) {
        const coneLeft = 260 * scaleX;
        const coneRight = 340 * scaleX;
        ctx.fillStyle = 'rgba(0, 242, 255, 0.04)';
        ctx.fillRect(coneLeft, jetY - 30 * scaleY, coneRight - coneLeft, 60 * scaleY);
        ctx.strokeStyle = 'rgba(0, 242, 255, 0.25)';
        ctx.strokeRect(coneLeft, jetY - 30 * scaleY, coneRight - coneLeft, 60 * scaleY);

        ctx.font = '9px "JetBrains Mono", monospace';
        ctx.fillStyle = 'rgba(0, 242, 255, 0.6)';
        ctx.fillText('G2 CONE (260-340mm)', coneLeft + 4, jetY + 18 * scaleY);
      }

      // Shield Zone at bottom (y >= 340 mm)
      const shieldY = 340 * scaleY;
      const grad = ctx.createLinearGradient(0, shieldY, 0, h);
      grad.addColorStop(0, 'rgba(239, 68, 68, 0.08)');
      grad.addColorStop(1, 'rgba(239, 68, 68, 0.22)');
      ctx.fillStyle = grad;
      ctx.fillRect(28 * scaleX, shieldY, w - 56 * scaleX, h - shieldY);

      ctx.strokeStyle = 'rgba(239, 68, 68, 0.55)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(28 * scaleX, shieldY);
      ctx.lineTo(w - 28 * scaleX, shieldY);
      ctx.stroke();

      ctx.font = 'bold 10px "JetBrains Mono", monospace';
      ctx.fillStyle = '#ef4444';
      ctx.fillText('CRITICAL SHIELD ZONE (BREACH = CONTAMINATION)', 36 * scaleX, shieldY + 16);

      // Corner Crosshair Reticles
      const reticleSize = 16;
      ctx.strokeStyle = 'rgba(0, 242, 255, 0.4)';
      ctx.lineWidth = 1.5;

      // Top Left
      ctx.beginPath();
      ctx.moveTo(10, 10 + reticleSize);
      ctx.lineTo(10, 10);
      ctx.lineTo(10 + reticleSize, 10);
      ctx.stroke();

      // Top Right
      ctx.beginPath();
      ctx.moveTo(w - 10 - reticleSize, 10);
      ctx.lineTo(w - 10, 10);
      ctx.lineTo(w - 10, 10 + reticleSize);
      ctx.stroke();

      // Millimeter Scale along edges
      ctx.fillStyle = 'rgba(148, 163, 184, 0.4)';
      ctx.font = '8px "JetBrains Mono", monospace';
      for (let x = 60; x < 600; x += 100) {
        ctx.fillText(`${x}mm`, x * scaleX - 10, 16);
      }
      for (let y = 60; y < 440; y += 80) {
        ctx.fillText(`${y}mm`, 6, y * scaleY + 3);
      }

      // Subtle Perspective Vignette
      const vig = ctx.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.4, w / 2, h / 2, Math.max(w, h) * 0.75);
      vig.addColorStop(0, 'transparent');
      vig.addColorStop(1, 'rgba(5, 7, 13, 0.65)');
      ctx.fillStyle = vig;
      ctx.fillRect(0, 0, w, h);
    };

    renderStatic();

    const ro = new ResizeObserver(() => renderStatic());
    ro.observe(container);
    return () => ro.disconnect();
  }, [layers]);

  // 2. Dynamic Canvas 60 FPS Render Loop (requestAnimationFrame)
  useEffect(() => {
    const canvas = dynamicCanvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    let animId: number;
    let scanAngle = 0;

    const renderDynamic = () => {
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

      const scaleX = w / 640;
      const scaleY = h / 480;

      // Read latest frame snapshot synchronously from transient memory
      const frame = telemetryStore.getLatestFrameSnapshot();
      const tracks: TrackData[] = frame?.tracks || [];
      const predictions: PredictionData[] = frame?.predictions || [];
      const bursts: ActuatorBurst[] = telemetryStore.getState().bursts || [];
      const predMap = new Map<number, PredictionData>(predictions.map(p => [p.track_id, p]));

      const isOfflineOrEmpty = tracks.length === 0;

      // Idle / Awaiting Feed State: animated scanning sweep + diagnostic waveform
      if (isOfflineOrEmpty) {
        scanAngle = (scanAngle + 0.02) % (Math.PI * 2);
        const cx = w / 2;
        const cy = h / 2;
        const radius = Math.min(w, h) * 0.28;

        // Radar scanning sweep circle
        ctx.strokeStyle = 'rgba(0, 242, 255, 0.15)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(cx, cy, radius * 0.5, 0, Math.PI * 2);
        ctx.stroke();

        // Rotating beam
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(scanAngle);
        const beamGrad = ctx.createRadialGradient(0, 0, 0, 0, 0, radius);
        beamGrad.addColorStop(0, 'rgba(0, 242, 255, 0.25)');
        beamGrad.addColorStop(1, 'transparent');
        ctx.fillStyle = beamGrad;
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.arc(0, 0, radius, 0, 0.45);
        ctx.closePath();
        ctx.fill();
        ctx.restore();

        // Subtle diagnostic waveform
        ctx.strokeStyle = 'rgba(0, 242, 255, 0.35)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        for (let x = cx - radius; x <= cx + radius; x += 4) {
          const t = Date.now() / 300 + x * 0.03;
          const y = cy + Math.sin(t) * 12 * Math.exp(-Math.pow((x - cx) / (radius * 0.8), 2));
          if (x === cx - radius) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();

        // Status text
        ctx.font = 'bold 12px "JetBrains Mono", monospace';
        ctx.fillStyle = '#94a3b8';
        ctx.textAlign = 'center';
        ctx.fillText('AWAITING FEED — PRESS START BELT', cx, cy + radius + 32);
        ctx.font = '10px "JetBrains Mono", monospace';
        ctx.fillStyle = '#64748b';
        ctx.fillText('DIGITAL TWIN INSPECTION BAY ACTIVE', cx, cy + radius + 48);
        ctx.textAlign = 'left';
      }

      // Smooth Position Interpolation between frames
      tracks.forEach(track => {
        const targetX = track.centroid[0] * scaleX;
        const targetY = track.centroid[1] * scaleY;
        let interp = interpPositionsRef.current.get(track.id);

        if (!interp) {
          interp = { current: [targetX, targetY], target: [targetX, targetY] };
          interpPositionsRef.current.set(track.id, interp);
        } else {
          interp.target = [targetX, targetY];
          // Linear interpolation (alpha 0.35 for 60 FPS smoothness)
          interp.current[0] += (interp.target[0] - interp.current[0]) * 0.35;
          interp.current[1] += (interp.target[1] - interp.current[1]) * 0.35;
        }

        // Update trajectory history
        let hist = trackHistoriesRef.current.get(track.id);
        if (!hist) {
          hist = [];
          trackHistoriesRef.current.set(track.id, hist);
        }
        hist.push([interp.current[0], interp.current[1]]);
        if (hist.length > 30) hist.shift(); // ~1 second history

        const [currX, currY] = interp.current;
        const pred = predMap.get(track.id);
        const isForeign = track.class === 'foreign';
        const isHighlighted = highlightedTrackId === track.id;

        // State Color Assignment
        let stateColor = '#64748b'; // MONITORING
        if (track.state === 'TRACKING') stateColor = '#00f2ff';
        else if (track.state === 'ASSESSING') stateColor = '#3b82f6';
        else if (track.state === 'GATHERING_EVIDENCE') stateColor = '#f59e0b';
        else if (track.state === 'AWAITING_HUMAN') stateColor = '#ff2e97';
        else if (track.state === 'INTERCEPTING') stateColor = '#ef4444';
        else if (track.state === 'VERIFYING') stateColor = '#22c55e';
        else if (isForeign) stateColor = '#ef4444';
        else stateColor = '#22c55e';

        // 1. Fading Trajectory Ribbon
        if (layers.trajectories && hist.length > 1) {
          for (let i = 1; i < hist.length; i++) {
            const alpha = (i / hist.length) * 0.4;
            ctx.strokeStyle = stateColor;
            ctx.globalAlpha = alpha;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(hist[i - 1][0], hist[i - 1][1]);
            ctx.lineTo(hist[i][0], hist[i][1]);
            ctx.stroke();
          }
          ctx.globalAlpha = 1.0;
        }

        // 2. Velocity Vector Arrow
        const vx = (track.velocity[0] || 0) * scaleX * 0.25;
        const vy = (track.velocity[1] || 120) * scaleY * 0.25;
        ctx.strokeStyle = stateColor;
        ctx.lineWidth = 1.8;
        ctx.beginPath();
        ctx.moveTo(currX, currY);
        ctx.lineTo(currX + vx, currY + vy);
        ctx.stroke();

        // 3. Predicted Path Spline & Uncertainty Cone
        if (pred && pred.at_jet_position_px) {
          const jetX = pred.at_jet_position_px[0] * scaleX;
          const jetY = pred.at_jet_position_px[1] * scaleY;
          const uncertainty = (pred.uncertainty_px || 16) * scaleX;

          // Uncertainty Cone Widening with Distance
          if (layers.uncertaintyCone && currY < jetY) {
            ctx.fillStyle = `${stateColor}15`;
            ctx.beginPath();
            ctx.moveTo(currX, currY);
            ctx.lineTo(jetX - uncertainty, jetY);
            ctx.lineTo(jetX + uncertainty, jetY);
            ctx.closePath();
            ctx.fill();

            ctx.strokeStyle = `${stateColor}35`;
            ctx.lineWidth = 1;
            ctx.stroke();
          }

          // Dashed Predicted Spline to Jet Line
          ctx.strokeStyle = stateColor;
          ctx.lineWidth = 1.5;
          ctx.setLineDash([4, 4]);
          ctx.beginPath();
          ctx.moveTo(currX, currY);
          ctx.quadraticCurveTo((currX + jetX) / 2, (currY + jetY) / 2, jetX, jetY);
          ctx.stroke();
          ctx.setLineDash([]);
        }

        // 4. Tactical Bounding Box with Corner Brackets
        const bw = (track.bbox ? track.bbox[2] : 36) * scaleX;
        const bh = (track.bbox ? track.bbox[3] : 36) * scaleY;
        const bx = currX - bw / 2;
        const by = currY - bh / 2;
        const cornerLen = Math.min(10, bw / 3);

        ctx.strokeStyle = isHighlighted ? '#ff2e97' : stateColor;
        ctx.lineWidth = isHighlighted ? 3 : 2;

        // Draw 4 corner brackets
        // Top-left
        ctx.beginPath();
        ctx.moveTo(bx, by + cornerLen);
        ctx.lineTo(bx, by);
        ctx.lineTo(bx + cornerLen, by);
        ctx.stroke();

        // Top-right
        ctx.beginPath();
        ctx.moveTo(bx + bw - cornerLen, by);
        ctx.lineTo(bx + bw, by);
        ctx.lineTo(bx + bw, by + cornerLen);
        ctx.stroke();

        // Bottom-left
        ctx.beginPath();
        ctx.moveTo(bx, by + bh - cornerLen);
        ctx.lineTo(bx, by + bh);
        ctx.lineTo(bx + cornerLen, by + bh);
        ctx.stroke();

        // Bottom-right
        ctx.beginPath();
        ctx.moveTo(bx + bw - cornerLen, by + bh);
        ctx.lineTo(bx + bw, by + bh);
        ctx.lineTo(bx + bw, by + bh - cornerLen);
        ctx.stroke();

        // Subtle box tint
        ctx.fillStyle = `${stateColor}18`;
        ctx.fillRect(bx, by, bw, bh);

        // 5. Track Label Chip: #id CLASS CONF%
        const label = `#${track.id} ${track.class.toUpperCase()} ${(track.confidence * 100).toFixed(1)}%`;
        ctx.font = 'bold 10px "JetBrains Mono", monospace';
        const textWidth = ctx.measureText(label).width;

        ctx.fillStyle = 'rgba(5, 7, 13, 0.9)';
        ctx.fillRect(bx, by - 20, textWidth + 10, 18);
        ctx.strokeStyle = stateColor;
        ctx.lineWidth = 1;
        ctx.strokeRect(bx, by - 20, textWidth + 10, 18);

        ctx.fillStyle = '#f8fafc';
        ctx.fillText(label, bx + 5, by - 7);

        // 6. TTI Countdown Chip (Amber < 400ms, Red < 230ms matching G1)
        if (pred?.tti_ms !== null && pred?.tti_ms !== undefined) {
          const tti = Math.round(pred.tti_ms);
          let ttiBg = '#3b82f6';
          if (tti < 230) ttiBg = '#ef4444'; // Red < G1 threshold
          else if (tti < 400) ttiBg = '#f59e0b'; // Amber < 400ms

          const ttiText = `TTI: ${tti}ms`;
          const ttiWidth = ctx.measureText(ttiText).width;

          ctx.fillStyle = ttiBg;
          ctx.fillRect(bx + bw - ttiWidth - 8, by + bh + 4, ttiWidth + 8, 16);
          ctx.fillStyle = '#ffffff';
          ctx.font = 'bold 9px "JetBrains Mono", monospace';
          ctx.fillText(ttiText, bx + bw - ttiWidth - 4, by + bh + 16);
        }

        // 7. Track State Indicator Dot / Ring
        if (track.state === 'AWAITING_HUMAN') {
          // Pulsing magenta ring
          const ringPulse = 18 + Math.sin(Date.now() / 150) * 4;
          ctx.strokeStyle = '#ff2e97';
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(currX, currY, ringPulse, 0, Math.PI * 2);
          ctx.stroke();
        } else if (track.state === 'VERIFYING') {
          // Green verification tick
          ctx.fillStyle = '#22c55e';
          ctx.font = 'bold 12px "JetBrains Mono"';
          ctx.fillText('✔ DEFLECTED', bx + bw + 6, currY);
        }
      });

      // 8. Simulated Jet Burst Animation
      const now = Date.now();
      bursts.forEach(burst => {
        const age = now - burst.timestamp;
        if (age < 600) {
          const burstProgress = age / 600;
          const bx = burst.targetX * scaleX;
          const by = burst.targetY * scaleY;
          const radius = burstProgress * 45;

          // Radial cone expansion
          const burstGrad = ctx.createRadialGradient(bx, by, 0, bx, by, radius);
          burstGrad.addColorStop(0, 'rgba(0, 242, 255, 0.85)');
          burstGrad.addColorStop(0.5, 'rgba(0, 242, 255, 0.35)');
          burstGrad.addColorStop(1, 'transparent');

          ctx.fillStyle = burstGrad;
          ctx.beginPath();
          ctx.arc(bx, by, radius, 0, Math.PI * 2);
          ctx.fill();

          // Shockwave ring
          ctx.strokeStyle = `rgba(0, 242, 255, ${1 - burstProgress})`;
          ctx.lineWidth = 3;
          ctx.beginPath();
          ctx.arc(bx, by, radius, 0, Math.PI * 2);
          ctx.stroke();

          // Non-negotiable C1 compliance label
          ctx.fillStyle = '#05070d';
          ctx.fillRect(bx - 55, by - radius - 20, 110, 18);
          ctx.strokeStyle = '#00f2ff';
          ctx.lineWidth = 1;
          ctx.strokeRect(bx - 55, by - radius - 20, 110, 18);

          ctx.fillStyle = '#00f2ff';
          ctx.font = 'bold 10px "JetBrains Mono", monospace';
          ctx.fillText('SIMULATED BURST', bx - 48, by - radius - 7);
        }
      });

      // 9. Disconnected Overlay (dim 40% when offline)
      if (connectionState !== 'live') {
        ctx.fillStyle = 'rgba(5, 7, 13, 0.45)';
        ctx.fillRect(0, 0, w, h);
      }

      ctx.restore();
      animId = requestAnimationFrame(renderDynamic);
    };

    animId = requestAnimationFrame(renderDynamic);
    return () => cancelAnimationFrame(animId);
  }, [layers, highlightedTrackId, connectionState]);

  return (
    <div
      ref={containerRef}
      className="relative flex-1 w-full h-full min-h-[360px] overflow-hidden bg-[#05070d] rounded-lg border border-white/8 select-none"
    >
      {/* Static Layer Canvas */}
      <canvas
        ref={staticCanvasRef}
        className="absolute inset-0 pointer-events-none"
      />

      {/* Dynamic Layer Canvas */}
      <canvas
        ref={dynamicCanvasRef}
        className="absolute inset-0"
      />
    </div>
  );
};
