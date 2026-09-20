"""Basic v1 polyphonic pitch grouping (2-4 notes) from harmonic salience.

Approach: score every candidate MIDI pitch by harmonic salience
(``dsp.features.harmonic_salience_scores``), then greedily accept the
highest-salience candidates, skipping any candidate whose fundamental is
well explained as a harmonic of an already-accepted note (the classic
octave/fifth "ghost note" false positive in multi-pitch estimation). This
keeps v1 chord recognition simple, fast, and confidence-aware without
requiring a full statistical multi-pitch model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from pianotutor.dsp.features import (
    PIANO_MAX_MIDI,
    PIANO_MIN_MIDI,
    harmonic_salience_scores,
    midi_index_to_pitch,
)
from pianotutor.dsp.spectrum import MagnitudeSpectrum

DEFAULT_MAX_NOTES = 4
DEFAULT_MIN_RELATIVE_SALIENCE = 0.18
HARMONIC_SUPPRESSION_RATIO_TOLERANCE = 0.03  # ~3% multiple tolerance for harmonic check


@dataclass(frozen=True)
class PitchCandidate:
    pitch_midi: int
    salience: float


def _is_harmonic_of(candidate_midi: int, accepted_midi: int) -> bool:
    """True if ``candidate_midi`` is approximately an integer-multiple overtone
    of ``accepted_midi`` (e.g. accepted=60 (C4), candidate=72 (C5, 2nd
    harmonic) or 79 (G5, 3rd harmonic))."""
    if candidate_midi <= accepted_midi:
        return False
    ratio = 2 ** ((candidate_midi - accepted_midi) / 12.0)
    nearest_integer_ratio = round(ratio)
    if nearest_integer_ratio < 2:
        return False
    return abs(ratio - nearest_integer_ratio) / nearest_integer_ratio <= HARMONIC_SUPPRESSION_RATIO_TOLERANCE


def estimate_chord_pitches(
    spectrum: MagnitudeSpectrum,
    max_notes: int = DEFAULT_MAX_NOTES,
    min_relative_salience: float = DEFAULT_MIN_RELATIVE_SALIENCE,
    min_note_separation_semitones: int = 1,
) -> List[PitchCandidate]:
    """Return up to ``max_notes`` pitches believed to be sounding simultaneously."""
    scores = harmonic_salience_scores(spectrum, min_midi=PIANO_MIN_MIDI, max_midi=PIANO_MAX_MIDI)
    if scores.size == 0 or float(np.max(scores)) <= 0:
        return []

    peak_score = float(np.max(scores))
    min_absolute_salience = peak_score * min_relative_salience

    order = np.argsort(scores)[::-1]
    accepted: List[PitchCandidate] = []

    for idx in order:
        score = float(scores[idx])
        if score < min_absolute_salience:
            break
        if len(accepted) >= max_notes:
            break

        candidate_midi = midi_index_to_pitch(int(idx))

        too_close = any(
            abs(candidate_midi - a.pitch_midi) < min_note_separation_semitones
            for a in accepted
        )
        if too_close:
            continue

        is_ghost_harmonic = any(
            _is_harmonic_of(candidate_midi, a.pitch_midi) for a in accepted
        )
        if is_ghost_harmonic:
            continue

        accepted.append(PitchCandidate(pitch_midi=candidate_midi, salience=score))

    accepted.sort(key=lambda c: c.pitch_midi)
    return accepted
