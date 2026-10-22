import React, { useState, useEffect } from 'react';
import { useTelemetryStore } from './store/useStore';
import { telemetryStore, type TabId } from './store/telemetryStore';
import { useTelemetrySocket } from './hooks/useTelemetrySocket';
import { useKillSwitch } from './hooks/useKillSwitch';
import { TopBar } from './components/topbar/TopBar';
import { ConnectionBanner } from './components/common/ConnectionBanner';
import { ViewportWorkspace } from './components/viewport/ViewportWorkspace';
import { SidePanelTabs } from './components/panel/SidePanelTabs';
import { ControlFooter } from './components/controls/ControlFooter';
import { FooterBar } from './components/footer/FooterBar';
import { ShortcutsModal } from './components/common/ShortcutsModal';
import { api } from './api/client';
import { sound } from './utils/audio';

export const App: React.FC = () => {
  const sessionId = useTelemetryStore(state => state.sessionId);
  const sessionState = useTelemetryStore(state => state.sessionState);
  const isKillSwitchActive = useTelemetryStore(state => state.actuatorState.kill_switch);
  const activeTab = useTelemetryStore(state => state.activeTab);

  const [isShortcutsOpen, setIsShortcutsOpen] = useState(false);

  // Initialize resilient WebSocket telemetry & mock engine
  const { retryNow } = useTelemetrySocket(sessionId);
  const { engageKillSwitch } = useKillSwitch();

  // Keyboard shortcut listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      if (e.code === 'Space') {
        e.preventDefault();
        sound.playClick();
        if (sessionState === 'running') {
          api.pauseSession(sessionId).then(() => telemetryStore.setSessionState('paused')).catch(() => {});
        } else {
          api.startSession(sessionId).then(() => telemetryStore.setSessionState('running')).catch(() => {});
        }
      } else if (e.code === 'KeyK') {
        e.preventDefault();
        engageKillSwitch('Operator keyboard shortcut [K]');
      } else if (e.code === 'KeyM') {
        e.preventDefault();
        if (!isKillSwitchActive) {
          sound.playClick();
          api.manualFire(sessionId).catch(() => {});
          telemetryStore.addTimelineEvent({
            id: `manual_${Date.now()}`,
            timestamp: Date.now(),
            type: 'simulated_fire',
            reason: 'Manual Operator Simulated Fire (M)',
          });
        }
      } else if (e.code === 'Digit1') {
        e.preventDefault();
        sound.playClick();
        telemetryStore.setViewportMode('radar2d');
      } else if (e.code === 'Digit2') {
        e.preventDefault();
        sound.playClick();
        telemetryStore.setViewportMode('iso3d');
      } else if (e.code === 'Digit3') {
        e.preventDefault();
        sound.playClick();
        telemetryStore.setViewportMode('mog2');
      } else if (e.code === 'KeyT') {
        e.preventDefault();
        sound.playClick();
        const tabs: TabId[] = ['telemetry', 'trace', 'review', 'selfcheck'];
        const nextIdx = (tabs.indexOf(activeTab) + 1) % tabs.length;
        telemetryStore.setActiveTab(tabs[nextIdx]);
      } else if (e.key === '?') {
        e.preventDefault();
        sound.playClick();
        setIsShortcutsOpen(prev => !prev);
      } else if (e.code === 'KeyF') {
        e.preventDefault();
        sound.playClick();
        if (!document.fullscreenElement) {
          document.documentElement.requestFullscreen().catch(() => {});
        } else {
          document.exitFullscreen().catch(() => {});
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [sessionId, sessionState, isKillSwitchActive, activeTab, engageKillSwitch]);

  return (
    <div
      className={`flex flex-col h-screen w-screen bg-[#05070d] text-slate-100 overflow-hidden font-sans select-none transition-all duration-300 ${
        isKillSwitchActive ? 'kill-switch-active-glow' : ''
      }`}
    >
      {/* 1. Tactical Glass Top Bar */}
      <TopBar onOpenShortcuts={() => setIsShortcutsOpen(true)} />

      {/* 2. Top Warning Strip (Connection Loss / Mock Mode / E-Stop Active) */}
      <ConnectionBanner onRetry={retryNow} />

      {/* 3. Main Operational Centerpiece (Viewport + Tabs Grid) */}
      <main className="flex-1 grid grid-cols-1 xl:grid-cols-[1fr_420px] gap-3 p-3 overflow-hidden min-h-0">
        {/* Left: Live Multi-Mode Viewport */}
        <ViewportWorkspace />

        {/* Right: Telemetry / Trace / Review / Self-Check Tabs */}
        <SidePanelTabs />
      </main>

      {/* 4. Bottom Controls & Emergency Kill Switch Bar */}
      <ControlFooter />

      {/* 5. Mission Constraints Footer Bar */}
      <FooterBar />

      {/* 6. Shortcuts Help Dialog */}
      <ShortcutsModal
        isOpen={isShortcutsOpen}
        onClose={() => setIsShortcutsOpen(false)}
      />
    </div>
  );
};

export default App;
