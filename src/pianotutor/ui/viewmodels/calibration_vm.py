"""Qt-facing adapter for calibration event bus messages."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pianotutor.services.event_types import Topic


class CalibrationViewModel(QObject):
    step_changed = Signal(object)
    completed = Signal(object)
    level_updated = Signal(object)

    def __init__(self, event_bus, parent=None):
        super().__init__(parent)
        self._subscriptions = [
            event_bus.subscribe(Topic.CALIBRATION_STEP_CHANGED, self.step_changed.emit),
            event_bus.subscribe(Topic.CALIBRATION_COMPLETED, self.completed.emit),
            event_bus.subscribe(Topic.AUDIO_LEVEL_UPDATED, self.level_updated.emit),
        ]
