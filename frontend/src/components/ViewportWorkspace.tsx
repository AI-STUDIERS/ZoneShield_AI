import React, { useRef, useState } from 'react';
import type { SourceType, PipelineParameters, Detection } from '../types/vision';
import { useCanvasOverlay } from '../hooks/useCanvasOverlay';
import { 
  Play, Pause, SkipBack, SkipForward, SplitSquareVertical, 
  Upload, Camera, Radio, ZoomIn, ZoomOut, RefreshCw, Crosshair 
} from 'lucide-react';

interface ViewportWorkspaceProps {
  canvasRef: React.RefObject<HTMLCanvasElement | null>;
  videoRef: React.RefObject<HTMLVideoElement | null>;
  detections: Detection[];
  opticalFlowVectors: { x: number; y: number; vx: number; vy: number }[];
  params: PipelineParameters;
  sourceType: SourceType;
  onSourceChange: (source: SourceType) => void;
  onFileUpload: (file: File) => void;
  isPlaying: boolean;
  onTogglePlay: () => void;
  onStepFrame: (direction: 'forward' | 'backward') => void;
  onSnapshot: () => void;
}

export const ViewportWorkspace: React.FC<ViewportWorkspaceProps> = ({
  canvasRef,
  videoRef,
  detections,
  opticalFlowVectors,
  params,
  sourceType,
  onSourceChange,
  onFileUpload,
  isPlaying,
  onTogglePlay,
  onStepFrame,
  onSnapshot
}) => {
  const [isWipeMode, setIsWipeMode] = useState(false);
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const { zoom, setZoom, resetView } = useCanvasOverlay(
    canvasRef,
    videoRef,
    detections,
    opticalFlowVectors,
    params,
    isWipeMode
  );

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDraggingFile(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      onFileUpload(e.dataTransfer.files[0]);
    }
  };

  return (
    <div 
      className="relative flex flex-col flex-1 bg-slate-950 border border-cyan-500/20 rounded-lg overflow-hidden shadow-2xl"
      onDragOver={(e) => { e.preventDefault(); setIsDraggingFile(true); }}
      onDragLeave={() => setIsDraggingFile(false)}
      onDrop={handleDrop}
    >
      {/* Hidden native video element for webcam / uploaded video playback */}
      <video ref={videoRef} playsInline muted className="hidden" />
      <input 
        type="file" 
        ref={fileInputRef} 
        accept="video/*,image/*" 
        className="hidden" 
        onChange={(e) => {
          if (e.target.files && e.target.files[0]) {
            onFileUpload(e.target.files[0]);
          }
        }}
      />

      {/* Viewport Top Bar: Source Selector & View Mode Tools */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-900/90 border-b border-slate-800 z-10">
        {/* Source Switchers */}
        <div className="flex items-center gap-1.5 font-mono text-xs">
          <button
            onClick={() => onSourceChange('synthetic_feed')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded transition-all ${
              sourceType === 'synthetic_feed'
                ? 'bg-cyan-500/20 border border-cyan-400 text-cyan-300'
                : 'bg-slate-950 border border-slate-800 text-slate-400 hover:bg-slate-800'
            }`}
          >
            <Radio className="w-3.5 h-3.5" />
            <span>Simulated Stream</span>
          </button>

          <button
            onClick={() => onSourceChange('webcam')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded transition-all ${
              sourceType === 'webcam'
                ? 'bg-cyan-500/20 border border-cyan-400 text-cyan-300'
                : 'bg-slate-950 border border-slate-800 text-slate-400 hover:bg-slate-800'
            }`}
          >
            <Camera className="w-3.5 h-3.5" />
            <span>Live Webcam</span>
          </button>

          <button
            onClick={() => {
              onSourceChange('video_file');
              fileInputRef.current?.click();
            }}
            className={`flex items-center gap-1.5 px-3 py-1 rounded transition-all ${
              sourceType === 'video_file'
                ? 'bg-cyan-500/20 border border-cyan-400 text-cyan-300'
                : 'bg-slate-950 border border-slate-800 text-slate-400 hover:bg-slate-800'
            }`}
          >
            <Upload className="w-3.5 h-3.5" />
            <span>File Upload</span>
          </button>

          <button
            onClick={() => onSourceChange('websocket_stream')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded transition-all ${
              sourceType === 'websocket_stream'
                ? 'bg-cyan-500/20 border border-cyan-400 text-cyan-300'
                : 'bg-slate-950 border border-slate-800 text-slate-400 hover:bg-slate-800'
            }`}
          >
            <Crosshair className="w-3.5 h-3.5" />
            <span>OpenCV 5 Backend WS</span>
          </button>
        </div>

        {/* View Tools: Wipe Mode & Zoom */}
        <div className="flex items-center gap-2 font-mono text-xs">
          <button
            onClick={() => setIsWipeMode(!isWipeMode)}
            className={`flex items-center gap-1.5 px-3 py-1 rounded border transition-all ${
              isWipeMode
                ? 'bg-indigo-600/30 border-indigo-400 text-indigo-300 shadow-sm shadow-indigo-500/50'
                : 'bg-slate-950 border-slate-800 text-slate-400 hover:bg-slate-800'
            }`}
          >
            <SplitSquareVertical className="w-3.5 h-3.5" />
            <span>Wipe Compare: {isWipeMode ? 'ON' : 'OFF'}</span>
          </button>

          {/* Zoom Indicator */}
          <div className="flex items-center gap-1 px-2.5 py-1 bg-slate-950 border border-slate-800 rounded text-slate-400">
            <span className="text-cyan-400 font-bold">{zoom.toFixed(1)}x</span>
            <button 
              onClick={() => setZoom(prev => Math.min(4.0, prev + 0.2))} 
              className="hover:text-white p-0.5"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button 
              onClick={() => setZoom(prev => Math.max(0.6, prev - 0.2))} 
              className="hover:text-white p-0.5"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <button 
              onClick={resetView} 
              title="Reset Zoom & Pan (Double Click)"
              className="hover:text-white p-0.5 ml-1"
            >
              <RefreshCw className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>

      {/* Canvas Viewport Frame */}
      <div className="relative flex-1 flex items-center justify-center bg-slate-950 overflow-hidden cursor-crosshair">
        <canvas
          ref={canvasRef}
          width={1280}
          height={720}
          className="max-w-full max-h-full object-contain shadow-2xl"
        />

        {/* Drag & Drop Overlay */}
        {isDraggingFile && (
          <div className="absolute inset-0 bg-cyan-950/80 backdrop-blur-sm border-2 border-dashed border-cyan-400 flex flex-col items-center justify-center text-cyan-300 font-mono text-sm pointer-events-none z-30">
            <Upload className="w-12 h-12 mb-3 animate-bounce" />
            <p className="font-bold">DROP VIDEO OR IMAGE FILE HERE</p>
            <p className="text-xs text-slate-400 mt-1">Supports MP4, WebM, PNG, JPG for OpenCV inference</p>
          </div>
        )}
      </div>

      {/* Transport Bar & Scrubber */}
      <div className="flex items-center justify-between px-5 py-3 bg-slate-900/90 border-t border-slate-800 z-10 font-mono text-xs">
        {/* Playback Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={onTogglePlay}
            className={`flex items-center gap-1.5 px-4 py-1.5 rounded font-bold transition-all ${
              isPlaying 
                ? 'bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-md shadow-amber-500/20' 
                : 'bg-cyan-500 hover:bg-cyan-400 text-slate-950 shadow-md shadow-cyan-500/20'
            }`}
          >
            {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            <span>{isPlaying ? 'PAUSE' : 'PLAY'}</span>
          </button>

          <button
            onClick={() => onStepFrame('backward')}
            title="Step Back 1 Frame ([)"
            className="p-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 rounded"
          >
            <SkipBack className="w-4 h-4" />
          </button>

          <button
            onClick={() => onStepFrame('forward')}
            title="Step Forward 1 Frame (])"
            className="p-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 rounded"
          >
            <SkipForward className="w-4 h-4" />
          </button>
        </div>

        {/* Viewport Hints */}
        <div className="hidden md:flex items-center gap-4 text-slate-500 text-[11px]">
          <span>Scroll: <strong className="text-slate-400">Zoom</strong></span>
          <span>Drag: <strong className="text-slate-400">Pan</strong></span>
          <span>Dbl-Click: <strong className="text-slate-400">Reset</strong></span>
          <span>Space: <strong className="text-slate-400">Play/Pause</strong></span>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={onSnapshot}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-cyan-300 rounded font-semibold transition-colors"
          >
            Snapshot (S)
          </button>
        </div>
      </div>
    </div>
  );
};
