"""Guided (wait) vs continuous practice mode policy.

Guided mode is the "wait" mode from the development plan: the playhead will
not advance past an unmatched, still-required expected note beyond its
tolerance window — the learner has to actually play it (or explicitly skip)
before the excerpt continues. Continuous mode advances strictly with the
clock, useful for playing along at tempo once notes are more familiar.
"""

from __future__ import annotations

from enum import Enum


class PracticeMode(str, Enum):
    GUIDED = "guided"
    CONTINUOUS = "continuous"


def timing_tolerance_ms_for_mode(mode: PracticeMode, guided_ms: float, continuous_ms: float) -> float:
    return guided_ms if mode == PracticeMode.GUIDED else continuous_ms


def waits_for_correct_note(mode: PracticeMode) -> bool:
    return mode == PracticeMode.GUIDED
