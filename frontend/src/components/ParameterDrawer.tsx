import React from 'react';
import type { PipelineParameters } from '../types/vision';
import { Sliders } from 'lucide-react';

interface ParameterDrawerProps {
  params: PipelineParameters;
  onChange: (updated: PipelineParameters) => void;
  isOpen: boolean;
  onToggle: () => void;
}

export const ParameterDrawer: React.FC<ParameterDrawerProps> = ({
  params,
  onChange,
  isOpen,
  onToggle
}) => {
  const handleLayerToggle = (layer: keyof typeof params.layers) => {
    onChange({
      ...params,
      layers: {
        ...params.layers,
        [layer]: !params.layers[layer]
      }
    });
  };

  const applyPreset = (preset: 'standard' | 'high_sensitivity' | 'edge_focus') => {
    if (preset === 'standard') {
      onChange({
        ...params,
        confidenceThreshold: 0.70,
        nmsThreshold: 0.45,
        contrast: 1.0,
        brightness: 0,
        cannyLow: 50,
        cannyHigh: 150,
        blurKernel: 3,
        preset: 'standard',
        layers: {
          boxes: true,
          labels: true,
          skeletons: true,
          trajectories: true,
          heatmaps: false,
          opticalFlow: false,
          masks: true,
          jetCone: true
        }
      });
    } else if (preset === 'high_sensitivity') {
      onChange({
        ...params,
        confidenceThreshold: 0.35,
        nmsThreshold: 0.30,
        contrast: 1.3,
        brightness: 10,
        cannyLow: 30,
        cannyHigh: 100,
        blurKernel: 5,
        preset: 'high_sensitivity',
        layers: {
          boxes: true,
          labels: true,
          skeletons: true,
          trajectories: true,
          heatmaps: true,
          opticalFlow: true,
          masks: true,
          jetCone: true
        }
      });
    } else if (preset === 'edge_focus') {
      onChange({
        ...params,
        confidenceThreshold: 0.60,
        nmsThreshold: 0.50,
        contrast: 1.6,
        brightness: -10,
        cannyLow: 75,
        cannyHigh: 200,
        blurKernel: 7,
        preset: 'edge_focus',
        layers: {
          boxes: false,
          labels: true,
          skeletons: true,
          trajectories: true,
          heatmaps: false,
          opticalFlow: true,
          masks: true,
          jetCone: true
        }
      });
    }
  };

  return (
    <aside className={`fixed top-16 right-0 h-[calc(100vh-4rem)] w-80 bg-slate-950/95 backdrop-blur-xl border-l border-cyan-500/20 shadow-2xl shadow-cyan-950/50 z-40 transition-transform duration-300 flex flex-col ${
      isOpen ? 'translate-x-0' : 'translate-x-full'
    }`}>
      {/* Drawer Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Sliders className="w-4 h-4 text-cyan-400" />
          <h2 className="text-sm font-semibold tracking-wider text-slate-100 uppercase font-mono">
            OpenCV Pipeline Tuner
          </h2>
        </div>
        <button
          onClick={onToggle}
          className="text-xs text-slate-400 hover:text-white px-2 py-1 rounded bg-slate-800 border border-slate-700 font-mono"
        >
          ESC
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-6 text-xs font-mono">
        {/* Preset Buttons */}
        <div>
          <label className="text-[11px] uppercase tracking-wider text-slate-400 block mb-2 font-semibold">
            Operational Presets
          </label>
          <div className="grid grid-cols-3 gap-1.5">
            <button
              onClick={() => applyPreset('standard')}
              className={`px-2 py-1.5 rounded border text-[11px] font-semibold transition-all ${
                params.preset === 'standard'
                  ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300 shadow-sm shadow-cyan-500/50'
                  : 'bg-slate-900 border-slate-800 text-slate-400 hover:bg-slate-800'
              }`}
            >
              Standard
            </button>
            <button
              onClick={() => applyPreset('high_sensitivity')}
              className={`px-2 py-1.5 rounded border text-[11px] font-semibold transition-all ${
                params.preset === 'high_sensitivity'
                  ? 'bg-amber-500/20 border-amber-400 text-amber-300 shadow-sm shadow-amber-500/50'
                  : 'bg-slate-900 border-slate-800 text-slate-400 hover:bg-slate-800'
              }`}
            >
              High-Sens
            </button>
            <button
              onClick={() => applyPreset('edge_focus')}
              className={`px-2 py-1.5 rounded border text-[11px] font-semibold transition-all ${
                params.preset === 'edge_focus'
                  ? 'bg-emerald-500/20 border-emerald-400 text-emerald-300 shadow-sm shadow-emerald-500/50'
                  : 'bg-slate-900 border-slate-800 text-slate-400 hover:bg-slate-800'
              }`}
            >
              Edge-Focus
            </button>
          </div>
        </div>

        {/* Inference Thresholds */}
        <div className="space-y-3">
          <label className="text-[11px] uppercase tracking-wider text-slate-400 block font-semibold">
            Inference Thresholds
          </label>

          {/* Confidence */}
          <div>
            <div className="flex justify-between text-slate-300 mb-1">
              <span>Confidence Cutoff:</span>
              <span className="text-cyan-400 font-bold">{Math.round(params.confidenceThreshold * 100)}%</span>
            </div>
            <input
              type="range"
              min="0.1"
              max="0.95"
              step="0.05"
              value={params.confidenceThreshold}
              onChange={(e) => onChange({ ...params, confidenceThreshold: parseFloat(e.target.value) })}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
            />
          </div>

          {/* NMS IoU */}
          <div>
            <div className="flex justify-between text-slate-300 mb-1">
              <span>NMS IoU Overlap:</span>
              <span className="text-cyan-400 font-bold">{params.nmsThreshold.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.1"
              max="0.9"
              step="0.05"
              value={params.nmsThreshold}
              onChange={(e) => onChange({ ...params, nmsThreshold: parseFloat(e.target.value) })}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
            />
          </div>
        </div>

        {/* Image Preprocessing Filters */}
        <div className="space-y-3">
          <label className="text-[11px] uppercase tracking-wider text-slate-400 block font-semibold">
            Pre-Processing Filters
          </label>

          {/* Contrast */}
          <div>
            <div className="flex justify-between text-slate-300 mb-1">
              <span>Contrast (Alpha):</span>
              <span className="text-emerald-400 font-bold">{params.contrast.toFixed(1)}x</span>
            </div>
            <input
              type="range"
              min="0.5"
              max="2.5"
              step="0.1"
              value={params.contrast}
              onChange={(e) => onChange({ ...params, contrast: parseFloat(e.target.value) })}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-emerald-400"
            />
          </div>

          {/* Canny Edge Threshold */}
          <div>
            <div className="flex justify-between text-slate-300 mb-1">
              <span>Canny Hysteresis (High):</span>
              <span className="text-emerald-400 font-bold">{params.cannyHigh}</span>
            </div>
            <input
              type="range"
              min="50"
              max="255"
              step="5"
              value={params.cannyHigh}
              onChange={(e) => onChange({ ...params, cannyHigh: parseInt(e.target.value) })}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-emerald-400"
            />
          </div>

          {/* Gaussian Blur Kernel */}
          <div>
            <div className="flex justify-between text-slate-300 mb-1">
              <span>Gaussian Blur Kernel:</span>
              <span className="text-emerald-400 font-bold">{params.blurKernel}px</span>
            </div>
            <div className="flex gap-2">
              {[0, 3, 5, 7, 9].map((k) => (
                <button
                  key={k}
                  onClick={() => onChange({ ...params, blurKernel: k })}
                  className={`flex-1 py-1 rounded border text-center ${
                    params.blurKernel === k
                      ? 'bg-emerald-500/20 border-emerald-400 text-emerald-300'
                      : 'bg-slate-900 border-slate-800 text-slate-400'
                  }`}
                >
                  {k === 0 ? 'Off' : `${k}x${k}`}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Layer Visibility Toggles */}
        <div className="space-y-2">
          <label className="text-[11px] uppercase tracking-wider text-slate-400 block font-semibold mb-2">
            Active Visual Layers
          </label>

          <div className="space-y-1.5">
            {[
              { key: 'boxes', label: 'Bounding Boxes & Precision Reticles' },
              { key: 'labels', label: 'Class Tags & Confidence Meters' },
              { key: 'skeletons', label: '17-Point Pose Skeleton Bones' },
              { key: 'trajectories', label: 'Kalman Trajectory Ribbons' },
              { key: 'heatmaps', label: 'Motion Density Heatmap' },
              { key: 'opticalFlow', label: 'Optical Flow Vector Field' },
              { key: 'masks', label: 'Semantic Segmentation Masks' }
            ].map(({ key, label }) => (
              <label
                key={key}
                className="flex items-center justify-between p-2 rounded bg-slate-900/60 border border-slate-800/80 hover:border-slate-700 cursor-pointer"
              >
                <span className="text-slate-300">{label}</span>
                <input
                  type="checkbox"
                  checked={params.layers[key as keyof typeof params.layers]}
                  onChange={() => handleLayerToggle(key as keyof typeof params.layers)}
                  className="rounded bg-slate-800 border-slate-700 text-cyan-400 focus:ring-0 cursor-pointer w-4 h-4 accent-cyan-400"
                />
              </label>
            ))}
          </div>
        </div>
      </div>
    </aside>
  );
};
