import React from 'react';
import type { TelemetryData } from '../types/vision';
import { Activity, Cpu, AlertTriangle, Layers, Clock } from 'lucide-react';

interface TelemetryHUDProps {
  telemetry: TelemetryData;
  uptimeSeconds: number;
}

export const TelemetryHUD: React.FC<TelemetryHUDProps> = ({ telemetry, uptimeSeconds }) => {
  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60).toString().padStart(2, '0');
    const s = (secs % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const isLatencySpike = telemetry.totalLatencyMs > 25.0;

  return (
    <div className="flex items-center justify-between gap-4 px-4 py-2.5 bg-slate-950/80 backdrop-blur-md border border-cyan-500/20 rounded-lg shadow-lg shadow-cyan-950/30">
      {/* FPS & Throughput */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-900 border border-slate-800 rounded">
          <Activity className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
          <span className="text-[11px] font-mono text-slate-400">SRC:</span>
          <span className="text-xs font-mono font-bold text-cyan-300">{telemetry.sourceFps}</span>
          <span className="text-[10px] text-slate-500">FPS</span>
        </div>

        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-900 border border-slate-800 rounded">
          <span className="text-[11px] font-mono text-slate-400">RENDER:</span>
          <span className="text-xs font-mono font-bold text-emerald-400">{telemetry.processedFps}</span>
          <span className="text-[10px] text-slate-500">FPS</span>
        </div>
      </div>

      {/* Latency Gauge */}
      <div className="flex items-center gap-2">
        <div className={`flex items-center gap-2 px-3 py-1 rounded border ${
          isLatencySpike 
            ? 'bg-rose-950/40 border-rose-500 text-rose-400 animate-bounce' 
            : 'bg-slate-900 border-slate-800 text-slate-300'
        }`}>
          <Cpu className="w-3.5 h-3.5 text-cyan-400" />
          <span className="text-[11px] font-mono text-slate-400">INFERENCE:</span>
          <span className="text-xs font-mono font-bold">{telemetry.totalLatencyMs.toFixed(1)}ms</span>
          <div className="flex items-center gap-1 text-[10px] font-mono text-slate-500 border-l border-slate-700 pl-2">
            <span>CAP:{telemetry.captureLatencyMs}ms</span>
            <span>MODEL:{telemetry.modelLatencyMs}ms</span>
          </div>
        </div>
      </div>

      {/* Active Model & Resolution */}
      <div className="hidden lg:flex items-center gap-2 px-3 py-1 bg-slate-900/90 border border-cyan-500/20 rounded text-xs font-mono">
        <Layers className="w-3.5 h-3.5 text-indigo-400" />
        <span className="text-cyan-300 font-semibold">{telemetry.activeModel}</span>
        <span className="text-slate-500">|</span>
        <span className="text-slate-400">{telemetry.resolution}</span>
      </div>

      {/* Class Counters */}
      <div className="flex items-center gap-2 text-xs font-mono">
        <div className="px-2 py-0.5 bg-cyan-950/40 border border-cyan-500/30 text-cyan-300 rounded">
          OBJS: <strong className="text-white">{telemetry.objectCounts.objects}</strong>
        </div>
        <div className="px-2 py-0.5 bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 rounded">
          PERSONS: <strong className="text-white">{telemetry.objectCounts.persons}</strong>
        </div>
        {telemetry.objectCounts.anomalies > 0 && (
          <div className="flex items-center gap-1 px-2 py-0.5 bg-rose-950/60 border border-rose-500 text-rose-300 rounded animate-pulse">
            <AlertTriangle className="w-3 h-3 text-rose-400" />
            THREATS: <strong className="text-white">{telemetry.objectCounts.anomalies}</strong>
          </div>
        )}
      </div>

      {/* Session Timer */}
      <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-900 border border-slate-800 rounded text-xs font-mono text-slate-400">
        <Clock className="w-3.5 h-3.5 text-amber-400" />
        <span>UPTIME:</span>
        <span className="text-amber-300 font-bold">{formatTime(uptimeSeconds)}</span>
      </div>
    </div>
  );
};
