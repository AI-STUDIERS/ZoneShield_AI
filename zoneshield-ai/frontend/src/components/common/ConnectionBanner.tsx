import React from 'react';
import { useTelemetryStore } from '../../store/useStore';
import { AlertTriangle, RefreshCw, ShieldOff, Info } from 'lucide-react';
import { sound } from '../../utils/audio';

interface ConnectionBannerProps {
  onRetry: () => void;
}

export const ConnectionBanner: React.FC<ConnectionBannerProps> = ({ onRetry }) => {
  const connectionState = useTelemetryStore(state => state.connectionState);
  const reconnectAttempt = useTelemetryStore(state => state.reconnectAttempt);
  const nextRetrySeconds = useTelemetryStore(state => state.nextRetrySeconds);
  const isKillSwitchActive = useTelemetryStore(state => state.actuatorState.kill_switch);
  const isMockMode = useTelemetryStore(state => state.isMockMode);

  return (
    <div className="flex flex-col select-none">
      {/* Emergency Kill Switch Banner */}
      {isKillSwitchActive && (
        <div className="flex items-center justify-between px-4 py-2 bg-gradient-to-r from-red-950 via-red-900 to-red-950 border-b border-red-500/60 shadow-lg text-red-100 z-20">
          <div className="flex items-center gap-2.5">
            <ShieldOff className="w-4 h-4 text-red-400 animate-pulse" />
            <span className="font-mono text-xs font-bold tracking-wider uppercase text-red-200">
              KILL SWITCH ACTIVE — ACTUATION SEVERED (G5)
            </span>
            <span className="hidden sm:inline text-[11px] text-red-300/80 font-mono">
              All simulated air-jet firing commands are blocked at the kernel level.
            </span>
          </div>
          <span className="px-2 py-0.5 rounded bg-red-800/80 border border-red-400 text-[10px] font-mono font-bold text-white uppercase tracking-wider">
            E-STOP ENGAGED
          </span>
        </div>
      )}

      {/* Connection Lost Banner */}
      {connectionState !== 'live' && (
        <div className="flex items-center justify-between px-4 py-1.5 bg-[#0f172a]/95 border-b border-amber-500/40 text-amber-200 text-xs font-mono z-20">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
            <span className="font-semibold">
              CONNECTION LOST — reconnecting (attempt {reconnectAttempt}
              {nextRetrySeconds > 0 ? `, next try in ${nextRetrySeconds}s` : ''})
            </span>
            <span className="hidden md:inline text-slate-400 text-[11px]">
              • Actuator state failsafe: UNKNOWN / DISCONNECTED
            </span>
          </div>
          <button
            onClick={() => {
              sound.playClick();
              onRetry();
            }}
            className="flex items-center gap-1.5 px-2.5 py-0.5 bg-amber-500/20 hover:bg-amber-500/30 border border-amber-400/60 text-amber-300 rounded font-mono text-[11px] transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
            <span>Retry now</span>
          </button>
        </div>
      )}

      {/* Mock Data Banner */}
      {isMockMode && (
        <div className="flex items-center justify-between px-4 py-1 bg-amber-950/40 border-b border-amber-500/20 text-amber-300 text-[11px] font-mono z-10">
          <div className="flex items-center gap-2">
            <Info className="w-3.5 h-3.5 text-amber-400" />
            <span className="font-bold tracking-wide">MOCK TELEMETRY ACTIVE</span>
            <span className="text-amber-400/80">
              Dev-only synthetic physics stream (?mock=1). All metrics generated locally.
            </span>
          </div>
          <span className="text-[10px] text-amber-400/60 font-mono">TRUTH RULE T1 COMPLIANT</span>
        </div>
      )}
    </div>
  );
};
