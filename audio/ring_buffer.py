"""A bounded, thread-safe float32 ring buffer for audio samples.

One producer (the audio callback thread) calls :meth:`write`; one or more
consumers (recognition worker, level monitor) call :meth:`read_latest` /
:meth:`read_since`. All operations hold a lock only long enough to copy
fixed-size numpy slices, so contention is minimal and bounded — there is no
unbounded work and no I/O under the lock, keeping this safe to call from
code adjacent to the real-time audio callback (the callback itself only
calls :meth:`write`).
"""

from __future__ import annotations

import threading

import numpy as np


class RingBuffer:
    """Fixed-capacity circular buffer of mono float32 samples."""

    def __init__(self, capacity_samples: int):
        if capacity_samples <= 0:
            raise ValueError("capacity_samples must be positive")
        self._capacity = capacity_samples
        self._buffer = np.zeros(capacity_samples, dtype=np.float32)
        self._write_pos = 0  # next index to write to
        self._total_written = 0  # monotonically increasing count of samples ever written
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        return self._capacity

    def write(self, samples: np.ndarray) -> None:
        """Append ``samples`` (1-D float32 array), overwriting the oldest data if full."""
        samples = np.asarray(samples, dtype=np.float32).reshape(-1)
        n = samples.shape[0]
        if n == 0:
            return

        with self._lock:
            if n >= self._capacity:
                # Larger than the whole buffer: keep only the most recent `capacity` samples.
                self._buffer[:] = samples[-self._capacity :]
                self._write_pos = 0
            else:
                end = self._write_pos + n
                if end <= self._capacity:
                    self._buffer[self._write_pos:end] = samples
                else:
                    first_part = self._capacity - self._write_pos
                    self._buffer[self._write_pos:] = samples[:first_part]
                    self._buffer[: end - self._capacity] = samples[first_part:]
                self._write_pos = end % self._capacity
            self._total_written += n

    def total_written(self) -> int:
        with self._lock:
            return self._total_written

    def read_latest(self, n: int) -> np.ndarray:
        """Return the most recent ``n`` samples (oldest-to-newest order).

        If fewer than ``n`` samples have ever been written, the result is
        zero-padded at the front.
        """
        if n <= 0:
            return np.zeros(0, dtype=np.float32)
        n = min(n, self._capacity)

        with self._lock:
            available = min(self._total_written, self._capacity)
            write_pos = self._write_pos
            buffer_copy_start = (write_pos - n) % self._capacity
            if buffer_copy_start + n <= self._capacity:
                data = self._buffer[buffer_copy_start:buffer_copy_start + n].copy()
            else:
                first_part = self._capacity - buffer_copy_start
                data = np.concatenate(
                    (
                        self._buffer[buffer_copy_start:],
                        self._buffer[: n - first_part],
                    )
                )

        valid = min(n, available)
        if valid < n:
            padded = np.zeros(n, dtype=np.float32)
            padded[-valid:] = data[-valid:] if valid > 0 else data[:0]
            return padded
        return data

    def clear(self) -> None:
        with self._lock:
            self._buffer[:] = 0
            self._write_pos = 0
            self._total_written = 0
