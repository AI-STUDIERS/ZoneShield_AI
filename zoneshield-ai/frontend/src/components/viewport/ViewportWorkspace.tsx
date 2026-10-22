import React from 'react';
import { useTelemetryStore } from '../../store/useStore';
import { ViewportToolbar } from './ViewportToolbar';
import { CanvasViewport } from './CanvasViewport';
import { IsometricViewport } from './IsometricViewport';
import { Mog2MaskViewport } from './Mog2MaskViewport';

export const ViewportWorkspace: React.FC = () => {
  const viewportMode = useTelemetryStore(state => state.viewportMode);

  return (
    <div className="flex-1 flex flex-col h-full min-h-0 bg-[#05070d] rounded-xl border border-white/8 overflow-hidden shadow-2xl">
      {/* Top Viewport Mode Toolbar & Layer Toggles */}
      <ViewportToolbar />

      {/* Main Visual Display */}
      <div className="flex-1 relative w-full h-full min-h-0 p-2">
        {viewportMode === 'radar2d' && <CanvasViewport />}
        {viewportMode === 'iso3d' && <IsometricViewport />}
        {viewportMode === 'mog2' && <Mog2MaskViewport />}
      </div>
    </div>
  );
};
