"""Confidence scoring shared by the monophonic and polyphonic recognition paths.

Combines several independent signals of "how sure are we this detection is
real" into a single 0..1 confidence value that the practice engine's
tolerance/matching logic (development plan section 4) consumes directly:
below 0.60 -> soft/uncertain feedback, at/above 0.85 with the wrong pitch ->
treated as a hard mismatch rather than a near-miss.
"""

from __future__ import annotations

import numpy as np


def _clip01(x: float) -> float:
    return float(np.clip(x, 0.0, 1.0))


def snr_ratio(signal_rms: float, noise_floor_rms: float, saturating_db: float = 30.0) -> float:
    """Map a signal-to-noise-floor ratio to 0..1, saturating at ``saturating_db``."""
    if signal_rms <= 0 or noise_floor_rms <= 0:
        return 0.0
    db = 20.0 * np.log10(signal_rms / noise_floor_rms)
    return _clip01(db / saturating_db)


def salience_ratio(candidate_salience: float, peak_salience: float) -> float:
    """How strong a candidate's harmonic salience is relative to the block's peak."""
    if peak_salience <= 0:
        return 0.0
    return _clip01(candidate_salience / peak_salience)


def monophonic_confidence(clarity: float, snr: float, onset_strength_ratio: float) -> float:
    """Confidence for a YIN-derived single-note detection.

    Weighted toward YIN's own clarity score (the strongest available signal
    for "is this really one clean pitch"), with SNR and onset strength as
    supporting evidence.
    """
    clarity = _clip01(clarity)
    snr = _clip01(snr)
    onset_strength_ratio = _clip01(onset_strength_ratio)
    return _clip01(0.6 * clarity + 0.25 * snr + 0.15 * onset_strength_ratio)


def polyphonic_confidence(
    salience: float, peak_salience: float, snr: float, onset_strength_ratio: float
) -> float:
    """Confidence for a harmonic-salience-derived chord-note detection."""
    rel_salience = salience_ratio(salience, peak_salience)
    snr = _clip01(snr)
    onset_strength_ratio = _clip01(onset_strength_ratio)
    return _clip01(0.55 * rel_salience + 0.25 * snr + 0.20 * onset_strength_ratio)
