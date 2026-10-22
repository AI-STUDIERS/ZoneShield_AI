"""Shared-memory frame ring buffer.

Keeps the LATEST frames and drops stale ones. A dropped-frame counter
is exported for observability. Single producer (ingest), single consumer
(vision worker) per session.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class RingBufferFrame:
    """A frame stored in the ring buffer."""
    image: np.ndarray
    t_capture_ms: float
    seq: int
    source_id: str


class FrameRingBuffer:
    """Thread-safe ring buffer that retains only the latest frame.

    Designed for the vision pipeline where stale frames should be dropped
    rather than queued, keeping latency bounded.
    """

    def __init__(self, capacity: int = 1) -> None:
        self._capacity = max(1, capacity)
        self._buffer: list[Optional[RingBufferFrame]] = [None] * self._capacity
        self._write_idx = 0
        self._lock = threading.Lock()
        self._dropped_frames = 0
        self._total_written = 0
        self._condition = threading.Condition(self._lock)

    def write(self, image: np.ndarray, t_capture_ms: float, seq: int, source_id: str) -> None:
        """Write a new frame, overwriting the oldest if full."""
        frame = RingBufferFrame(
            image=image.copy(),
            t_capture_ms=t_capture_ms,
            seq=seq,
            source_id=source_id,
        )
        with self._lock:
            self._buffer[self._write_idx] = frame
            self._write_idx = (self._write_idx + 1) % self._capacity
            self._total_written += 1
            if self._capacity == 1:
                # Single slot: every write after the first drops the previous
                if self._total_written > 1:
                    self._dropped_frames += 1
            self._condition.notify_all()

    def read_latest(self, timeout_s: Optional[float] = None) -> Optional[RingBufferFrame]:
        """Read the latest frame. Blocks until one is available or timeout."""
        with self._condition:
            if self._buffer[self._write_idx - 1] is None and self._total_written == 0:
                if timeout_s is None:
                    self._condition.wait()
                else:
                    self._condition.wait(timeout=timeout_s)
            # Return the most recently written slot
            idx = (self._write_idx - 1) % self._capacity
            return self._buffer[idx]

    def read_all(self) -> list[RingBufferFrame]:
        """Return all non-None frames in the buffer (newest first)."""
        with self._lock:
            frames = [f for f in self._buffer if f is not None]
            frames.sort(key=lambda f: f.seq, reverse=True)
            return frames

    @property
    def dropped_frames(self) -> int:
        with self._lock:
            return self._dropped_frames

    @property
    def total_written(self) -> int:
        with self._lock:
            return self._total_written

    def reset(self) -> None:
        with self._lock:
            self._buffer = [None] * self._capacity
            self._write_idx = 0
            self._dropped_frames = 0
            self._total_written = 0