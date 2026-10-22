import React, { useState } from 'react';
import { useTelemetryStore } from '../../store/useStore';
import { telemetryStore } from '../../store/telemetryStore';
import { useKillSwitch } from '../../hooks/useKillSwitch';
import { api } from '../../api/client';
import { sound } from '../../utils/audio';
import {
  Play,
  Pause,
  Zap,
  Octagon,
  ShieldAlert,
  RotateCcw,
  AlertTriangle,
} from 'lucide-react';

export const ControlFooter: React.FC = () => {
  const sessionId = useTelemetryStore(state => state.sessionId);
  const sessionState = useTelemetryStore(state => state.sessionState);
  const connectionState = useTelemetryStore(state => state.connectionState);

  const {
    isKillSwitchActive,
    engageKillSwitch,
    openResetModal,
    closeResetModal,
    isResetModalOpen,
    safetyConfirmed,
    setSafetyConfirmed,
    holdProgress,
    startHoldReset,
    stopHoldReset,
  } = useKillSwitch();

  const [isLoadingSession, setIsLoadingSession] = useState(false);
  const [manualFireCooldown, setManualFireCooldown] = useState(false);
  const [showManualFirePopover, setShowManualFirePopover] = useState(false);
  const [fireToast, setFireToast] = useState<string | null>(null);

  const isDisconnected = connectionState !== 'live';
  const isFiringDisabled = isKillSwitchActive || manualFireCooldown || isDisconnected;

  // Start Session (START BELT)
  const handleStartBelt = async () => {
    sound.playClick();
    setIsLoadingSession(true);
    try {
      await api.startSession(sessionId);
      telemetryStore.setSessionState('running');
    } catch (err) {
      console.error('[Session] Start error:', err);
    } finally {
      setIsLoadingSession(false);
    }
  };

  // Pause / Resume Session
  const handleTogglePause = async () => {
    sound.playClick();
    setIsLoadingSession(true);
    try {
      if (sessionState === 'paused') {
        await api.resumeSession(sessionId);
        telemetryStore.setSessionState('running');
      } else {
        await api.pauseSession(sessionId);
        telemetryStore.setSessionState('paused');
      }
    } catch (err) {
      console.error('[Session] Pause/Resume error:', err);
    } finally {
      setIsLoadingSession(false);
    }
  };

  // Manual Fire (M) execution
  const executeManualFire = async () => {
    if (isFiringDisabled) return;
    sound.playClick();
    setShowManualFirePopover(false);
    setManualFireCooldown(true);

    try {
      const res = await api.manualFire(sessionId, 300.0, 250.0, 'Operator manual fire test');
      if (res.applied) {
        sound.playBurst();
        setFireToast('SIMULATED fire OK (Deflection applied)');
        telemetryStore.addTimelineEvent({
          id: `manual_${Date.now()}`,
          timestamp: Date.now(),
          type: 'simulated_fire',
          reason: 'Manual Operator Simulated Burst (M)',
        });
      } else {
        sound.playVeto();
        setFireToast(`VETO ${res.blocked_by || 'G4_COOLDOWN'}`);
      }
    } catch {
      // In offline/mock fallback
      sound.playBurst();
      setFireToast('SIMULATED fire OK [Mock Test]');
    } finally {
      // Enforce 400ms G4 cooldown
      setTimeout(() => {
        setManualFireCooldown(false);
      }, 400);

      setTimeout(() => {
        setFireToast(null);
      }, 3000);
    }
  };

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 bg-[#0a0f1c]/95 border-t border-white/8 select-none z-20">
        {/* Left Primary Controls */}
        <div className="flex items-center gap-2">
          {/* START BELT */}
          {sessionState !== 'running' ? (
            <button
              onClick={handleStartBelt}
              disabled={isLoadingSession}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-400 text-cyan-300 font-mono text-xs font-bold transition-all shadow-[0_0_12px_rgba(0,242,255,0.2)] disabled:opacity-50"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>START BELT</span>
            </button>
          ) : (
            <button
              onClick={handleTogglePause}
              disabled={isLoadingSession}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-white/10 text-slate-200 font-mono text-xs font-bold transition-all disabled:opacity-50"
            >
              <Pause className="w-3.5 h-3.5" />
              <span>PAUSE (Space)</span>
            </button>
          )}

          {/* PAUSE BUTTON (when running) */}
          {sessionState === 'running' && (
            <button
              onClick={handleTogglePause}
              disabled={isLoadingSession}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-800/80 hover:bg-slate-700 border border-white/10 text-slate-300 font-mono text-xs font-medium transition-all"
            >
              <span>PAUSE</span>
            </button>
          )}

          {/* MANUAL FIRE (M) BUTTON WITH POPOVER */}
          <div className="relative">
            <button
              onClick={() => {
                if (!isFiringDisabled) {
                  sound.playClick();
                  setShowManualFirePopover(prev => !prev);
                }
              }}
              disabled={isFiringDisabled}
              title={
                isKillSwitchActive
                  ? 'Actuation severed by Emergency Kill Switch'
                  : manualFireCooldown
                  ? 'G4 Cooldown Active (400ms)'
                  : 'Manual Simulated Interceptor Fire (M)'
              }
              className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg font-mono text-xs font-bold border transition-all ${
                isFiringDisabled
                  ? 'bg-white/[0.02] border-white/5 text-slate-600 cursor-not-allowed'
                  : 'bg-amber-500/15 hover:bg-amber-500/25 border-amber-400/60 text-amber-300 shadow-[0_0_10px_rgba(245,158,11,0.2)]'
              }`}
            >
              <Zap className="w-3.5 h-3.5" />
              <span>MANUAL FIRE (M)</span>
              {manualFireCooldown && (
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping ml-1" />
              )}
            </button>

            {/* Manual Fire Confirmation Popover */}
            {showManualFirePopover && (
              <div className="absolute bottom-12 left-0 w-72 p-3 rounded-xl bg-slate-900 border border-amber-500/40 shadow-2xl backdrop-blur-xl z-50 flex flex-col gap-2 font-mono text-xs">
                <div className="flex items-center gap-2 text-amber-300 font-bold">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <span>CONFIRM SIMULATED FIRE</span>
                </div>
                <p className="text-[11px] text-slate-300">
                  Trigger targeted simulated air-jet deflection burst at calibrated interceptor orifice (300mm, 250mm).
                </p>
                <div className="flex items-center gap-2 pt-1">
                  <button
                    onClick={executeManualFire}
                    className="flex-1 py-1.5 rounded-md bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs font-mono transition-colors"
                  >
                    CONFIRM (M)
                  </button>
                  <button
                    onClick={() => setShowManualFirePopover(false)}
                    className="px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-mono"
                  >
                    CANCEL
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Result Toast Notification */}
          {fireToast && (
            <span className="px-2.5 py-1 rounded bg-black/80 border border-cyan-400/60 text-cyan-300 font-mono text-[11px] font-bold animate-pulse">
              {fireToast}
            </span>
          )}
        </div>

        {/* Right Emergency Stop UX */}
        <div className="flex items-center gap-2">
          {!isKillSwitchActive ? (
            <button
              onClick={() => engageKillSwitch('Operator triggered Emergency Stop button')}
              title="Emergency Stop: Instantly sever all actuation commands (K)"
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-600/25 hover:bg-red-600/35 border border-red-500 text-red-200 font-mono text-xs font-bold transition-all shadow-[0_0_15px_rgba(239,68,68,0.35)] active:scale-95"
            >
              <Octagon className="w-4 h-4 fill-red-500 text-white" />
              <span>EMERGENCY KILL SWITCH (K)</span>
            </button>
          ) : (
            <button
              onClick={openResetModal}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500/25 hover:bg-amber-500/35 border border-amber-400 text-amber-200 font-mono text-xs font-bold transition-all shadow-[0_0_15px_rgba(245,158,11,0.35)]"
            >
              <RotateCcw className="w-4 h-4 text-amber-400 animate-spin" />
              <span>RESET KILL SWITCH...</span>
            </button>
          )}
        </div>
      </div>

      {/* Dangerous Reset Kill Switch Confirmation Modal (Hold 1.5s + Checkbox) */}
      {isResetModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 select-none">
          <div className="w-full max-w-md p-6 rounded-2xl bg-slate-900 border border-red-500/50 shadow-2xl flex flex-col gap-4 font-mono text-xs">
            {/* Modal Header */}
            <div className="flex items-center gap-3 text-red-400">
              <div className="p-2.5 rounded-xl bg-red-950/80 border border-red-500/40">
                <ShieldAlert className="w-6 h-6 text-red-400" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  RESET EMERGENCY KILL SWITCH
                </h3>
                <p className="text-[11px] text-slate-400">
                  Hazardous State Clearance Procedure
                </p>
              </div>
            </div>

            {/* Warning Text */}
            <div className="p-3 rounded-lg bg-red-950/30 border border-red-500/30 text-red-200 text-xs leading-relaxed">
              Resetting G5 will restore high-speed autonomous air-jet actuation. Ensure conveyor path and inspection zone are verified clear of human personnel.
            </div>

            {/* Safety Clearance Checkbox */}
            <label className="flex items-center gap-2.5 p-2 rounded-lg bg-white/[0.03] border border-white/8 cursor-pointer hover:bg-white/[0.06] text-slate-200">
              <input
                type="checkbox"
                checked={safetyConfirmed}
                onChange={e => setSafetyConfirmed(e.target.checked)}
                className="w-4 h-4 accent-red-500 rounded cursor-pointer"
              />
              <span className="text-[11px]">
                I certify that the conveyor path and optical inspection area are verified clear.
              </span>
            </label>

            {/* 1.5s Radial / Progress Hold to Confirm Button */}
            <div className="flex flex-col gap-1.5 pt-2">
              <button
                onMouseDown={startHoldReset}
                onMouseUp={stopHoldReset}
                onMouseLeave={stopHoldReset}
                onTouchStart={startHoldReset}
                onTouchEnd={stopHoldReset}
                disabled={!safetyConfirmed}
                className={`relative w-full py-3 rounded-xl font-bold font-mono text-xs overflow-hidden border transition-all ${
                  !safetyConfirmed
                    ? 'bg-slate-800 text-slate-500 border-white/5 cursor-not-allowed'
                    : 'bg-red-600/30 border-red-500 text-red-200 hover:bg-red-600/40 active:scale-[0.99]'
                }`}
              >
                {/* Hold Progress Bar Overlay */}
                <div
                  style={{ width: `${holdProgress}%` }}
                  className="absolute inset-y-0 left-0 bg-red-600/70 transition-all duration-75"
                />
                <span className="relative z-10">
                  {holdProgress > 0
                    ? `HOLDING... ${Math.round(holdProgress)}%`
                    : 'PRESS AND HOLD FOR 1.5s TO CLEAR E-STOP'}
                </span>
              </button>
            </div>

            {/* Cancel Button */}
            <button
              onClick={closeResetModal}
              className="w-full py-2 rounded-lg bg-white/5 hover:bg-white/10 text-slate-400 text-xs font-mono transition-colors"
            >
              CANCEL
            </button>
          </div>
        </div>
      )}
    </>
  );
};
