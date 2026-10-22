import React, { useState, useEffect } from 'react';
import { useTelemetryStore } from '../../store/useStore';
import { telemetryStore } from '../../store/telemetryStore';
import { api } from '../../api/client';
import { sound } from '../../utils/audio';
import {
  Inbox,
  CheckCircle,
  XCircle,
  PlusCircle,
  Clock,
  AlertTriangle,
} from 'lucide-react';
import type { ReviewItemData } from '../../types/telemetry';

export const ReviewQueueTab: React.FC = () => {
  const reviewQueue = useTelemetryStore(state => state.reviewQueue);
  const [activeCropIndex] = useState(0);
  const [confirmingApproveId, setConfirmingApproveId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [nowMs, setNowMs] = useState(Date.now());

  // Deadline countdown timer ticker
  useEffect(() => {
    const timer = setInterval(() => {
      setNowMs(Date.now());
    }, 200);
    return () => clearInterval(timer);
  }, []);

  const pendingItems = reviewQueue.filter(item => item.status === 'pending');

  const handleResolve = async (
    item: ReviewItemData,
    status: 'APPROVED' | 'DISMISSED' | 'MORE_EVIDENCE'
  ) => {
    sound.playClick();
    setIsSubmitting(true);
    try {
      await api.resolveReview(item.id, status, 'Operator-1', `Human review operator selected ${status}`);
      telemetryStore.resolveReviewItem(
        item.id,
        status === 'APPROVED' ? 'approved' : status === 'DISMISSED' ? 'dismissed' : 'more_evidence'
      );
      setConfirmingApproveId(null);
    } catch (err) {
      console.error('[ReviewQueue] Resolve error:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col h-full overflow-hidden select-none">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-white/8 bg-[#0a0f1c]/60">
        <div className="flex items-center gap-2">
          <Inbox className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-mono font-bold tracking-wider uppercase text-white">
            HUMAN-IN-THE-LOOP REVIEW QUEUE
          </span>
        </div>
        <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-purple-950/60 border border-purple-500/40 text-purple-300 font-bold">
          {pendingItems.length} PENDING
        </span>
      </div>

      {/* Review Item Cards List */}
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
        {pendingItems.length === 0 ? (
          <div className="py-12 flex flex-col items-center justify-center text-center text-slate-500 font-mono text-xs gap-2">
            <CheckCircle className="w-8 h-8 text-emerald-500/60" />
            <span className="text-slate-300 font-medium">Review queue clear</span>
            <span className="text-[10px] text-slate-500">
              Ambiguous threats will be escalated here for operator validation.
            </span>
          </div>
        ) : (
          pendingItems.map(item => {
            const timeLeftMs = Math.max(0, item.deadline_ms - nowMs);
            const isExpired = timeLeftMs <= 0;
            const progressPct = Math.min(100, Math.max(0, (timeLeftMs / 10000) * 100));
            const isConfirming = confirmingApproveId === item.id;

            return (
              <div
                key={item.id}
                className={`flex flex-col rounded-xl border transition-all ${
                  isExpired
                    ? 'bg-slate-900/40 border-slate-700/40 opacity-60'
                    : 'bg-black/50 border-white/10 hover:border-cyan-500/30 shadow-lg'
                }`}
              >
                {/* Item Top Bar */}
                <div className="flex items-center justify-between p-3 border-b border-white/5">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
                    <span className="font-mono text-xs font-bold text-white">
                      REVIEW ITEM #{item.id.substring(0, 8)}
                    </span>
                  </div>

                  {/* Deadline Countdown Ring / Chip */}
                  <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-black/60 border border-white/10 text-[10px] font-mono">
                    <Clock className={`w-3 h-3 ${isExpired ? 'text-red-400' : 'text-amber-400'}`} />
                    <span
                      className={`font-bold font-mono-num ${
                        isExpired
                          ? 'text-red-400'
                          : timeLeftMs < 3000
                          ? 'text-red-400 animate-pulse'
                          : 'text-amber-300'
                      }`}
                    >
                      {isExpired ? 'EXPIRED → MONITOR' : `${(timeLeftMs / 1000).toFixed(1)}s`}
                    </span>
                  </div>
                </div>

                {/* Deadline progress indicator */}
                <div className="w-full bg-slate-950/80 h-1 overflow-hidden">
                  <div
                    className={`h-full transition-all duration-200 ${
                      isExpired ? 'bg-red-500/50' : timeLeftMs < 3000 ? 'bg-red-500' : 'bg-amber-400'
                    }`}
                    style={{ width: `${progressPct}%` }}
                  />
                </div>

                {/* Evidence Crop Carousel & Recommendation */}
                <div className="p-3 flex flex-col gap-2.5">
                  {/* Evidence Crop Visual Area */}
                  <div className="relative w-full h-32 rounded-lg bg-slate-950 border border-white/8 overflow-hidden flex items-center justify-center">
                    <div className="flex flex-col items-center justify-center text-slate-500 text-xs font-mono gap-1">
                      <div className="w-16 h-16 rounded bg-slate-900 border border-cyan-500/30 flex items-center justify-center">
                        <span className="text-cyan-400 font-bold text-xs font-mono">CROP #{activeCropIndex + 1}</span>
                      </div>
                      <span className="text-[10px] text-slate-400">Multi-Angle High-Speed Ingest Frame</span>
                    </div>

                    <div className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded bg-black/80 text-[10px] font-mono text-slate-400">
                      FRAME {activeCropIndex + 1} OF 3
                    </div>
                  </div>

                  {/* Recommendation Text */}
                  <div className="flex flex-col gap-1 text-xs font-mono">
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider">
                      AGENT RECOMMENDATION:
                    </span>
                    <p className="text-slate-200 text-xs leading-relaxed bg-white/[0.02] p-2 rounded border border-white/5">
                      {item.recommendation}
                    </p>
                  </div>

                  {/* Approve Confirmation Warning Panel */}
                  {isConfirming && (
                    <div className="p-2.5 rounded-lg bg-red-950/40 border border-red-500/40 flex flex-col gap-2 text-xs font-mono">
                      <div className="flex items-center gap-1.5 text-red-300 font-bold">
                        <AlertTriangle className="w-4 h-4 text-red-400" />
                        <span>AUTHORIZE SIMULATED INTERCEPTION?</span>
                      </div>
                      <p className="text-[11px] text-red-200/80">
                        Confirming will route track to G1-G5 guardrail safety checks and arm simulated air-jet deflection.
                      </p>
                      <div className="flex items-center gap-2 pt-1">
                        <button
                          onClick={() => handleResolve(item, 'APPROVED')}
                          disabled={isSubmitting}
                          className="flex-1 py-1 rounded bg-red-600 hover:bg-red-500 text-white font-bold text-xs font-mono transition-colors"
                        >
                          CONFIRM APPROVE
                        </button>
                        <button
                          onClick={() => setConfirmingApproveId(null)}
                          className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-mono"
                        >
                          CANCEL
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Action Buttons (when not confirming) */}
                  {!isConfirming && !isExpired && (
                    <div className="flex items-center gap-2 pt-1">
                      <button
                        onClick={() => setConfirmingApproveId(item.id)}
                        className="flex-1 flex items-center justify-center gap-1 py-1.5 rounded-lg bg-red-500/20 hover:bg-red-500/30 border border-red-500/50 text-red-300 font-mono text-xs font-bold transition-all"
                      >
                        <CheckCircle className="w-3.5 h-3.5" />
                        <span>APPROVE</span>
                      </button>

                      <button
                        onClick={() => handleResolve(item, 'DISMISSED')}
                        className="flex-1 flex items-center justify-center gap-1 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 border border-white/10 text-slate-300 font-mono text-xs font-medium transition-all"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        <span>DISMISS</span>
                      </button>

                      <button
                        onClick={() => handleResolve(item, 'MORE_EVIDENCE')}
                        className="flex-1 flex items-center justify-center gap-1 py-1.5 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/50 text-purple-300 font-mono text-xs font-medium transition-all"
                      >
                        <PlusCircle className="w-3.5 h-3.5" />
                        <span>EVIDENCE</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
