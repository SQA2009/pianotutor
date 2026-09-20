"""Live signal monitoring: RMS level, peak, clipping, and noise-floor tracking.

Used by the diagnostics/calibration UI to show a level meter and clipping
indicator, and by the recognition pipeline to decide whether a block is
"silence" (skip expensive pitch analysis) or worth analyzing.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class LevelSnapshot:
    rms: float
    peak: float
    is_clipping: bool
    is_silence: bool
    noise_floor_rms: float


class SignalMonitor:
    """Tracks a running noise floor and classifies incoming blocks.

    The noise floor is estimated as a slowly-decaying minimum of the RMS of
    "quiet" blocks, using an exponential moving average that only moves
    *down* quickly but *up* slowly — this way a single quiet block that
    follows a loud passage quickly re-establishes a low floor, while
    transient loud blocks don't drag the floor up.
    """

    def __init__(
        self,
        clipping_threshold: float = 0.98,
        initial_noise_floor_rms: float = 0.01,
        floor_rise_alpha: float = 0.02,
        floor_fall_alpha: float = 0.2,
    ):
        self._clipping_threshold = clipping_threshold
        self._noise_floor_rms = initial_noise_floor_rms
        self._floor_rise_alpha = floor_rise_alpha
        self._floor_fall_alpha = floor_fall_alpha

    @property
    def noise_floor_rms(self) -> float:
        return self._noise_floor_rms

    def process(self, samples: np.ndarray) -> LevelSnapshot:
        if samples.size == 0:
            return LevelSnapshot(0.0, 0.0, False, True, self._noise_floor_rms)

        rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
        peak = float(np.max(np.abs(samples))) if samples.size else 0.0
        is_clipping = peak >= self._clipping_threshold

        if rms < self._noise_floor_rms * 1.5:
            alpha = self._floor_fall_alpha
        else:
            alpha = self._floor_rise_alpha
        # Only let the floor drift toward quieter blocks meaningfully; loud
        # transient blocks barely move it (small alpha in that branch is
        # implicit because such blocks rarely satisfy the `< floor*1.5` test).
        self._noise_floor_rms = (1 - alpha) * self._noise_floor_rms + alpha * min(
            rms, self._noise_floor_rms * 3.0 + 1e-6
        )
        self._noise_floor_rms = max(self._noise_floor_rms, 1e-5)

        is_silence = rms <= self._noise_floor_rms * 2.0

        return LevelSnapshot(
            rms=rms,
            peak=peak,
            is_clipping=is_clipping,
            is_silence=is_silence,
            noise_floor_rms=self._noise_floor_rms,
        )

    def reset(self, initial_noise_floor_rms: float = 0.01) -> None:
        self._noise_floor_rms = initial_noise_floor_rms
