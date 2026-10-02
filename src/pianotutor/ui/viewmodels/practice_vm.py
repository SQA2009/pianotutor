"""Qt-facing adapter for practice-related event bus messages."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pianotutor.services.event_types import Topic


class PracticeViewModel(QObject):
    feedback_received = Signal(object)
    score_updated = Signal(dict)
    playhead_updated = Signal(float)
    excerpt_looped = Signal(object)
    mastery_achieved = Signal(object)
    level_updated = Signal(object)
    stream_error = Signal(str)

    def __init__(self, event_bus, parent=None):
        super().__init__(parent)
        self._event_bus = event_bus
        self._subscriptions = [
            event_bus.subscribe(Topic.PRACTICE_FEEDBACK, self.feedback_received.emit),
            event_bus.subscribe(Topic.PRACTICE_SCORE_UPDATED, self._on_score_updated),
            event_bus.subscribe(Topic.PRACTICE_PLAYHEAD_UPDATED, self._on_playhead_updated),
            event_bus.subscribe(Topic.PRACTICE_EXCERPT_LOOPED, self.excerpt_looped.emit),
            event_bus.subscribe(Topic.PRACTICE_MASTERY_ACHIEVED, self.mastery_achieved.emit),
            event_bus.subscribe(Topic.AUDIO_LEVEL_UPDATED, self.level_updated.emit),
            event_bus.subscribe(Topic.AUDIO_STREAM_ERROR, self._on_stream_error),
        ]

    def _on_score_updated(self, payload) -> None:
        self.score_updated.emit(payload or {})

    def _on_playhead_updated(self, payload) -> None:
        t_ms = float((payload or {}).get("playhead_ms", 0.0))
        self.playhead_updated.emit(t_ms)

    def _on_stream_error(self, payload) -> None:
        message = str((payload or {}).get("error", "Audio stream error"))
        self.stream_error.emit(message)
