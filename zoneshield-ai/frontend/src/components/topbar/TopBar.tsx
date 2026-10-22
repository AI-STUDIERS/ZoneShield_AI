import React, { useState, useEffect } from 'react';
import { useTelemetryStore } from '../../store/useStore';
import { telemetryStore } from '../../store/telemetryStore';
import { sound } from '../../utils/audio';
import {
  ShieldAlert,
  Volume2,
  VolumeX,
  Maximize,
  HelpCircle,
  Radio,
  Wifi,
  WifiOff,
  Flame,
} from 'lucide-react';

interface TopBarProps {
  onOpenShortcuts: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({ onOpenShortcuts }) => {
  const connectionState = useTelemetryStore(state => state.connectionState);
  const reconnectAttempt = useTelemetryStore(state => state.reconnectAttempt);
  const nextRetrySeconds = useTelemetryStore(state => state.nextRetrySeconds);
  const isMockMode = useTelemetryStore(state => state.isMockMode);
  const audioEnabled = useTelemetryStore(state => state.audioEnabled);
  const [uptimeSeconds, setUptimeSeconds] = useState(0);

  // Uptime counter
  useEffect(() => {
    const timer = setInterval(() => {
      setUptimeSeconds(prev => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const formatUptime = (totalSec: number) => {
    const h = Math.floor(totalSec / 3600).toString().padStart(2, '0');
    const m = Math.floor((totalSec % 3600) / 60).toString().padStart(2, '0');
    const s = (totalSec % 60).toString().padStart(2, '0');
    return `${h}:${m}:${s}`;
  };

  const toggleFullscreen = () => {
    sound.playClick();
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  };

  const toggleSound = () => {
    telemetryStore.toggleAudio();
    sound.enabled = !audioEnabled;
    if (!audioEnabled) sound.playClick();
  };

  return (
    <header className="flex items-center justify-between px-4 py-2.5 bg-[#05070d]/90 backdrop-blur-md border-b border-white/8 z-30 select-none shadow-md">
      {/* Brand Identity */}
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-cyan-950/60 border border-cyan-400/40 shadow-sm shadow-cyan-500/20">
          <ShieldAlert className="w-4 h-4 text-cyan-400" />
        </div>
        <div className="flex items-center gap-2">
          <span className="font-extrabold tracking-wider text-sm font-sans text-white">
            ZONESHIELD <span className="text-cyan-400">AI</span>
          </span>
          <span className="font-mono-num text-[11px] px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-slate-400">
            v0.1
          </span>
        </div>
      </div>

      {/* Center Compliance Status Badges (Slow 2s pulsing dots) */}
      <div className="hidden md:flex items-center gap-4">
        {/* OPENCV 5.0 (Green) */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-white/[0.03] border border-white/8 text-xs font-mono">
          <span className="w-2 h-2 rounded-full bg-[#22c55e] animate-pulse-slow shadow-[0_0_8px_#22c55e]" />
          <span className="text-slate-300 font-medium">OPENCV 5.0</span>
        </div>

        {/* AWS COOL ARM64 (Blue) */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-white/[0.03] border border-white/8 text-xs font-mono">
          <span className="w-2 h-2 rounded-full bg-[#3b82f6] animate-pulse-slow shadow-[0_0_8px_#3b82f6]" />
          <span className="text-slate-300 font-medium">AWS COOL ARM64</span>
        </div>

        {/* SIMULATED ACTUATOR (Amber - Rule C1 Compliance) */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-amber-950/30 border border-amber-500/30 text-xs font-mono">
          <span className="w-2 h-2 rounded-full bg-[#f59e0b] animate-pulse-slow shadow-[0_0_8px_#f59e0b]" />
          <span className="text-amber-300 font-semibold tracking-wide">SIMULATED ACTUATOR</span>
        </div>

        {/* Dev Mock Stream Active Badge if in mock mode */}
        {isMockMode && (
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-amber-500/20 border border-amber-400 text-amber-300 font-mono text-[10px] animate-pulse">
            <Flame className="w-3 h-3 text-amber-400" />
            <span>MOCK STREAM (?mock=1)</span>
          </div>
        )}
      </div>

      {/* Right Telemetry Controls */}
      <div className="flex items-center gap-3">
        {/* Connection State Chip */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-black/40 border border-white/10 text-xs font-mono">
          {connectionState === 'live' && (
            <>
              <Wifi className="w-3.5 h-3.5 text-[#22c55e]" />
              <span className="text-[#22c55e] font-semibold tracking-wide">LIVE</span>
            </>
          )}
          {connectionState === 'reconnecting' && (
            <>
              <Radio className="w-3.5 h-3.5 text-[#f59e0b] animate-pulse" />
              <span className="text-[#f59e0b] font-medium">
                RECONNECTING ({reconnectAttempt}
                {nextRetrySeconds > 0 ? ` • ${nextRetrySeconds}s` : ''})
              </span>
            </>
          )}
          {connectionState === 'offline' && (
            <>
              <WifiOff className="w-3.5 h-3.5 text-[#ef4444]" />
              <span className="text-[#ef4444] font-semibold">OFFLINE</span>
            </>
          )}
        </div>

        {/* Session Uptime */}
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-black/40 border border-white/10 text-xs font-mono-num text-slate-400">
          <span className="text-[10px] text-slate-500 uppercase tracking-wider">UPTIME</span>
          <span className="text-slate-200 font-semibold">{formatUptime(uptimeSeconds)}</span>
        </div>

        {/* Audio Toggle */}
        <button
          onClick={toggleSound}
          title={audioEnabled ? 'Mute Audio FX' : 'Enable Audio FX'}
          aria-label="Toggle Sound Effects"
          className={`p-1.5 rounded-md border transition-all ${
            audioEnabled
              ? 'bg-cyan-500/15 border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/25'
              : 'bg-white/5 border-white/10 text-slate-500 hover:text-slate-300'
          }`}
        >
          {audioEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
        </button>

        {/* Fullscreen Toggle */}
        <button
          onClick={toggleFullscreen}
          title="Fullscreen (F)"
          aria-label="Toggle Fullscreen"
          className="p-1.5 rounded-md bg-white/5 border border-white/10 text-slate-400 hover:text-cyan-300 transition-colors"
        >
          <Maximize className="w-4 h-4" />
        </button>

        {/* Shortcut Overlay Button */}
        <button
          onClick={() => {
            sound.playClick();
            onOpenShortcuts();
          }}
          title="Keyboard Shortcuts (?)"
          aria-label="Keyboard Shortcuts"
          className="p-1.5 rounded-md bg-white/5 border border-white/10 text-slate-400 hover:text-cyan-300 transition-colors"
        >
          <HelpCircle className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
};
