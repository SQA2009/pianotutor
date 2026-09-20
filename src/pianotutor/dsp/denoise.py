"""Lightweight denoising: a noise gate and simple spectral subtraction.

v1 deliberately avoids heavier adaptive-filter or ML-based denoise (that's
explicitly deferred, see the development plan's "richer ML models" note).
These two techniques are cheap, real-time-safe, and materially reduce false
onsets/pitch jitter from room noise and mic self-noise.
"""

from __future__ import annotations

import numpy as np


def noise_gate(samples: np.ndarray, noise_floor_rms: float, ratio: float = 1.5) -> np.ndarray:
    """Zero out ``samples`` entirely if their RMS is close to the noise floor.

    A block-level gate (not sample-level) is intentional: piano transients
    fill an entire ~20ms block if a note was struck within it, so block-RMS
    gating avoids introducing sample-level clicks that would themselves
    create spurious high-frequency onset energy.
    """
    if samples.size == 0:
        return samples
    rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
    if rms < noise_floor_rms * ratio:
        return np.zeros_like(samples)
    return samples


def spectral_subtract(
    magnitudes: np.ndarray, noise_magnitudes: np.ndarray, oversubtraction: float = 1.5
) -> np.ndarray:
    """Subtract an estimated noise spectrum from a signal's magnitude spectrum.

    ``noise_magnitudes`` should be the same length as ``magnitudes`` (e.g. an
    averaged spectrum captured during a silent calibration period). Result is
    floored at zero and never goes negative.
    """
    if magnitudes.shape != noise_magnitudes.shape:
        raise ValueError("magnitudes and noise_magnitudes must have the same shape")
    subtracted = magnitudes - oversubtraction * noise_magnitudes
    return np.clip(subtracted, 0.0, None)
