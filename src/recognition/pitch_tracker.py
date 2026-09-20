"""Monophonic fundamental-frequency tracking via the YIN algorithm.

YIN (de Cheveigne & Kawahara, 2002) is a well-established, inexpensive
autocorrelation-family pitch estimator that works well for a single sung or
played note — exactly what "single-note recognition (reliable baseline)"
calls for. It reports both a frequency estimate and a "clarity" score
(1 - the normalized difference function's value at the chosen lag), which
doubles as a strong signal for "is this block actually monophonic" — low
clarity means no single periodicity dominates, which is exactly when the
aggregator should fall back to the polyphonic harmonic-salience path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class YinResult:
    freq_hz: float
    clarity: float  # 0..1, higher = more confidently periodic/monophonic


def _difference_function(samples: np.ndarray, max_lag: int) -> np.ndarray:
    """YIN's squared-difference function d(tau) via an FFT-based autocorrelation.

    Computing this with FFT autocorrelation instead of the naive O(n*max_lag)
    double loop keeps per-block cost low enough for real-time use even at the
    long lags needed to resolve low piano notes (A0 ~27.5 Hz).
    """
    n = samples.shape[0]
    size = 1
    while size < 2 * n:
        size *= 2

    fft = np.fft.rfft(samples, n=size)
    power = fft * np.conj(fft)
    autocorr = np.fft.irfft(power, n=size)[:n]

    squared = samples.astype(np.float64) ** 2
    cumsum = np.concatenate(([0.0], np.cumsum(squared)))

    # Standard YIN difference function:
    # d(tau) = sum_{j=0}^{n-tau-1} (x_j - x_{j+tau})^2
    #        = sum(x_j^2) + sum(x_{j+tau}^2) - 2*autocorr(tau)
    d = np.zeros(max_lag + 1, dtype=np.float64)
    total_energy = float(np.sum(squared))
    running_tail_energy = total_energy
    for tau in range(0, max_lag + 1):
        if tau == 0:
            d[tau] = 0.0
            continue
        if tau >= n:
            d[tau] = d[tau - 1]
            continue
        head_energy = float(cumsum[n - tau])  # sum of x_j^2 for j in [0, n-tau)
        tail_energy = total_energy - float(cumsum[tau])  # sum of x_{j+tau}^2 for j in [0, n-tau)
        d[tau] = head_energy + tail_energy - 2 * autocorr[tau]

    return d


def _cumulative_mean_normalized_difference(d: np.ndarray) -> np.ndarray:
    cmnd = np.ones_like(d)
    running_sum = 0.0
    for tau in range(1, len(d)):
        running_sum += d[tau]
        cmnd[tau] = d[tau] / (running_sum / tau) if running_sum > 0 else 1.0
    return cmnd


def _parabolic_refine(cmnd: np.ndarray, tau: int) -> float:
    if tau <= 0 or tau >= len(cmnd) - 1:
        return float(tau)
    s0, s1, s2 = cmnd[tau - 1], cmnd[tau], cmnd[tau + 1]
    denom = 2 * (2 * s1 - s0 - s2)
    if denom == 0:
        return float(tau)
    adjustment = (s0 - s2) / denom
    return tau + adjustment


def estimate_pitch_yin(
    samples: np.ndarray,
    sample_rate: int,
    fmin_hz: float = 24.0,
    fmax_hz: float = 2100.0,
    threshold: float = 0.15,
) -> Optional[YinResult]:
    """Estimate the dominant fundamental frequency of ``samples`` via YIN.

    Returns ``None`` if the block is too short to analyze the requested
    frequency range, or if no lag's cumulative-mean-normalized-difference
    drops below ``threshold`` (i.e. no strongly periodic signal was found).
    """
    n = samples.shape[0]
    min_lag = max(2, int(sample_rate / fmax_hz))
    max_lag = int(sample_rate / fmin_hz)

    if n < max_lag + 2:
        # Not enough samples to resolve fmin; caller should supply a larger window.
        max_lag = max(min_lag + 1, n - 2)
        if max_lag <= min_lag:
            return None

    d = _difference_function(samples.astype(np.float64), max_lag)
    cmnd = _cumulative_mean_normalized_difference(d)

    tau = None
    for candidate in range(min_lag, max_lag):
        if cmnd[candidate] < threshold:
            # Walk forward to the local minimum (YIN's standard refinement step).
            t = candidate
            while t + 1 < len(cmnd) and cmnd[t + 1] < cmnd[t]:
                t += 1
            tau = t
            break

    if tau is None:
        # Fall back to global minimum in range if nothing met the threshold;
        # report it but let the confidence layer downweight it heavily.
        search = cmnd[min_lag:max_lag]
        if search.size == 0:
            return None
        tau = int(np.argmin(search)) + min_lag

    refined_tau = _parabolic_refine(cmnd, tau)
    if refined_tau <= 0:
        return None

    freq_hz = sample_rate / refined_tau
    clarity = float(np.clip(1.0 - cmnd[tau], 0.0, 1.0))

    if not (fmin_hz * 0.5 <= freq_hz <= fmax_hz * 2.0):
        return None

    return YinResult(freq_hz=freq_hz, clarity=clarity)
