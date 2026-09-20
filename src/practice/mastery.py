"""Excerpt loop-to-mastery tracking (development plan Milestone E).

An excerpt is "mastered" once the learner achieves
``consecutive_passes_required`` passes in a row, each scoring at or above
``pass_score_threshold``. Any pass below the threshold resets the streak —
mastery must be earned with a genuine run of consecutive good passes, not
just an average.
"""

from __future__ import annotations

from dataclasses import dataclass

from pianotutor.services.config import MasteryConfig


@dataclass
class MasteryState:
    consecutive_passes: int = 0
    total_loops: int = 0
    mastered: bool = False


class MasteryTracker:
    def __init__(self, config: MasteryConfig):
        self._config = config
        self._state = MasteryState()

    @property
    def state(self) -> MasteryState:
        return self._state

    def record_pass(self, total_score: float) -> MasteryState:
        self._state.total_loops += 1
        if total_score >= self._config.pass_score_threshold:
            self._state.consecutive_passes += 1
        else:
            self._state.consecutive_passes = 0

        if self._state.consecutive_passes >= self._config.consecutive_passes_required:
            self._state.mastered = True

        return self._state

    def reset(self) -> None:
        self._state = MasteryState()
