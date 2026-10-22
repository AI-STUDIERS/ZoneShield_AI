import React from 'react';
import { X, Command } from 'lucide-react';
import { sound } from '../../utils/audio';

interface ShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ShortcutsModal: React.FC<ShortcutsModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  const shortcuts = [
    { key: 'Space', desc: 'Start / Pause Conveyor Inspection Belt' },
    { key: 'M', desc: 'Trigger Manual Simulated Interceptor Fire' },
    { key: 'K', desc: 'Engage Instant Emergency Kill Switch (E-Stop)' },
    { key: '1', desc: 'Switch Viewport to 2D Optical Radar' },
    { key: '2', desc: 'Switch Viewport to 3D Isometric View' },
    { key: '3', desc: 'Switch Viewport to MOG2 Mask View' },
    { key: 'T', desc: 'Cycle Right Side-Panel Tabs (Telemetry / Trace / Review)' },
    { key: 'F', desc: 'Toggle Operational Console Fullscreen' },
    { key: '?', desc: 'Open / Close Shortcuts Reference Modal' },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 select-none">
      <div className="w-full max-w-lg p-6 rounded-2xl bg-slate-900 border border-white/10 shadow-2xl flex flex-col gap-4 font-mono text-xs">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-white/8 text-white">
          <div className="flex items-center gap-2">
            <Command className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-bold tracking-wider uppercase">
              OPERATIONAL CONSOLE SHORTCUTS
            </h3>
          </div>
          <button
            onClick={() => {
              sound.playClick();
              onClose();
            }}
            className="p-1 rounded-md hover:bg-white/10 text-slate-400 hover:text-white"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Shortcuts List */}
        <div className="flex flex-col gap-2">
          {shortcuts.map(s => (
            <div
              key={s.key}
              className="flex items-center justify-between p-2 rounded-lg bg-black/40 border border-white/5"
            >
              <span className="text-slate-300">{s.desc}</span>
              <kbd className="px-2 py-1 rounded bg-slate-800 border border-white/10 text-cyan-300 font-bold text-xs shadow-sm">
                {s.key}
              </kbd>
            </div>
          ))}
        </div>

        {/* Footer Note */}
        <div className="pt-2 border-t border-white/5 flex items-center justify-between text-[11px] text-slate-500">
          <span>ZoneShield AI v0.1 • Tactical Mission Control</span>
          <span>Press ESC or ? to dismiss</span>
        </div>
      </div>
    </div>
  );
};
