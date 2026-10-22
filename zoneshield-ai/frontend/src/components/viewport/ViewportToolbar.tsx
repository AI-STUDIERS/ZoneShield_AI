import React from 'react';
import { useTelemetryStore } from '../../store/useStore';
import { telemetryStore } from '../../store/telemetryStore';
import { sound } from '../../utils/audio';
import type { ViewportMode } from '../../types/telemetry';
import {
  Radar,
  Box,
  Eye,
  SlidersHorizontal,
} from 'lucide-react';

export const ViewportToolbar: React.FC = () => {
  const viewportMode = useTelemetryStore(state => state.viewportMode);
  const layers = useTelemetryStore(state => state.layers);
  const tracks = useTelemetryStore(state => state.tracks);
  const guardrails = useTelemetryStore(state => state.guardrails);

  const setMode = (mode: ViewportMode) => {
    sound.playClick();
    telemetryStore.setViewportMode(mode);
  };

  const toggleLayer = (layer: keyof typeof layers) => {
    sound.playClick();
    telemetryStore.toggleLayer(layer);
  };

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 bg-[#0a0f1c]/80 border-b border-white/8 select-none">
      {/* Viewport Modes */}
      <div className="flex items-center gap-1.5">
        <button
          onClick={() => setMode('radar2d')}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono font-medium transition-all ${
            viewportMode === 'radar2d'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-400/50 shadow-[0_0_10px_rgba(0,242,255,0.2)]'
              : 'bg-white/[0.03] text-slate-400 border border-white/5 hover:text-slate-200 hover:bg-white/[0.06]'
          }`}
        >
          <Radar className="w-3.5 h-3.5" />
          <span>2D RADAR</span>
        </button>

        <button
          onClick={() => setMode('iso3d')}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono font-medium transition-all ${
            viewportMode === 'iso3d'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-400/50 shadow-[0_0_10px_rgba(0,242,255,0.2)]'
              : 'bg-white/[0.03] text-slate-400 border border-white/5 hover:text-slate-200 hover:bg-white/[0.06]'
          }`}
        >
          <Box className="w-3.5 h-3.5" />
          <span>3D ISOMETRIC</span>
        </button>

        <button
          onClick={() => setMode('mog2')}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono font-medium transition-all ${
            viewportMode === 'mog2'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-400/50 shadow-[0_0_10px_rgba(0,242,255,0.2)]'
              : 'bg-white/[0.03] text-slate-400 border border-white/5 hover:text-slate-200 hover:bg-white/[0.06]'
          }`}
        >
          <Eye className="w-3.5 h-3.5" />
          <span>MOG2 MASK</span>
        </button>
      </div>

      {/* Center Target Count */}
      <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-black/40 border border-white/8 text-xs font-mono">
        <span className="text-[10px] text-slate-500 uppercase tracking-wider">ACTIVE TARGETS:</span>
        <span className="font-mono-num font-bold text-cyan-300">{tracks.length}</span>
      </div>

      {/* Right Guardrails Chips (G1 - G5) */}
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider hidden xl:inline mr-1">
          GUARDRAILS:
        </span>
        {(['G1', 'G2', 'G3', 'G4', 'G5'] as const).map(gid => {
          const g = guardrails[gid];
          const isVeto = g.status === 'veto';
          return (
            <div
              key={gid}
              title={`${g.name}: ${g.description} (${g.threshold})${g.lastVetoReason ? ` — VETO: ${g.lastVetoReason}` : ''}`}
              className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono transition-all ${
                isVeto
                  ? 'bg-red-950/80 border border-red-500 text-red-300 animate-bounce shadow-[0_0_8px_#ef4444]'
                  : 'bg-white/[0.02] border border-white/8 text-slate-400'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isVeto ? 'bg-red-400 animate-ping' : 'bg-[#22c55e]'
                }`}
              />
              <span className="font-bold">{gid}</span>
            </div>
          );
        })}
      </div>

      {/* Layer Toggles (Sub-toolbar) */}
      <div className="w-full flex items-center justify-between pt-1.5 border-t border-white/5 text-[11px] font-mono text-slate-400">
        <div className="flex items-center gap-1 text-[10px] text-slate-500 uppercase">
          <SlidersHorizontal className="w-3 h-3 text-cyan-400" />
          <span>LAYERS:</span>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1 cursor-pointer hover:text-slate-200">
            <input
              type="checkbox"
              checked={layers.trajectories}
              onChange={() => toggleLayer('trajectories')}
              className="accent-cyan-400 rounded cursor-pointer"
            />
            <span>Trajectory Ribbon</span>
          </label>

          <label className="flex items-center gap-1 cursor-pointer hover:text-slate-200">
            <input
              type="checkbox"
              checked={layers.uncertaintyCone}
              onChange={() => toggleLayer('uncertaintyCone')}
              className="accent-cyan-400 rounded cursor-pointer"
            />
            <span>Uncertainty Cone</span>
          </label>

          <label className="flex items-center gap-1 cursor-pointer hover:text-slate-200">
            <input
              type="checkbox"
              checked={layers.jetEnvelope}
              onChange={() => toggleLayer('jetEnvelope')}
              className="accent-cyan-400 rounded cursor-pointer"
            />
            <span>Jet Envelope (G2)</span>
          </label>

          <label className="flex items-center gap-1 cursor-pointer hover:text-slate-200">
            <input
              type="checkbox"
              checked={layers.sensorGrid}
              onChange={() => toggleLayer('sensorGrid')}
              className="accent-cyan-400 rounded cursor-pointer"
            />
            <span>Tactical Grid</span>
          </label>
        </div>
      </div>
    </div>
  );
};
