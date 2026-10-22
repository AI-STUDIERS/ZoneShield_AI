import React, { useState } from 'react';
import type { Detection } from '../types/vision';
import { Download, Search, ShieldAlert, CheckCircle, Crosshair, FileJson, FileSpreadsheet } from 'lucide-react';

interface DetectionsEventFeedProps {
  detections: Detection[];
  onExportPng: () => void;
  onExportJson: () => void;
  onExportCsv: () => void;
}

export const DetectionsEventFeed: React.FC<DetectionsEventFeedProps> = ({
  detections,
  onExportPng,
  onExportJson,
  onExportCsv
}) => {
  const [filterQuery, setFilterQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<'all' | 'person' | 'threat' | 'anomaly'>('all');

  const filteredDetections = detections.filter(d => {
    const matchesQuery = d.class.toLowerCase().includes(filterQuery.toLowerCase()) || String(d.id).includes(filterQuery);
    if (!matchesQuery) return false;
    if (selectedCategory === 'all') return true;
    if (selectedCategory === 'person') return d.class === 'person';
    if (selectedCategory === 'threat') return d.class.includes('threat') || d.isAnomaly;
    if (selectedCategory === 'anomaly') return d.isAnomaly;
    return true;
  });

  return (
    <div className="flex flex-col h-full bg-slate-950/80 backdrop-blur-md border border-cyan-500/20 rounded-lg overflow-hidden shadow-xl">
      {/* Feed Header */}
      <div className="px-4 py-3 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Crosshair className="w-4 h-4 text-cyan-400" />
          <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200">
            Detections Stream & Event Log
          </h3>
          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-cyan-950/60 border border-cyan-500/30 text-cyan-400">
            {filteredDetections.length} LIVE
          </span>
        </div>

        {/* Quick Export Tools */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={onExportPng}
            title="Download Canvas Snapshot (PNG)"
            className="flex items-center gap-1 px-2 py-1 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 rounded text-[11px] font-mono transition-colors"
          >
            <Download className="w-3 h-3 text-cyan-400" />
            <span>PNG</span>
          </button>
          <button
            onClick={onExportJson}
            title="Export Telemetry Log (JSON)"
            className="flex items-center gap-1 px-2 py-1 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 rounded text-[11px] font-mono transition-colors"
          >
            <FileJson className="w-3 h-3 text-amber-400" />
            <span>JSON</span>
          </button>
          <button
            onClick={onExportCsv}
            title="Export Detection Log (CSV)"
            className="flex items-center gap-1 px-2 py-1 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 rounded text-[11px] font-mono transition-colors"
          >
            <FileSpreadsheet className="w-3 h-3 text-emerald-400" />
            <span>CSV</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-3 bg-slate-900/40 border-b border-slate-800 flex flex-col gap-2">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
          <input
            type="text"
            placeholder="Search by ID or Class..."
            value={filterQuery}
            onChange={(e) => setFilterQuery(e.target.value)}
            className="w-full bg-slate-950/90 border border-slate-800 rounded pl-8 pr-3 py-1.5 text-xs font-mono text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
          />
        </div>

        <div className="flex gap-1.5 text-[11px] font-mono">
          {(['all', 'person', 'threat', 'anomaly'] as const).map(cat => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-2.5 py-1 rounded capitalize transition-all ${
                selectedCategory === cat
                  ? 'bg-cyan-500/20 border border-cyan-400 text-cyan-300'
                  : 'bg-slate-900 border border-slate-800 text-slate-400 hover:bg-slate-800'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Scrollable Event List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {filteredDetections.length === 0 ? (
          <div className="text-center py-8 text-xs font-mono text-slate-500">
            No active targets matching criteria
          </div>
        ) : (
          filteredDetections.map((det) => {
            const isThreat = det.isAnomaly || det.class.includes('threat');
            return (
              <div
                key={det.id}
                className={`p-2.5 rounded border transition-all ${
                  isThreat
                    ? 'bg-rose-950/20 border-rose-500/40 hover:border-rose-500'
                    : 'bg-slate-900/60 border-slate-800 hover:border-cyan-500/40'
                }`}
              >
                <div className="flex items-center justify-between font-mono text-xs mb-1">
                  <div className="flex items-center gap-1.5">
                    {isThreat ? (
                      <ShieldAlert className="w-3.5 h-3.5 text-rose-400 animate-pulse" />
                    ) : (
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                    )}
                    <span className="font-bold text-slate-200 uppercase">{det.class}</span>
                    <span className="text-slate-500 text-[10px]">#{det.id}</span>
                  </div>
                  <span className={`font-semibold ${isThreat ? 'text-rose-400' : 'text-cyan-400'}`}>
                    {Math.round(det.confidence * 100)}% CONF
                  </span>
                </div>

                <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                  <span>
                    BBOX: [{Math.round(det.bbox.x)}, {Math.round(det.bbox.y)}, {Math.round(det.bbox.w)}, {Math.round(det.bbox.h)}]
                  </span>
                  {det.ttiMs && (
                    <span className="text-rose-400 font-bold bg-rose-950/50 px-1 rounded">
                      TTI: {det.ttiMs}ms
                    </span>
                  )}
                </div>

                {det.velocity && (
                  <div className="mt-1 text-[10px] font-mono text-slate-500 flex justify-between">
                    <span>VEL: [{det.velocity[0].toFixed(1)}, {det.velocity[1].toFixed(1)}] px/s</span>
                    <span className="text-emerald-400">TRACKING_ACTIVE</span>
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
