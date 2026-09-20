"""Spectral-flux based onset (note-start) detection.

Classic, lightweight approach well suited to v1: compute the magnitude
spectrum of each block, sum the positive-only frame-to-frame increase in
each bin ("spectral flux"), and flag an onset when that flux exceeds an
adaptive threshold (local mean + a multiple of local standard deviation)
and enough time has passed since the last onset (refractory period) to
avoid re-triggering on a single note's amplitude envelope ripple.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

from pianotutor.dsp.spectrum import compute_magnitude_spectrum


@dataclass(frozen=True)
class OnsetResult:
    is_onset: bool
    flux: float
    threshold: float


class OnsetDetector:
    """Stateful, block-by-block spectral flux onset detector."""

    def __init__(
        self,
        sample_rate: int,
        history_len: int = 43,  # ~1s at ~23ms blocks
        sensitivity: float = 1.6,  # threshold = mean + sensitivity * stddev
        min_flux_floor: float = 1e-3,
        refractory_ms: float = 60.0,
    ):
        self._sample_rate = sample_rate
        self._history: deque[float] = deque(maxlen=history_len)
        self._prev_magnitudes: np.ndarray | None = None
        self._sensitivity = sensitivity
        self._min_flux_floor = min_flux_floor
        self._refractory_ms = refractory_ms
        self._last_onset_t_ms: float | None = None

    def reset(self) -> None:
        self._history.clear()
        self._prev_magnitudes = None
        self._last_onset_t_ms = None

    def process(self, samples: np.ndarray, t_ms: float) -> OnsetResult:
        spectrum = compute_magnitude_spectrum(samples, self._sample_rate)
        magnitudes = spectrum.magnitudes

        if magnitudes.size == 0:
            return OnsetResult(False, 0.0, 0.0)

        if self._prev_magnitudes is None or self._prev_magnitudes.shape != magnitudes.shape:
            self._prev_magnitudes = magnitudes
            self._history.append(0.0)
            return OnsetResult(False, 0.0, 0.0)

        diff = magnitudes - self._prev_magnitudes
        flux = float(np.sum(diff[diff > 0]))
        self._prev_magnitudes = magnitudes

        if len(self._history) >= 3:
            hist = np.array(self._history)
            threshold = float(np.mean(hist) + self._sensitivity * np.std(hist))
        else:
            threshold = self._min_flux_floor
        threshold = max(threshold, self._min_flux_floor)

        self._history.append(flux)

        in_refractory = (
            self._last_onset_t_ms is not None
            and (t_ms - self._last_onset_t_ms) < self._refractory_ms
        )
        is_onset = flux > threshold and not in_refractory

        if is_onset:
            self._last_onset_t_ms = t_ms

        return OnsetResult(is_onset=is_onset, flux=flux, threshold=threshold)
