"""Harmonic/pitch-salience features used by both mono and polyphonic pitch estimation.

The core idea used for polyphony (basic v1 chord grouping): for every
candidate MIDI pitch in the piano range, compute a "harmonic salience" score
by summing the spectral magnitude found near its fundamental and its first
few harmonics (weighted so the fundamental matters most). Candidate pitches
are then ranked by salience; the top, non-conflicting candidates above a
minimum-salience threshold become the detected chord. This is a well-known,
inexpensive approach (related to harmonic-sum / two-way mismatch methods)
appropriate for a v1 "basic chord recognition" milestone — it is not a
full NMF/deep-learning multi-pitch estimator, which is explicitly deferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

from pianotutor.dsp.filters import PIANO_MAX_FREQ_HZ, PIANO_MIN_FREQ_HZ
from pianotutor.dsp.spectrum import (
    MagnitudeSpectrum,
    freq_to_midi,
    midi_to_freq,
    parabolic_interpolate_peak,
)

PIANO_MIN_MIDI = 21  # A0
PIANO_MAX_MIDI = 108  # C8


@dataclass(frozen=True)
class SpectralPeak:
    freq_hz: float
    magnitude: float


def find_spectral_peaks(
    spectrum: MagnitudeSpectrum,
    max_peaks: int = 12,
    min_freq_hz: float = PIANO_MIN_FREQ_HZ,
    max_freq_hz: float = PIANO_MAX_FREQ_HZ,
    relative_threshold: float = 0.05,
) -> List[SpectralPeak]:
    """Find local maxima in the magnitude spectrum, refined by parabolic interpolation."""
    mags = spectrum.magnitudes
    freqs = spectrum.freqs_hz
    if mags.size < 3:
        return []

    peak_mag = float(np.max(mags))
    if peak_mag <= 0:
        return []
    abs_threshold = peak_mag * relative_threshold

    candidates: List[Tuple[int, float]] = []
    for i in range(1, len(mags) - 1):
        if freqs[i] < min_freq_hz or freqs[i] > max_freq_hz:
            continue
        if mags[i] > mags[i - 1] and mags[i] > mags[i + 1] and mags[i] >= abs_threshold:
            candidates.append((i, mags[i]))

    candidates.sort(key=lambda c: c[1], reverse=True)
    candidates = candidates[: max_peaks * 3]  # over-fetch before frequency refinement

    bin_width = freqs[1] - freqs[0] if len(freqs) > 1 else 1.0
    peaks: List[SpectralPeak] = []
    for idx, mag in candidates:
        offset = parabolic_interpolate_peak(mags, idx)
        refined_freq = freqs[idx] + offset * bin_width
        peaks.append(SpectralPeak(freq_hz=refined_freq, magnitude=mag))

    peaks.sort(key=lambda p: p.magnitude, reverse=True)
    return peaks[:max_peaks]


def harmonic_salience_scores(
    spectrum: MagnitudeSpectrum,
    min_midi: int = PIANO_MIN_MIDI,
    max_midi: int = PIANO_MAX_MIDI,
    num_harmonics: int = 5,
    bin_search_cents: float = 35.0,
) -> np.ndarray:
    """Compute a harmonic-salience score for every MIDI pitch in range.

    For each candidate pitch, look for spectral energy within
    ``bin_search_cents`` of its fundamental and of each of its first
    ``num_harmonics - 1`` overtones, weighting harmonic ``k`` by ``1/k`` so
    the fundamental dominates. Returns an array indexed by
    ``midi_pitch - min_midi``.
    """
    mags = spectrum.magnitudes
    freqs = spectrum.freqs_hz
    n_pitches = max_midi - min_midi + 1
    scores = np.zeros(n_pitches, dtype=np.float64)

    if mags.size == 0:
        return scores

    for pitch_offset in range(n_pitches):
        midi_pitch = min_midi + pitch_offset
        fundamental = midi_to_freq(midi_pitch)
        if fundamental > freqs[-1]:
            continue
        score = 0.0
        for harmonic in range(1, num_harmonics + 1):
            target_freq = fundamental * harmonic
            if target_freq > freqs[-1]:
                break
            low = target_freq * (2 ** (-bin_search_cents / 1200.0))
            high = target_freq * (2 ** (bin_search_cents / 1200.0))
            mask = (freqs >= low) & (freqs <= high)
            if np.any(mask):
                score += float(np.max(mags[mask])) / harmonic
        scores[pitch_offset] = score

    return scores


def midi_index_to_pitch(index: int, min_midi: int = PIANO_MIN_MIDI) -> int:
    return index + min_midi
