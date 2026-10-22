import { useSyncExternalStore } from 'react';
import { telemetryStore, type StoreState } from './telemetryStore';

export function useTelemetryStore<T>(selector: (state: StoreState) => T): T {
  return useSyncExternalStore(
    cb => telemetryStore.subscribe(cb),
    () => selector(telemetryStore.getState()),
    () => selector(telemetryStore.getState())
  );
}
