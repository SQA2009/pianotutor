"""Practice engine: orchestrates matching, scoring, mastery, and looping.

Consumes ``NOTE_DETECTED`` events from the event bus (assumed already
latency-compensated upstream — see ``app.py``'s wiring), matches them
against the current excerpt's ``ExpectedNote`` timeline, updates a running
score, tracks mastery across loop passes, and emits
``PracticeFeedbackEvent``s plus session/score lifecycle events for the UI.

Guided ("wait") mode holds the playhead back from running past an unplayed,
still-pending note by more than ``GUIDED_WAIT_GRACE_MS``, giving the learner
a real chance to play it before it's marked missing and the excerpt moves
on; continuous mode has no such hold and uses the (tighter) continuous
timing tolerance as its missing-note cutoff instead.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from pianotutor.midi.timeline import ExpectedNote
from pianotutor.practice.feedback import (
    feedback_for_match,
    feedback_for_missing_note,
    feedback_for_progress,
)
from pianotutor.practice.matcher import (
    MatchOutcome,
    MatchResult,
    chord_completeness,
    find_missing_notes,
    group_expected_chords,
    match_detected_note,
)
from pianotutor.practice.mastery import MasteryState, MasteryTracker
from pianotutor.practice.modes import PracticeMode, waits_for_correct_note
from pianotutor.practice.scoring import ScoreAccumulator, ScoreComponents
from pianotutor.practice.tolerance import ResolvedTolerance, resolve_tolerance
from pianotutor.recognition.note_events import DetectedNoteEvent, NoteState
from pianotutor.services.clock import Clock
from pianotutor.services.config import AppConfig
from pianotutor.services.event_bus import EventBus
from pianotutor.services.event_types import Topic

logger = logging.getLogger(__name__)

GUIDED_WAIT_GRACE_MS = 2000.0


@dataclass
class SessionResult:
    score: ScoreComponents
    total_score: float
    mastery: MasteryState
    loop_count: int


class PracticeEngine:
    def __init__(
        self,
        expected_notes: List[ExpectedNote],
        section_start_ms: float,
        section_end_ms: float,
        config: AppConfig,
        mode: PracticeMode,
        event_bus: EventBus,
        clock: Clock,
    ):
        self._all_notes = [
            n for n in expected_notes if section_start_ms <= n.start_ms < section_end_ms
        ]
        self._section_start_ms = section_start_ms
        self._section_end_ms = section_end_ms
        self._config = config
        self._mode = mode
        self._event_bus = event_bus
        self._clock = clock

        self._tolerance: ResolvedTolerance = resolve_tolerance(config.tolerance, mode)
        self._missing_timeout_ms = (
            GUIDED_WAIT_GRACE_MS if mode == PracticeMode.GUIDED else self._tolerance.timing_tolerance_ms
        )
        self._mastery_tracker = MasteryTracker(config.mastery)
        self._chord_groups = group_expected_chords(
            self._all_notes, self._tolerance.chord_grouping_window_ms
        )

        self._session_active = False
        self._unsubscribe_note = None

        self._pending: Dict[int, ExpectedNote] = {}
        self._accumulator: Optional[ScoreAccumulator] = None
        self._detected_pitches_by_chord_index: Dict[int, set] = {}
        self._playhead_ms = section_start_ms
        self._reset_pass_state()

    # --- Session lifecycle ---------------------------------------------------
    def start_session(self) -> None:
        self._reset_pass_state()
        self._session_active = True
        self._unsubscribe_note = self._event_bus.subscribe(
            Topic.NOTE_DETECTED, self._on_note_detected
        )
        self._event_bus.publish(
            Topic.PRACTICE_SESSION_STARTED,
            {
                "mode": self._mode.value,
                "section_start_ms": self._section_start_ms,
                "section_end_ms": self._section_end_ms,
            },
        )
        logger.info("Practice session started (mode=%s)", self._mode.value)

    def stop_session(self) -> None:
        self._session_active = False
        if self._unsubscribe_note:
            self._unsubscribe_note()
            self._unsubscribe_note = None
        self._event_bus.publish(Topic.PRACTICE_SESSION_ENDED, None)
        logger.info("Practice session stopped")

    def _reset_pass_state(self) -> None:
        self._pending = {n.note_id: n for n in self._all_notes}
        self._accumulator = ScoreAccumulator(self._tolerance.timing_tolerance_ms)
        self._accumulator.set_total_expected(len(self._all_notes))
        self._playhead_ms = self._section_start_ms
        self._detected_pitches_by_chord_index = {}

    # --- Playhead / transport --------------------------------------------------
    def advance(self, elapsed_ms: float) -> float:
        """Advance the playhead by ``elapsed_ms`` (driven by the UI's timer)."""
        if not self._session_active:
            return self._playhead_ms

        proposed = self._playhead_ms + elapsed_ms

        if waits_for_correct_note(self._mode):
            earliest_pending = self._earliest_pending_start_ms()
            if earliest_pending is not None:
                hold_limit = earliest_pending + GUIDED_WAIT_GRACE_MS
                proposed = max(self._playhead_ms, min(proposed, hold_limit))

        self._playhead_ms = min(proposed, self._section_end_ms)

        self._expire_missing_notes()
        self._event_bus.publish(
            Topic.PRACTICE_PLAYHEAD_UPDATED, {"playhead_ms": self._playhead_ms}
        )

        if self._playhead_ms >= self._section_end_ms:
            if self._pending:
                self._expire_missing_notes(force=True)
            self._finish_pass()

        return self._playhead_ms

    def _earliest_pending_start_ms(self) -> Optional[float]:
        if not self._pending:
            return None
        return min(n.start_ms for n in self._pending.values())

    # --- Detection handling --------------------------------------------------
    def _on_note_detected(self, detected: DetectedNoteEvent) -> None:
        if not self._session_active or detected.state != NoteState.STARTED:
            return

        candidates = list(self._pending.values())
        result = match_detected_note(detected, candidates, self._tolerance)
        self._accumulator.record_match(result)

        if result.expected_note is not None and result.outcome in (
            MatchOutcome.CORRECT,
            MatchOutcome.EARLY,
            MatchOutcome.LATE,
        ):
            self._pending.pop(result.expected_note.note_id, None)
            self._record_chord_progress(result.expected_note, detected.pitch_midi)

        feedback = feedback_for_match(
            result, score_delta=self._score_delta_for_outcome(result.outcome)
        )
        self._event_bus.publish(Topic.PRACTICE_FEEDBACK, feedback)

    @staticmethod
    def _score_delta_for_outcome(outcome: MatchOutcome) -> float:
        return {
            MatchOutcome.CORRECT: 1.0,
            MatchOutcome.EARLY: 0.5,
            MatchOutcome.LATE: 0.5,
            MatchOutcome.EXTRA: -0.5,
            MatchOutcome.UNCERTAIN: 0.0,
            MatchOutcome.MISSING: -1.0,
        }[outcome]

    def _record_chord_progress(self, matched_expected: ExpectedNote, detected_pitch: int) -> None:
        for idx, group in enumerate(self._chord_groups):
            if any(n.note_id == matched_expected.note_id for n in group):
                seen = self._detected_pitches_by_chord_index.setdefault(idx, set())
                seen.add(detected_pitch)
                if all(n.note_id not in self._pending for n in group):
                    expected_pitches = [n.pitch_midi for n in group]
                    fraction = chord_completeness(expected_pitches, list(seen))
                    self._accumulator.record_chord_completeness(fraction)
                break

    def _expire_missing_notes(self, force: bool = False) -> None:
        if not self._pending:
            return
        if force:
            expired = list(self._pending.values())
        else:
            expired = find_missing_notes(
                list(self._pending.values()), self._playhead_ms, self._missing_timeout_ms
            )

        for note in expired:
            self._pending.pop(note.note_id, None)
            missing_result = MatchResult(MatchOutcome.MISSING, note, None, None, 0.0)
            self._accumulator.record_match(missing_result)
            self._record_chord_progress(note, detected_pitch=-1)
            feedback = feedback_for_missing_note(
                note.pitch_midi, score_delta=self._score_delta_for_outcome(MatchOutcome.MISSING)
            )
            self._event_bus.publish(Topic.PRACTICE_FEEDBACK, feedback)

    def _finish_pass(self) -> SessionResult:
        components = self._accumulator.finalize()
        total = components.total(self._config.scoring)
        mastery_state = self._mastery_tracker.record_pass(total)

        self._event_bus.publish(
            Topic.PRACTICE_SCORE_UPDATED,
            {
                "note_accuracy": components.note_accuracy,
                "chord_completeness": components.chord_completeness,
                "timing": components.timing,
                "consistency": components.consistency,
                "total": total,
            },
        )

        result = SessionResult(
            score=components,
            total_score=total,
            mastery=mastery_state,
            loop_count=mastery_state.total_loops,
        )

        if mastery_state.mastered:
            self._session_active = False
            self._event_bus.publish(Topic.PRACTICE_MASTERY_ACHIEVED, result)
            self._event_bus.publish(
                Topic.PRACTICE_FEEDBACK,
                feedback_for_progress(
                    f"Mastered! {mastery_state.consecutive_passes} clean passes in a row."
                ),
            )
        else:
            self._event_bus.publish(Topic.PRACTICE_EXCERPT_LOOPED, result)
            streak_note = (
                f"Streak: {mastery_state.consecutive_passes}"
                if mastery_state.consecutive_passes
                else "Looping again."
            )
            self._event_bus.publish(
                Topic.PRACTICE_FEEDBACK,
                feedback_for_progress(f"Pass complete: {total:.0%}. {streak_note}"),
            )
            self._reset_pass_state()

        return result

    @property
    def playhead_ms(self) -> float:
        return self._playhead_ms

    @property
    def is_mastered(self) -> bool:
        return self._mastery_tracker.state.mastered

    @property
    def mastery_state(self) -> MasteryState:
        return self._mastery_tracker.state
