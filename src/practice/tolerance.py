"""Resolves the active tolerance windows for a practice session.

Thin wrapper around ``services.config.ToleranceConfig`` that bakes in the
current :class:`~pianotutor.practice.modes.PracticeMode`, so the matcher and
engine only ever need one concrete tolerance value rather than threading
mode-branching logic through every call site.
"""

from __future__ import annotations

from dataclasses import dataclass

from pianotutor.practice.modes import PracticeMode, timing_tolerance_ms_for_mode
from pianotutor.services.config import ToleranceConfig


@dataclass(frozen=True)
class ResolvedTolerance:
    timing_tolerance_ms: float
    chord_grouping_window_ms: float
    uncertain_confidence_threshold: float
    hard_mismatch_confidence_threshold: float


def resolve_tolerance(config: ToleranceConfig, mode: PracticeMode) -> ResolvedTolerance:
    return ResolvedTolerance(
        timing_tolerance_ms=timing_tolerance_ms_for_mode(
            mode, config.guided_timing_tolerance_ms, config.continuous_timing_tolerance_ms
        ),
        chord_grouping_window_ms=config.chord_grouping_window_ms,
        uncertain_confidence_threshold=config.uncertain_confidence_threshold,
        hard_mismatch_confidence_threshold=config.hard_mismatch_confidence_threshold,
    )
