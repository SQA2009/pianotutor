"""The v1 weighted scoring model (development plan section 5).

- **Note accuracy** (40%): an F1-style blend of recall (expected pitches
  that were actually played) and precision (played pitches that were
  actually expected) — chosen because it naturally captures both missed
  notes and extra/wrong notes in one number, matching the plan's own
  testing-strategy language ("note precision/recall").
- **Chord completeness** (30%): average fraction of each expected chord's
  pitches that were detected, across all chord groupings in the excerpt.
- **Timing** (20%): average closeness-to-on-time of pitch-matched notes,
  normalized by the active tolerance window.
- **Consistency** (10%): of the notes whose pitch was matched, the fraction
  that were actually on-time (``CORRECT``) rather than early/late — a
  steadiness signal distinct from raw timing closeness.

Components are stored separately (not just the weighted total) so the UI
can show the learner *why* they got the score they did.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from pianotutor.practice.matcher import MatchOutcome, MatchResult
from pianotutor.services.config import ScoringWeights


@dataclass(frozen=True)
class ScoreComponents:
    note_accuracy: float
    chord_completeness: float
    timing: float
    consistency: float

    def total(self, weights: ScoringWeights) -> float:
        return (
            self.note_accuracy * weights.note_accuracy
            + self.chord_completeness * weights.chord_completeness
            + self.timing * weights.timing
            + self.consistency * weights.consistency
        )


class ScoreAccumulator:
    """Accumulates match outcomes across an excerpt pass and finalizes a score."""

    def __init__(self, tolerance_ms: float):
        self._tolerance_ms = max(tolerance_ms, 1e-6)
        self._matched_pitch_count = 0
        self._correct_count = 0
        self._extra_count = 0
        self._total_expected = 0
        self._timing_closeness_sum = 0.0
        self._timing_sample_count = 0
        self._chord_completeness_values: List[float] = []

    def set_total_expected(self, total_expected_notes: int) -> None:
        self._total_expected = total_expected_notes

    def record_match(self, result: MatchResult) -> None:
        if result.outcome in (MatchOutcome.CORRECT, MatchOutcome.EARLY, MatchOutcome.LATE):
            self._matched_pitch_count += 1
            if result.outcome == MatchOutcome.CORRECT:
                self._correct_count += 1
            if result.timing_error_ms is not None:
                closeness = max(0.0, 1.0 - abs(result.timing_error_ms) / self._tolerance_ms)
                self._timing_closeness_sum += closeness
                self._timing_sample_count += 1
        elif result.outcome == MatchOutcome.EXTRA:
            self._extra_count += 1
        # UNCERTAIN and MISSING intentionally do not directly increment any
        # counter here: UNCERTAIN detections are too unreliable to score
        # either way, and MISSING notes are already reflected by simply
        # never incrementing matched_pitch_count for them (see recall below).

    def record_chord_completeness(self, fraction: float) -> None:
        self._chord_completeness_values.append(fraction)

    def finalize(self) -> ScoreComponents:
        recall = (
            self._matched_pitch_count / self._total_expected if self._total_expected > 0 else 1.0
        )
        matched_plus_extra = self._matched_pitch_count + self._extra_count
        precision = self._matched_pitch_count / matched_plus_extra if matched_plus_extra > 0 else 1.0

        if recall + precision > 0:
            note_accuracy = 2 * precision * recall / (precision + recall)
        else:
            note_accuracy = 0.0

        chord_completeness = (
            sum(self._chord_completeness_values) / len(self._chord_completeness_values)
            if self._chord_completeness_values
            else 1.0
        )

        timing = (
            self._timing_closeness_sum / self._timing_sample_count
            if self._timing_sample_count > 0
            else 1.0
        )

        consistency = (
            self._correct_count / self._matched_pitch_count
            if self._matched_pitch_count > 0
            else 1.0
        )

        return ScoreComponents(
            note_accuracy=note_accuracy,
            chord_completeness=chord_completeness,
            timing=timing,
            consistency=consistency,
        )
