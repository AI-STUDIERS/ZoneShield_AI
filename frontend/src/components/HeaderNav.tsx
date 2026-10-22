import React, { useState } from 'react';
import { Shield, Volume2, VolumeX, Maximize, Sliders, HelpCircle } from 'lucide-react';
import { sound } from '../utils/audio';

interface HeaderNavProps {
  onToggleDrawer: () => void;
  isDrawerOpen: boolean;
}

export const HeaderNav: React.FC<HeaderNavProps> = ({ onToggleDrawer, isDrawerOpen }) => {
  const [audioEnabled, setAudioEnabled] = useState(true);
  const [showHelp, setShowHelp] = useState(false);

  const toggleAudio = () => {
    sound.enabled = !audioEnabled;
    setAudioEnabled(!audioEnabled);
    if (!audioEnabled) sound.playBeep(600, 'sine', 0.1);
  };

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  };

  return (
    <header className="flex items-center justify-between px-6 py-3 bg-slate-950/95 border-b border-cyan-500/20 backdrop-blur-xl z-30 shadow-md shadow-cyan-950/40">
      {/* Brand Identity */}
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-gradient-to-br from-cyan-500/30 to-indigo-600/30 border border-cyan-400 shadow-sm shadow-cyan-500/50">
          <Shield className="w-5 h-5 text-cyan-300" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-extrabold tracking-wider font-mono text-white">
              ZONESHIELD <span className="text-cyan-400">VISION AUTONOMY</span>
            </h1>
            <span className="px-1.5 py-0.5 text-[10px] font-mono font-bold bg-cyan-950 border border-cyan-500/40 text-cyan-300 rounded">
              v2.4-PRO
            </span>
          </div>
          <p className="text-[11px] font-mono text-slate-400">
            OpenCV 5 + AWS Graviton COOL Neural Edge Perception Dashboard
          </p>
        </div>
      </div>

      {/* Center Compliance Status Badges */}
      <div className="hidden md:flex items-center gap-2 font-mono text-[11px]">
        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-900 border border-cyan-500/30 rounded text-cyan-300">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
          <span>OPENCV 5.0 (C2)</span>
        </div>
        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-900 border border-indigo-500/30 rounded text-indigo-300">
          <span className="w-2 h-2 rounded-full bg-indigo-400" />
          <span>COOL ARM64 NEON (C3)</span>
        </div>
        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-900 border border-amber-500/30 rounded text-amber-300">
          <span>SIMULATED DIGITAL TWIN (C1)</span>
        </div>
      </div>

      {/* Right Action Tools */}
      <div className="flex items-center gap-2">
        <button
          onClick={toggleAudio}
          title={audioEnabled ? "Disable Synthesizer Audio FX" : "Enable Synthesizer Audio FX"}
          className={`p-2 rounded border transition-all ${
            audioEnabled
              ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300'
              : 'bg-slate-900 border-slate-800 text-slate-500 hover:text-slate-300'
          }`}
        >
          {audioEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
        </button>

        <button
          onClick={toggleFullscreen}
          title="Toggle Fullscreen (F)"
          className="p-2 rounded bg-slate-900 border border-slate-800 text-slate-400 hover:text-cyan-300 transition-colors"
        >
          <Maximize className="w-4 h-4" />
        </button>

        <button
          onClick={() => setShowHelp(!showHelp)}
          title="Keyboard Shortcuts & System Info"
          className="p-2 rounded bg-slate-900 border border-slate-800 text-slate-400 hover:text-cyan-300 transition-colors"
        >
          <HelpCircle className="w-4 h-4" />
        </button>

        {/* OpenCV Pipeline Tuner Toggle */}
        <button
          onClick={onToggleDrawer}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded font-mono text-xs font-semibold border transition-all ${
            isDrawerOpen
              ? 'bg-cyan-500 text-slate-950 border-cyan-400 shadow-md shadow-cyan-500/40'
              : 'bg-slate-900 text-cyan-400 border-cyan-500/30 hover:bg-slate-800'
          }`}
        >
          <Sliders className="w-4 h-4" />
          <span>PIPELINE TUNER</span>
        </button>
      </div>

      {/* Keyboard Shortcuts Modal */}
      {showHelp && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-cyan-500/40 rounded-xl p-6 max-w-md w-full shadow-2xl font-mono text-xs text-slate-300 space-y-4">
            <div className="flex justify-between items-center pb-2 border-b border-slate-800">
              <h3 className="text-sm font-bold text-cyan-400 uppercase">Mission Control Hotkeys</h3>
              <button onClick={() => setShowHelp(false)} className="text-slate-500 hover:text-white">✕</button>
            </div>
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <div><kbd className="px-1.5 py-0.5 bg-slate-800 border border-slate-700 rounded text-cyan-300">Space</kbd> : Play / Pause</div>
              <div><kbd className="px-1.5 py-0.5 bg-slate-800 border border-slate-700 rounded text-cyan-300">F</kbd> : Fullscreen Toggle</div>
              <div><kbd className="px-1.5 py-0.5 bg-slate-800 border border-slate-700 rounded text-cyan-300">[</kbd> : Step Back 1 Frame</div>
              <div><kbd className="px-1.5 py-0.5 bg-slate-800 border border-slate-700 rounded text-cyan-300">]</kbd> : Step Forward 1 Frame</div>
              <div><kbd className="px-1.5 py-0.5 bg-slate-800 border border-slate-700 rounded text-cyan-300">S</kbd> : Snapshot PNG Export</div>
              <div><kbd className="px-1.5 py-0.5 bg-slate-800 border border-slate-700 rounded text-cyan-300">Dbl-Click</kbd> : Reset Zoom & Pan</div>
            </div>
            <p className="text-[10px] text-slate-500 pt-2 border-t border-slate-800">
              Drag wipe divider bar to compare raw video against OpenCV neural inference.
            </p>
          </div>
        </div>
      )}
    </header>
  );
};
