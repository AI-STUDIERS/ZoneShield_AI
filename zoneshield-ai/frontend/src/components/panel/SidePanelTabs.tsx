import React from 'react';
import { useTelemetryStore } from '../../store/useStore';
import { telemetryStore, type TabId } from '../../store/telemetryStore';
import { sound } from '../../utils/audio';
import { TelemetryTab } from '../telemetry/TelemetryTab';
import { DecisionTraceTab } from '../trace/DecisionTraceTab';
import { ReviewQueueTab } from '../review/ReviewQueueTab';
import { SystemSelfCheckTab } from '../selfcheck/SystemSelfCheckTab';
import { Activity, GitCommit, Inbox, ShieldCheck } from 'lucide-react';

export const SidePanelTabs: React.FC = () => {
  const activeTab = useTelemetryStore(state => state.activeTab);
  const reviewQueue = useTelemetryStore(state => state.reviewQueue);
  const pendingCount = reviewQueue.filter(i => i.status === 'pending').length;

  const setTab = (tab: TabId) => {
    sound.playClick();
    telemetryStore.setActiveTab(tab);
  };

  return (
    <div className="flex flex-col h-full bg-[#0a0f1c]/90 rounded-xl border border-white/8 overflow-hidden shadow-2xl">
      {/* Tab Navigation Header */}
      <div className="flex items-center border-b border-white/8 bg-black/40 px-2 pt-2 select-none">
        {/* TELEMETRY */}
        <button
          onClick={() => setTab('telemetry')}
          className={`flex items-center gap-1.5 px-3 py-2 text-xs font-mono font-medium border-b-2 transition-all ${
            activeTab === 'telemetry'
              ? 'border-cyan-400 text-cyan-300 font-bold bg-white/[0.03]'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          <span>TELEMETRY</span>
        </button>

        {/* DECISION TRACE */}
        <button
          onClick={() => setTab('trace')}
          className={`flex items-center gap-1.5 px-3 py-2 text-xs font-mono font-medium border-b-2 transition-all ${
            activeTab === 'trace'
              ? 'border-cyan-400 text-cyan-300 font-bold bg-white/[0.03]'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <GitCommit className="w-3.5 h-3.5" />
          <span>TRACE</span>
        </button>

        {/* REVIEW QUEUE */}
        <button
          onClick={() => setTab('review')}
          className={`flex items-center gap-1.5 px-3 py-2 text-xs font-mono font-medium border-b-2 transition-all ${
            activeTab === 'review'
              ? 'border-cyan-400 text-cyan-300 font-bold bg-white/[0.03]'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Inbox className="w-3.5 h-3.5" />
          <span>REVIEW</span>
          {pendingCount > 0 && (
            <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-purple-500/30 text-purple-300 border border-purple-400">
              {pendingCount}
            </span>
          )}
        </button>

        {/* SELF-CHECK */}
        <button
          onClick={() => setTab('selfcheck')}
          className={`flex items-center gap-1.5 px-3 py-2 text-xs font-mono font-medium border-b-2 transition-all ${
            activeTab === 'selfcheck'
              ? 'border-cyan-400 text-cyan-300 font-bold bg-white/[0.03]'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>SELF-CHECK</span>
        </button>
      </div>

      {/* Tab Content Body */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {activeTab === 'telemetry' && <TelemetryTab />}
        {activeTab === 'trace' && <DecisionTraceTab />}
        {activeTab === 'review' && <ReviewQueueTab />}
        {activeTab === 'selfcheck' && <SystemSelfCheckTab />}
      </div>
    </div>
  );
};
