import React, { useRef, useEffect, useState } from 'react';
import { useTelemetryStore } from '../../store/useStore';
import { Activity, Clock, ShieldAlert, Cpu, ArrowUpRight, ArrowDownRight, Minus, AlertTriangle } from 'lucide-react';
import type { PipelineTimings } from '../../types/telemetry';

export const TelemetryTab: React.FC = () => {
  const metrics = useTelemetryStore(state => state.metrics);
  const rollingAverages = useTelemetryStore(state => state.rollingAverages);
  const pipelineTimings = useTelemetryStore(state => state.pipelineTimings);
  const latencyHistory = useTelemetryStore(state => state.latencyHistory);
  const actuatorTimeline = useTelemetryStore(state => state.actuatorTimeline);
  const simulatedThreatsCount = useTelemetryStore(state => state.simulatedThreatsCount);

  const sparklineCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  // Compute total pipeline latency from real keys
  const stageKeys: (keyof PipelineTimings)[] = [
    'UndistortHomography',
    'ROIDownscale',
    'BackgroundSubtract',
    'Morphology',
    'Contours',
    'Tracker',
    'Predictor',
  ];

  const totalComputeMs = stageKeys.reduce<number>((acc, key) => acc + (pipelineTimings[key] || 0), 0);
  const maxStage = stageKeys.reduce(
    (max, key) => ((pipelineTimings[key] || 0) > (pipelineTimings[max] || 0) ? key : max),
    'BackgroundSubtract' as keyof PipelineTimings
  );

  const isBudgetExceeded = metrics.compute_ms > 33.3;

  // Render Latency Sparkline Canvas (120 samples)
  useEffect(() => {
    const canvas = sparklineCanvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
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
    ctx.clearRect(0, 0, w, h);

    const samples = latencyHistory.slice(-120);
    const maxVal = Math.max(40, ...samples);
    const stepX = w / (samples.length - 1 || 1);

    // 33.3ms Budget Line (dashed red)
    const budgetY = h - (33.3 / maxVal) * (h - 10) - 5;
    ctx.strokeStyle = 'rgba(239, 68, 68, 0.45)';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(0, budgetY);
    ctx.lineTo(w, budgetY);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = 'rgba(239, 68, 68, 0.7)';
    ctx.font = '8px "JetBrains Mono", monospace';
    ctx.fillText('33.3ms BUDGET (30 FPS)', 6, budgetY - 3);

    // Gradient Area Fill
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, 'rgba(0, 242, 255, 0.25)');
    grad.addColorStop(1, 'rgba(0, 242, 255, 0.01)');

    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(0, h);

    samples.forEach((val, idx) => {
      const x = idx * stepX;
      const y = h - (val / maxVal) * (h - 10) - 5;
      if (idx === 0) ctx.lineTo(x, y);
      else ctx.lineTo(x, y);
    });

    ctx.lineTo(w, h);
    ctx.closePath();
    ctx.fill();

    // Line Path with Red Spikes for Values > 33.3ms
    for (let i = 1; i < samples.length; i++) {
      const prevVal = samples[i - 1];
      const curVal = samples[i];
      const prevX = (i - 1) * stepX;
      const prevY = h - (prevVal / maxVal) * (h - 10) - 5;
      const curX = i * stepX;
      const curY = h - (curVal / maxVal) * (h - 10) - 5;

      ctx.strokeStyle = (curVal > 33.3 || prevVal > 33.3) ? '#ef4444' : '#00f2ff';
      ctx.lineWidth = (curVal > 33.3 || prevVal > 33.3) ? 2.5 : 1.5;
      ctx.beginPath();
      ctx.moveTo(prevX, prevY);
      ctx.lineTo(curX, curY);
      ctx.stroke();
    }

    // Hover Crosshair
    if (hoverIndex !== null && hoverIndex >= 0 && hoverIndex < samples.length) {
      const hoverVal = samples[hoverIndex];
      const hx = hoverIndex * stepX;
      const hy = h - (hoverVal / maxVal) * (h - 10) - 5;

      ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 2]);

      // Vertical line
      ctx.beginPath();
      ctx.moveTo(hx, 0);
      ctx.lineTo(hx, h);
      ctx.stroke();
      ctx.setLineDash([]);

      // Point dot
      ctx.fillStyle = hoverVal > 33.3 ? '#ef4444' : '#00f2ff';
      ctx.beginPath();
      ctx.arc(hx, hy, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Tooltip pill
      const tipText = `${hoverVal.toFixed(2)} ms`;
      ctx.font = 'bold 9px "JetBrains Mono"';
      ctx.fillStyle = 'rgba(5, 7, 13, 0.9)';
      ctx.fillRect(Math.min(w - 60, hx + 8), hy - 16, 52, 16);
      ctx.strokeStyle = '#00f2ff';
      ctx.strokeRect(Math.min(w - 60, hx + 8), hy - 16, 52, 16);
      ctx.fillStyle = '#ffffff';
      ctx.fillText(tipText, Math.min(w - 60, hx + 8) + 6, hy - 4);
    }

    ctx.restore();
  }, [latencyHistory, hoverIndex]);

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = sparklineCanvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const stepX = rect.width / 119;
    const index = Math.min(119, Math.max(0, Math.round(x / stepX)));
    setHoverIndex(index);
  };

  return (
    <div className="flex flex-col gap-3.5 p-3 overflow-y-auto select-none h-full">
      {/* 1. Four Mission-Critical KPI Cards */}
      <div className="grid grid-cols-2 gap-2">
        {/* KPI 1: Pipeline Throughput */}
        <div className="flex flex-col p-2.5 rounded-lg bg-black/40 border border-white/8">
          <div className="flex items-center justify-between text-slate-400">
            <span className="micro-label">PIPELINE THROUGHPUT</span>
            <Activity className="w-3.5 h-3.5 text-cyan-400" />
          </div>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="font-mono-num text-xl font-bold text-white tracking-tight">
              {metrics.fps.toFixed(1)}
            </span>
            <span className="text-[10px] font-mono text-slate-500 uppercase">FPS</span>
          </div>
          <div className="flex items-center gap-1 mt-1 text-[10px] font-mono">
            {rollingAverages.deltaFps > 0 ? (
              <span className="flex items-center text-[#22c55e]">
                <ArrowUpRight className="w-3 h-3" /> +{rollingAverages.deltaFps} vs 10s
              </span>
            ) : rollingAverages.deltaFps < 0 ? (
              <span className="flex items-center text-[#f59e0b]">
                <ArrowDownRight className="w-3 h-3" /> {rollingAverages.deltaFps} vs 10s
              </span>
            ) : (
              <span className="flex items-center text-slate-500">
                <Minus className="w-3 h-3" /> 0.0 vs 10s
              </span>
            )}
          </div>
        </div>

        {/* KPI 2: Compute Latency */}
        <div
          className={`flex flex-col p-2.5 rounded-lg border transition-colors ${
            isBudgetExceeded
              ? 'bg-red-950/40 border-red-500/50 text-red-200'
              : 'bg-black/40 border-white/8'
          }`}
        >
          <div className="flex items-center justify-between text-slate-400">
            <span className="micro-label">COMPUTE LATENCY</span>
            <Cpu className={`w-3.5 h-3.5 ${isBudgetExceeded ? 'text-red-400' : 'text-cyan-400'}`} />
          </div>
          <div className="flex items-baseline gap-1 mt-1">
            <span
              className={`font-mono-num text-xl font-bold tracking-tight ${
                isBudgetExceeded ? 'text-red-400' : 'text-white'
              }`}
            >
              {metrics.compute_ms.toFixed(2)}
            </span>
            <span className="text-[10px] font-mono text-slate-500 uppercase">MS</span>
          </div>
          <div className="flex items-center gap-1 mt-1 text-[10px] font-mono">
            {isBudgetExceeded ? (
              <span className="flex items-center text-red-400 font-semibold">
                <AlertTriangle className="w-3 h-3 mr-0.5" /> &gt; 33.3ms budget
              </span>
            ) : rollingAverages.deltaComputeMs <= 0 ? (
              <span className="flex items-center text-[#22c55e]">
                <ArrowDownRight className="w-3 h-3" /> {rollingAverages.deltaComputeMs} ms vs 10s
              </span>
            ) : (
              <span className="flex items-center text-[#f59e0b]">
                <ArrowUpRight className="w-3 h-3" /> +{rollingAverages.deltaComputeMs} ms vs 10s
              </span>
            )}
          </div>
        </div>

        {/* KPI 3: Threats Intercepted (Simulated C1) */}
        <div className="flex flex-col p-2.5 rounded-lg bg-black/40 border border-white/8">
          <div className="flex items-center justify-between text-slate-400">
            <span className="micro-label">THREATS INTERCEPTED</span>
            <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
          </div>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="font-mono-num text-xl font-bold text-amber-300 tracking-tight">
              {simulatedThreatsCount}
            </span>
            <span className="text-[10px] font-mono text-amber-400/80 uppercase font-bold">
              [SIM]
            </span>
          </div>
          <span className="text-[10px] text-slate-500 font-mono mt-1">
            Zero physical solenoids
          </span>
        </div>

        {/* KPI 4: Ring-Buffer Drops */}
        <div className="flex flex-col p-2.5 rounded-lg bg-black/40 border border-white/8">
          <div className="flex items-center justify-between text-slate-400">
            <span className="micro-label">RING-BUFFER DROPS</span>
            <Clock className="w-3.5 h-3.5 text-slate-400" />
          </div>
          <div className="flex items-baseline gap-1 mt-1">
            <span
              className={`font-mono-num text-xl font-bold tracking-tight ${
                metrics.dropped_frames > 0 ? 'text-amber-400' : 'text-slate-200'
              }`}
            >
              {metrics.dropped_frames}
            </span>
            <span className="text-[10px] font-mono text-slate-500 uppercase">PKTS</span>
          </div>
          <span className="text-[10px] text-slate-500 font-mono mt-1">
            Drop-stale policy
          </span>
        </div>
      </div>

      {/* 2. Latency Sparkline Card (last 120 samples) */}
      <div className="flex flex-col p-3 rounded-lg bg-black/40 border border-white/8">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5">
            <span className="micro-label">LIVE LATENCY SPARKLINE</span>
            <span className="text-[9px] font-mono text-slate-500">(LAST 120 FRAMES)</span>
          </div>
          <span className="font-mono-num text-xs text-cyan-300 font-semibold">
            {metrics.compute_ms.toFixed(2)} ms
          </span>
        </div>
        <div className="relative w-full h-24">
          <canvas
            ref={sparklineCanvasRef}
            onMouseMove={handleMouseMove}
            onMouseLeave={() => setHoverIndex(null)}
            className="w-full h-full cursor-crosshair"
          />
        </div>
      </div>

      {/* 3. Pipeline Stage Waterfall (Real Keys from pipeline_timings) */}
      <div className="flex flex-col p-3 rounded-lg bg-black/40 border border-white/8">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5">
            <span className="micro-label">PIPELINE STAGE WATERFALL</span>
            <span className="text-[9px] font-mono text-slate-500">OPENCV 5 + COOL</span>
          </div>
          <span className="font-mono-num text-xs text-slate-300 font-bold">
            TOTAL: {totalComputeMs.toFixed(2)} ms
          </span>
        </div>

        {/* Horizontal Stacked Bar */}
        <div className="w-full h-2.5 rounded-full overflow-hidden flex bg-white/5 mb-3">
          {stageKeys.map(key => {
            const time = pipelineTimings[key] || 0;
            const pct = totalComputeMs > 0 ? (time / totalComputeMs) * 100 : 0;
            const colors: Record<string, string> = {
              UndistortHomography: 'bg-indigo-500',
              ROIDownscale: 'bg-blue-500',
              BackgroundSubtract: 'bg-cyan-500',
              Morphology: 'bg-teal-500',
              Contours: 'bg-emerald-500',
              Tracker: 'bg-amber-500',
              Predictor: 'bg-purple-500',
            };
            return (
              <div
                key={key}
                title={`${key}: ${time.toFixed(2)}ms (${pct.toFixed(1)}%)`}
                style={{ width: `${pct}%` }}
                className={`h-full ${colors[key] || 'bg-slate-500'}`}
              />
            );
          })}
        </div>

        {/* Breakdown Rows for Real Keys */}
        <div className="flex flex-col gap-1.5 text-xs font-mono">
          {stageKeys.map(key => {
            const time = pipelineTimings[key] || 0;
            const pct = totalComputeMs > 0 ? (time / totalComputeMs) * 100 : 0;
            const isSlowest = key === maxStage && time > 0;

            return (
              <div
                key={key}
                className={`flex items-center justify-between px-2 py-1 rounded transition-colors ${
                  isSlowest ? 'bg-amber-500/10 border border-amber-500/30' : 'hover:bg-white/[0.02]'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      isSlowest ? 'bg-amber-400' : 'bg-slate-600'
                    }`}
                  />
                  <span className={`${isSlowest ? 'text-amber-200 font-semibold' : 'text-slate-300'}`}>
                    {key}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[10px] text-slate-500 font-mono-num">
                    {pct.toFixed(1)}%
                  </span>
                  <span
                    className={`font-mono-num font-semibold ${
                      isSlowest ? 'text-amber-300' : 'text-slate-200'
                    }`}
                  >
                    {time.toFixed(2)} ms
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 4. Actuator 60s Strip & Cooldown Timeline */}
      <div className="flex flex-col p-3 rounded-lg bg-black/40 border border-white/8">
        <div className="flex items-center justify-between mb-2">
          <span className="micro-label">ACTUATOR TIMELINE (LAST 60s)</span>
          <span className="text-[10px] font-mono text-amber-400 font-semibold">
            G4 COOLDOWN ENFORCED (400ms)
          </span>
        </div>

        {actuatorTimeline.length === 0 ? (
          <div className="py-4 text-center text-slate-500 font-mono text-xs">
            No simulated actuation events recorded in the last 60 seconds.
          </div>
        ) : (
          <div className="flex flex-col gap-1 max-h-36 overflow-y-auto pr-1">
            {actuatorTimeline.map(ev => {
              const ageSec = Math.round((Date.now() - ev.timestamp) / 1000);
              return (
                <div
                  key={ev.id}
                  className="flex items-center justify-between px-2 py-1 rounded bg-white/[0.02] border border-white/5 text-[11px] font-mono"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        ev.type === 'simulated_fire'
                          ? 'bg-cyan-400'
                          : ev.type === 'veto'
                          ? 'bg-red-400'
                          : 'bg-amber-400'
                      }`}
                    />
                    <span className="text-slate-200">{ev.reason}</span>
                  </div>
                  <span className="text-slate-500 text-[10px] font-mono-num">
                    {ageSec}s ago
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
