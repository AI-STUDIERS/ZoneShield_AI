import { useState, useCallback, useRef } from 'react';
import { telemetryStore } from '../store/telemetryStore';
import { useTelemetryStore } from '../store/useStore';
import { api } from '../api/client';
import { sound } from '../utils/audio';

export function useKillSwitch() {
  const isKillSwitchActive = useTelemetryStore(state => state.actuatorState.kill_switch);
  const [isResetModalOpen, setIsResetModalOpen] = useState(false);
  const [safetyConfirmed, setSafetyConfirmed] = useState(false);
  const [holdProgress, setHoldProgress] = useState(0); // 0 to 100
  const holdTimerRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);

  // Instant emergency stop engagement
  const engageKillSwitch = useCallback(async (reason = 'Operator Emergency Stop') => {
    // 1. Optimistic UI update immediately (no waiting on network)
    telemetryStore.setKillSwitchState(true, reason);
    sound.playAlarm();

    // 2. Transmit to backend
    try {
      await api.engageKillSwitch(reason);
    } catch (err) {
      console.error('[KillSwitch] Server sync error:', err);
    }
  }, []);

  // Open reset dialog
  const openResetModal = useCallback(() => {
    setSafetyConfirmed(false);
    setHoldProgress(0);
    setIsResetModalOpen(true);
  }, []);

  const closeResetModal = useCallback(() => {
    if (holdTimerRef.current) {
      cancelAnimationFrame(holdTimerRef.current);
      holdTimerRef.current = null;
    }
    setHoldProgress(0);
    setIsResetModalOpen(false);
  }, []);

  // 1.5-second radial / progress hold to confirm reset
  const startHoldReset = useCallback(() => {
    if (!safetyConfirmed) return;
    startTimeRef.current = performance.now();

    const checkProgress = (now: number) => {
      const elapsed = now - startTimeRef.current;
      const progress = Math.min(100, (elapsed / 1500) * 100);
      setHoldProgress(progress);

      if (progress >= 100) {
        // Confirmed!
        telemetryStore.setKillSwitchState(false);
        sound.playAlert();
        api.resetKillSwitch().catch(err => console.error('[KillSwitch] Reset sync error:', err));
        closeResetModal();
      } else {
        holdTimerRef.current = requestAnimationFrame(checkProgress);
      }
    };

    holdTimerRef.current = requestAnimationFrame(checkProgress);
  }, [safetyConfirmed, closeResetModal]);

  const stopHoldReset = useCallback(() => {
    if (holdTimerRef.current) {
      cancelAnimationFrame(holdTimerRef.current);
      holdTimerRef.current = null;
    }
    setHoldProgress(0);
  }, []);

  return {
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
  };
}
