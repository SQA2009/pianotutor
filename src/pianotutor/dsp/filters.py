"""Basic signal-conditioning filters shared by onset detection and pitch tracking.

All filters are implemented as small, stateless (per-call) IIR designs via
``scipy.signal`` operating on a single block. For v1 this is simpler and
"good enough": blocks are short (tens of ms) and filters have short enough
impulse responses that block-boundary transients are negligible relative to
the ~50-2000ms note durations we're trying to detect. If continuous-state
filtering across blocks becomes necessary, this module would grow ``sosfilt``
with saved filter state — everything here is already ``sosfilt``-based so
extending to statefulness is a small, isolated change (not a redesign).
"""

from __future__ import annotations

import numpy as np
from scipy import signal

# Standard 88-key piano range, A0 to C8, with a little headroom on each side.
PIANO_MIN_FREQ_HZ = 24.0
PIANO_MAX_FREQ_HZ = 4300.0


def dc_block(samples: np.ndarray, sample_rate: int, cutoff_hz: float = 20.0) -> np.ndarray:
    """Remove DC offset / sub-audio rumble with a gentle high-pass filter."""
    if samples.size == 0:
        return samples
    sos = signal.butter(2, cutoff_hz, btype="highpass", fs=sample_rate, output="sos")
    return signal.sosfilt(sos, samples).astype(np.float32)


def piano_bandpass(
    samples: np.ndarray,
    sample_rate: int,
    low_hz: float = PIANO_MIN_FREQ_HZ,
    high_hz: float = PIANO_MAX_FREQ_HZ,
) -> np.ndarray:
    """Band-limit audio to the piano's fundamental frequency range.

    This doesn't remove harmonic content above ``high_hz`` from a piano
    note's overtone series (that content matters for pitch/chord features),
    but it does remove out-of-instrument-range rumble and hiss that would
    otherwise contribute to false onsets/noise-floor inflation.
    """
    if samples.size == 0:
        return samples
    nyquist = sample_rate / 2.0
    high = min(high_hz, nyquist * 0.99)
    low = max(low_hz, 1.0)
    sos = signal.butter(4, [low, high], btype="bandpass", fs=sample_rate, output="sos")
    return signal.sosfilt(sos, samples).astype(np.float32)


def notch_filter(samples: np.ndarray, sample_rate: int, freq_hz: float, q: float = 30.0) -> np.ndarray:
    """Remove a narrow frequency band (e.g. 50/60Hz mains hum and harmonics)."""
    if samples.size == 0:
        return samples
    nyquist = sample_rate / 2.0
    if freq_hz >= nyquist:
        return samples
    b, a = signal.iirnotch(freq_hz, q, fs=sample_rate)
    return signal.lfilter(b, a, samples).astype(np.float32)


def remove_mains_hum(samples: np.ndarray, sample_rate: int, mains_hz: float = 60.0) -> np.ndarray:
    """Notch out mains hum and its first two harmonics."""
    out = samples
    for harmonic in (1, 2, 3):
        out = notch_filter(out, sample_rate, mains_hz * harmonic)
    return out
