"""Builds the ``PracticeFeedbackEvent`` contract, Practice -> UI.

Keeping message text generation in one place makes it easy to keep the
learner-facing tone consistent (encouraging, specific, never scolding) and
to later localize without touching matching/scoring logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List

from pianotutor.practice.matcher import MatchOutcome, MatchResult
from pianotutor.dsp.spectrum import midi_to_freq  # noqa: F401  (re-exported for UI note naming)

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def pitch_name(pitch_midi: int) -> str:
    octave = pitch_midi // 12 - 1
    return f"{_NOTE_NAMES[pitch_midi % 12]}{octave}"


class FeedbackType(str, Enum):
    CORRECT = "correct"
    MISSING = "missing"
    EXTRA = "extra"
    LATE = "late"
    EARLY = "early"
    UNCERTAIN = "uncertain"
    PROGRESS = "progress"


@dataclass(frozen=True)
class PracticeFeedbackEvent:
    type: FeedbackType
    message: str
    related_pitches: List[int] = field(default_factory=list)
    score_delta: float = 0.0


_OUTCOME_TO_TYPE = {
    MatchOutcome.CORRECT: FeedbackType.CORRECT,
    MatchOutcome.EARLY: FeedbackType.EARLY,
    MatchOutcome.LATE: FeedbackType.LATE,
    MatchOutcome.EXTRA: FeedbackType.EXTRA,
    MatchOutcome.UNCERTAIN: FeedbackType.UNCERTAIN,
    MatchOutcome.MISSING: FeedbackType.MISSING,
}


def feedback_for_match(result: MatchResult, score_delta: float = 0.0) -> PracticeFeedbackEvent:
    feedback_type = _OUTCOME_TO_TYPE[result.outcome]
    related = []
    if result.expected_note is not None:
        related.append(result.expected_note.pitch_midi)
    elif result.detected is not None:
        related.append(result.detected.pitch_midi)

    if feedback_type == FeedbackType.CORRECT:
        message = f"Nice, {pitch_name(related[0])} right on time."
    elif feedback_type == FeedbackType.EARLY:
        message = f"{pitch_name(related[0])} was a little early."
    elif feedback_type == FeedbackType.LATE:
        message = f"{pitch_name(related[0])} was a little late."
    elif feedback_type == FeedbackType.EXTRA:
        message = f"{pitch_name(related[0])} wasn't expected here."
    elif feedback_type == FeedbackType.UNCERTAIN:
        message = "Couldn't tell for sure what was played — try again a bit louder/clearer."
    else:  # MISSING
        message = f"Missed {pitch_name(related[0])}."

    return PracticeFeedbackEvent(
        type=feedback_type, message=message, related_pitches=related, score_delta=score_delta
    )


def feedback_for_missing_note(pitch_midi: int, score_delta: float = 0.0) -> PracticeFeedbackEvent:
    return PracticeFeedbackEvent(
        type=FeedbackType.MISSING,
        message=f"Missed {pitch_name(pitch_midi)}.",
        related_pitches=[pitch_midi],
        score_delta=score_delta,
    )


def feedback_for_progress(message: str, related_pitches: List[int] | None = None) -> PracticeFeedbackEvent:
    return PracticeFeedbackEvent(
        type=FeedbackType.PROGRESS,
        message=message,
        related_pitches=related_pitches or [],
        score_delta=0.0,
    )
