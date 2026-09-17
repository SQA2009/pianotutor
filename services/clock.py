"""A monotonic clock abstraction.

Using a small interface instead of calling ``time.monotonic()`` directly
throughout the codebase lets tests (and offline/deterministic replays such
as MIDI-only "dry run" scoring) inject a fake clock instead of depending on
wall-clock time.
"""

from __future__ import annotations

import time
from typing import Protocol


class Clock(Protocol):
    """Anything that can report an elapsed, monotonically increasing time."""

    def now_ms(self) -> float:
        """Return the current time in milliseconds. Not tied to wall clock."""
        ...


class SystemClock:
    """Wraps ``time.monotonic()``, the correct clock for real-time audio work."""

    def __init__(self) -> None:
        self._origin = time.monotonic()

    def now_ms(self) -> float:
        return (time.monotonic() - self._origin) * 1000.0


class ManualClock:
    """A clock whose time only advances when explicitly told to.

    Used in tests and in the calibration/practice engines' unit tests to get
    fully deterministic timing without sleeping real time.
    """

    def __init__(self, start_ms: float = 0.0) -> None:
        self._now_ms = start_ms

    def now_ms(self) -> float:
        return self._now_ms

    def advance(self, delta_ms: float) -> None:
        if delta_ms < 0:
            raise ValueError("ManualClock cannot move backwards")
        self._now_ms += delta_ms

    def set(self, now_ms: float) -> None:
        self._now_ms = now_ms
