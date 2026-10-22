import React, { useState, useRef, useEffect } from 'react';
import type { SourceType, PipelineParameters } from './types/vision';
import { useOpenCVStream } from './hooks/useOpenCVStream';
import { HeaderNav } from './components/HeaderNav';
import { TelemetryHUD } from './components/TelemetryHUD';
import { ViewportWorkspace } from './components/ViewportWorkspace';
import { DetectionsEventFeed } from './components/DetectionsEventFeed';
import { ParameterDrawer } from './components/ParameterDrawer';
import { sound } from './utils/audio';

export const App: React.FC = () => {
  const [sourceType, setSourceType] = useState<SourceType>('synthetic_feed');
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);
  const [uptimeSeconds, setUptimeSeconds] = useState<number>(0);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Pipeline configuration state
  const [params, setParams] = useState<PipelineParameters>({
    confidenceThreshold: 0.65,
    nmsThreshold: 0.45,
    contrast: 1.0,
    brightness: 0,
    cannyLow: 50,
    cannyHigh: 150,
    blurKernel: 3,
    hsvMin: [0, 0, 0],
    hsvMax: [180, 255, 255],
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

  // OpenCV Vision Stream Hook
  const { videoRef, detections, opticalFlowVectors, telemetry } = useOpenCVStream(
    sourceType,
    uploadedFile,
    params,
    isPlaying
  );

  // Uptime ticker
  useEffect(() => {
    const timer = setInterval(() => {
      setUptimeSeconds(prev => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Export PNG Snapshot
  const handleExportPng = () => {
    sound.playBeep(880, 'sine', 0.1);
    if (!canvasRef.current) return;
    const url = canvasRef.current.toDataURL('image/png');
    const a = document.createElement('a');
    a.href = url;
    a.download = `opencv_frame_${Date.now()}.png`;
    a.click();
  };

  // Export JSON Telemetry Log
  const handleExportJson = () => {
    sound.playBeep(660, 'sine', 0.1);
    const data = {
      telemetry,
      params,
      activeDetections: detections,
      timestamp: new Date().toISOString()
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `telemetry_audit_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Export CSV Report
  const handleExportCsv = () => {
    sound.playBeep(660, 'sine', 0.1);
    const headers = ['id', 'class', 'confidence', 'x', 'y', 'w', 'h', 'ttiMs'];
    const rows = detections.map(d => [
      d.id,
      d.class,
      (d.confidence * 100).toFixed(1) + '%',
      d.bbox.x.toFixed(1),
      d.bbox.y.toFixed(1),
      d.bbox.w.toFixed(1),
      d.bbox.h.toFixed(1),
      d.ttiMs || 'N/A'
    ]);
    const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `detections_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Global Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      if (e.code === 'Space') {
        e.preventDefault();
        setIsPlaying(prev => !prev);
        sound.playBeep(440, 'sine', 0.05);
      } else if (e.code === 'KeyS') {
        e.preventDefault();
        handleExportPng();
      } else if (e.code === 'KeyF') {
        e.preventDefault();
        if (!document.fullscreenElement) {
          document.documentElement.requestFullscreen().catch(() => {});
        } else {
          document.exitFullscreen().catch(() => {});
        }
      } else if (e.code === 'BracketLeft') {
        setIsPlaying(false);
      } else if (e.code === 'BracketRight') {
        setIsPlaying(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden font-sans select-none">
      {/* Top Header */}
      <HeaderNav
        onToggleDrawer={() => setIsDrawerOpen(prev => !prev)}
        isDrawerOpen={isDrawerOpen}
      />

      {/* Main Workspace Frame */}
      <div className="flex-1 flex flex-col p-4 gap-3 overflow-hidden">
        {/* Floating Telemetry HUD */}
        <TelemetryHUD
          telemetry={telemetry}
          uptimeSeconds={uptimeSeconds}
        />

        {/* Viewport Centerpiece & Side Feed Grid */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4 min-h-0">
          <ViewportWorkspace
            canvasRef={canvasRef}
            videoRef={videoRef}
            detections={detections}
            opticalFlowVectors={opticalFlowVectors}
            params={params}
            sourceType={sourceType}
            onSourceChange={setSourceType}
            onFileUpload={(file) => {
              setUploadedFile(file);
              setSourceType('video_file');
              sound.playBeep(520, 'sine', 0.1);
            }}
            isPlaying={isPlaying}
            onTogglePlay={() => {
              setIsPlaying(prev => !prev);
              sound.playBeep(480, 'sine', 0.06);
            }}
            onStepFrame={() => setIsPlaying(false)}
            onSnapshot={handleExportPng}
          />

          <DetectionsEventFeed
            detections={detections}
            onExportPng={handleExportPng}
            onExportJson={handleExportJson}
            onExportCsv={handleExportCsv}
          />
        </div>
      </div>

      {/* Live OpenCV Parameter Tuner Drawer */}
      <ParameterDrawer
        params={params}
        onChange={setParams}
        isOpen={isDrawerOpen}
        onToggle={() => setIsDrawerOpen(false)}
      />
    </div>
  );
};

export default App;
