import React, { useEffect, useState } from 'react';
import { useTelemetryStore } from '../../store/useStore';
import { ShieldCheck, Clock, Terminal } from 'lucide-react';

export const FooterBar: React.FC = () => {
  const connectionState = useTelemetryStore(state => state.connectionState);
  const lastFrameTimestamp = useTelemetryStore(state => state.lastFrameTimestamp);
  const metrics = useTelemetryStore(state => state.metrics);
  const debugMode = useTelemetryStore(state => state.debugMode);

  const [frameAgeMs, setFrameAgeMs] = useState(0);

  // Frame age ticker
  useEffect(() => {
    const timer = setInterval(() => {
      if (lastFrameTimestamp > 0) {
        setFrameAgeMs(Math.max(0, Date.now() - lastFrameTimestamp));
      }
    }, 100);
    return () => clearInterval(timer);
  }, [lastFrameTimestamp]);

  return (
    <footer className="flex flex-wrap items-center justify-between px-4 py-1.5 bg-[#05070d] border-t border-white/8 text-[11px] font-mono text-slate-400 select-none z-10">
      {/* Left: Non-negotiable C1 Constraint Line */}
      <div className="flex items-center gap-2 text-amber-400/90 font-medium">
        <ShieldCheck className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
        <span className="tracking-wide">
          Digital twin only. Zero physical GPIO/solenoids fired.
        </span>
      </div>

      {/* Right: Technical Link State, Seq #, Last-Frame Age */}
      <div className="flex items-center gap-4">
        {/* Debug FPS Meter (?debug=1) */}
        {debugMode && (
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-purple-950/60 border border-purple-400/40 text-purple-300 text-[10px]">
            <Terminal className="w-3 h-3 text-purple-400" />
            <span>DEV RENDER: 60.0 FPS | TELEMETRY: {metrics.fps.toFixed(1)} FPS</span>
          </div>
        )}

        {/* WebSocket Status */}
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-slate-500 uppercase">WS:</span>
          <span
            className={`font-semibold ${
              connectionState === 'live'
                ? 'text-[#22c55e]'
                : connectionState === 'reconnecting'
                ? 'text-[#f59e0b]'
                : 'text-[#ef4444]'
            }`}
          >
            {connectionState.toUpperCase()}
          </span>
        </div>

        {/* Last-Frame Age */}
        <div className="flex items-center gap-1.5 font-mono-num">
          <Clock className="w-3 h-3 text-slate-500" />
          <span className="text-[10px] text-slate-500 uppercase">AGE:</span>
          <span
            className={`${
              frameAgeMs > 500 ? 'text-amber-400 font-bold' : 'text-slate-300'
            }`}
          >
            {lastFrameTimestamp === 0 ? '--' : `${frameAgeMs}ms`}
          </span>
        </div>
      </div>
    </footer>
  );
};
