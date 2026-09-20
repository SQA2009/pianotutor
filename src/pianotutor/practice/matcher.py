"""Stateless matching between one detected note and a set of expected notes.

Deliberately pure/stateless: given a detected event and the current list of
still-pending expected notes (state tracking is the engine's job), it
returns a single :class:`MatchResult`. This makes the matching *rules*
independently unit-testable against synthetic fixtures without needing a
running practice session.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from pianotutor.midi.timeline import ExpectedNote
from pianotutor.practice.tolerance import ResolvedTolerance
from pianotutor.recognition.note_events import DetectedNoteEvent


class MatchOutcome(str, Enum):
    CORRECT = "correct"
    EARLY = "early"
    LATE = "late"
    EXTRA = "extra"
    UNCERTAIN = "uncertain"
    MISSING = "missing"


@dataclass(frozen=True)
class MatchResult:
    outcome: MatchOutcome
    expected_note: Optional[ExpectedNote]
    detected: Optional[DetectedNoteEvent]
    timing_error_ms: Optional[float]
    confidence: float


def match_detected_note(
    detected: DetectedNoteEvent,
    pending_candidates: List[ExpectedNote],
    tolerance: ResolvedTolerance,
    search_window_ms: float = 1500.0,
) -> MatchResult:
    """Match one detected ``started`` note event against pending expected notes.

    ``pending_candidates`` must already be filtered by the caller to notes
    not yet matched/missed. Selection among same-pitch candidates is by
    nearest start time. Confidence gates the whole classification first
    (development plan section 4): below the uncertain threshold, a
    detection is reported as ``UNCERTAIN`` regardless of pitch/timing, since
    we can't trust it enough to call it definitively right or wrong.
    """
    same_pitch = [
        c
        for c in pending_candidates
        if c.pitch_midi == detected.pitch_midi
        and abs(detected.t_ms - c.start_ms) <= search_window_ms
    ]

    if not same_pitch:
        outcome = (
            MatchOutcome.UNCERTAIN
            if detected.confidence < tolerance.uncertain_confidence_threshold
            else MatchOutcome.EXTRA
        )
        return MatchResult(outcome, None, detected, None, detected.confidence)

    nearest = min(same_pitch, key=lambda c: abs(detected.t_ms - c.start_ms))
    timing_error_ms = detected.t_ms - nearest.start_ms

    if detected.confidence < tolerance.uncertain_confidence_threshold:
        return MatchResult(
            MatchOutcome.UNCERTAIN, nearest, detected, timing_error_ms, detected.confidence
        )

    if abs(timing_error_ms) <= tolerance.timing_tolerance_ms:
        outcome = MatchOutcome.CORRECT
    elif timing_error_ms < 0:
        outcome = MatchOutcome.EARLY
    else:
        outcome = MatchOutcome.LATE

    return MatchResult(outcome, nearest, detected, timing_error_ms, detected.confidence)


def find_missing_notes(
    pending_candidates: List[ExpectedNote], playhead_ms: float, tolerance: ResolvedTolerance
) -> List[ExpectedNote]:
    """Expected notes whose matching window has fully elapsed with no match."""
    return [
        c
        for c in pending_candidates
        if playhead_ms - c.start_ms > tolerance.timing_tolerance_ms
    ]


def chord_completeness(expected_pitches: List[int], detected_pitches: List[int]) -> float:
    """Fraction of an expected chord's pitches that were actually detected.

    Extra (unexpected) detected pitches don't push completeness above 1.0 —
    they're penalized separately, via per-note ``EXTRA`` outcomes.
    """
    if not expected_pitches:
        return 1.0
    expected_set = set(expected_pitches)
    detected_set = set(detected_pitches)
    return len(expected_set & detected_set) / len(expected_set)


def group_expected_chords(
    expected_notes: List[ExpectedNote], chord_grouping_window_ms: float
) -> List[List[ExpectedNote]]:
    """Group expected notes that start within ``chord_grouping_window_ms`` of
    each other into chords (a "chord" of size 1 is just a plain single note).
    """
    if not expected_notes:
        return []
    ordered = sorted(expected_notes, key=lambda n: n.start_ms)
    groups: List[List[ExpectedNote]] = [[ordered[0]]]
    for note in ordered[1:]:
        if note.start_ms - groups[-1][0].start_ms <= chord_grouping_window_ms:
            groups[-1].append(note)
        else:
            groups.append([note])
    return groups
