import React, { useState } from 'react';
import { useTelemetryStore } from '../../store/useStore';
import { telemetryStore } from '../../store/telemetryStore';
import { sound } from '../../utils/audio';
import {
  GitCommit,
  Brain,
  Cpu,
  ChevronDown,
  ChevronRight,
  Filter,
} from 'lucide-react';

export const DecisionTraceTab: React.FC = () => {
  const decisions = useTelemetryStore(state => state.decisions);
  const highlightedTrackId = useTelemetryStore(state => state.highlightedTrackId);

  const [activeFilter, setActiveFilter] = useState<'all' | 'intercept' | 'veto' | 'escalated'>('all');
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null);

  const toggleExpand = (rowKey: string) => {
    sound.playClick();
    setExpandedRowId(prev => (prev === rowKey ? null : rowKey));
  };

  const handleRowClick = (trackId: number) => {
    sound.playClick();
    telemetryStore.setHighlightedTrackId(highlightedTrackId === trackId ? null : trackId);
  };

  const filteredDecisions = decisions.filter(d => {
    if (activeFilter === 'all') return true;
    if (activeFilter === 'intercept') return d.action === 'intercept';
    if (activeFilter === 'veto') return d.reason && d.reason.toLowerCase().includes('veto');
    if (activeFilter === 'escalated') return d.action === 'request_human' || d.tier === '2';
    return true;
  });

  return (
    <div className="flex flex-col h-full overflow-hidden select-none">
      {/* Filter Chips Bar */}
      <div className="flex items-center justify-between p-3 border-b border-white/8 bg-[#0a0f1c]/60">
        <div className="flex items-center gap-1.5">
          <Filter className="w-3.5 h-3.5 text-slate-500 mr-1" />
          {(['all', 'intercept', 'veto', 'escalated'] as const).map(filter => (
            <button
              key={filter}
              onClick={() => {
                sound.playClick();
                setActiveFilter(filter);
              }}
              className={`px-2 py-0.5 rounded text-[11px] font-mono capitalize transition-all ${
                activeFilter === filter
                  ? 'bg-cyan-500/20 border border-cyan-400 text-cyan-300 font-semibold shadow-sm'
                  : 'bg-white/[0.03] border border-white/5 text-slate-400 hover:text-slate-200'
              }`}
            >
              {filter}
            </button>
          ))}
        </div>
        <span className="text-[10px] font-mono text-slate-500">
          {filteredDecisions.length} / {decisions.length} EVENTS
        </span>
      </div>

      {/* Feed List */}
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-2">
        {filteredDecisions.length === 0 ? (
          <div className="py-12 flex flex-col items-center justify-center text-center text-slate-500 font-mono text-xs gap-2">
            <GitCommit className="w-8 h-8 text-slate-600" />
            <span>No decisions recorded matching filter.</span>
            <span className="text-[10px] text-slate-600">Start the belt to begin tracking threats.</span>
          </div>
        ) : (
          filteredDecisions.map((dec, idx) => {
            const rowKey = `${dec.track_id}_${dec.t_ms || idx}_${dec.action}`;
            const isExpanded = expandedRowId === rowKey;
            const isHighlighted = highlightedTrackId === dec.track_id;
            const isTier2 = dec.tier === '2';
            const isIntercept = dec.action === 'intercept';

            return (
              <div
                key={rowKey}
                onClick={() => handleRowClick(dec.track_id)}
                className={`flex flex-col rounded-lg border transition-all cursor-pointer ${
                  isHighlighted
                    ? 'bg-cyan-950/40 border-cyan-400/80 shadow-[0_0_12px_rgba(0,242,255,0.2)]'
                    : 'bg-black/40 border-white/8 hover:border-white/20'
                }`}
              >
                {/* Header Row */}
                <div className="flex items-center justify-between p-2.5">
                  <div className="flex items-center gap-2">
                    {/* Tier Badge */}
                    <span
                      className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-bold ${
                        isTier2
                          ? 'bg-purple-950/80 border border-purple-400 text-purple-300'
                          : 'bg-blue-950/80 border border-blue-400 text-blue-300'
                      }`}
                    >
                      {isTier2 ? <Brain className="w-3 h-3" /> : <Cpu className="w-3 h-3" />}
                      <span>T{dec.tier}</span>
                    </span>

                    {/* Track ID */}
                    <span className="font-mono-num font-bold text-xs text-white">
                      #{dec.track_id}
                    </span>

                    {/* State Transition */}
                    <span className="text-[10px] font-mono text-slate-400">
                      {dec.state_from || 'ASSESSING'} →{' '}
                      <span className="text-white font-semibold">
                        {dec.state_to || (isIntercept ? 'INTERCEPTING' : 'MONITORING')}
                      </span>
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {/* Action Chip */}
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                        isIntercept
                          ? 'bg-red-500/20 border border-red-500/60 text-red-300'
                          : dec.action === 'request_human'
                          ? 'bg-purple-500/20 border border-purple-500/60 text-purple-300'
                          : 'bg-slate-800 border border-slate-700 text-slate-300'
                      }`}
                    >
                      {dec.action}
                    </span>

                    {isTier2 && (
                      <button
                        onClick={e => {
                          e.stopPropagation();
                          toggleExpand(rowKey);
                        }}
                        className="p-1 hover:text-cyan-300 text-slate-400"
                      >
                        {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                      </button>
                    )}
                  </div>
                </div>

                {/* Reason Text & Confidence */}
                <div className="px-2.5 pb-2 text-xs font-mono text-slate-300 flex flex-col gap-1">
                  <p className="text-[11px] text-slate-400 leading-relaxed">{dec.reason}</p>

                  {/* Confidence Bar */}
                  {dec.confidence_before !== undefined && (
                    <div className="flex items-center gap-2 pt-1">
                      <span className="text-[10px] text-slate-500">CONF:</span>
                      <div className="flex-1 h-1.5 rounded-full bg-white/10 overflow-hidden">
                        <div
                          style={{ width: `${(dec.confidence_before || 0) * 100}%` }}
                          className={`h-full ${
                            (dec.confidence_before || 0) >= 0.75
                              ? 'bg-red-500'
                              : (dec.confidence_before || 0) >= 0.40
                              ? 'bg-amber-400'
                              : 'bg-emerald-400'
                          }`}
                        />
                      </div>
                      <span className="font-mono-num text-[10px] font-bold text-slate-200">
                        {((dec.confidence_before || 0) * 100).toFixed(1)}%
                      </span>
                    </div>
                  )}
                </div>

                {/* Expandable Tier 2 Agentic Tool-Call Steps */}
                {isTier2 && isExpanded && (
                  <div className="p-2.5 bg-black/60 border-t border-purple-500/20 flex flex-col gap-2 text-xs font-mono">
                    <span className="text-[10px] font-bold uppercase text-purple-400 tracking-wider">
                      AGENTIC VISION STEPS (AMAZON BEDROCK):
                    </span>
                    <div className="flex flex-col gap-1.5 pl-2 border-l-2 border-purple-500/40">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-slate-300">1. request_more_frames(track_id={dec.track_id})</span>
                        <span className="text-emerald-400 text-[10px]">✔ SUCCESS (+3 frames)</span>
                      </div>
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-slate-300">2. intercept(target_jet=300mm)</span>
                        <span className="text-emerald-400 text-[10px]">✔ AUTHORIZED</span>
                      </div>
                    </div>
                    {dec.confidence_before !== undefined && dec.confidence_after !== undefined && (
                      <div className="flex items-center justify-between text-[11px] pt-1 text-slate-400">
                        <span>Confidence Delta:</span>
                        <span className="text-emerald-400 font-bold font-mono-num">
                          {(dec.confidence_before * 100).toFixed(1)}% → {(dec.confidence_after * 100).toFixed(1)}% (+{((dec.confidence_after - dec.confidence_before) * 100).toFixed(1)}%)
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
