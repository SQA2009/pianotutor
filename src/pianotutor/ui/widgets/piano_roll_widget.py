"""Falling-notes practice timeline.

Notes fall from the top of the widget toward a fixed "hit line" near the
bottom, which represents "now" (the playhead). Pitch maps to the x-axis
using the same geometry as :class:`~pianotutor.ui.widgets.piano_widget.PianoWidget`,
so a note visually lands exactly on the key it corresponds to.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from pianotutor.dsp.features import PIANO_MAX_MIDI, PIANO_MIN_MIDI
from pianotutor.midi.timeline import ExpectedNote
from pianotutor.ui import theme
from pianotutor.ui.widgets import keyboard_geometry as geom

HIT_LINE_FRACTION = 0.85  # fraction of widget height where "now" sits


@dataclass(frozen=True)
class _RollNote:
    note: ExpectedNote
    outcome: str  # "pending" | "correct" | "late" | "early" | "missing" | "extra" | "uncertain"


class PianoRollWidget(QWidget):
    def __init__(
        self,
        min_midi: int = PIANO_MIN_MIDI,
        max_midi: int = PIANO_MAX_MIDI,
        lookahead_ms: float = 3000.0,
        lookbehind_ms: float = 400.0,
        parent=None,
    ):
        super().__init__(parent)
        self._min_midi = min_midi
        self._max_midi = max_midi
        self._lookahead_ms = lookahead_ms
        self._lookbehind_ms = lookbehind_ms

        self._notes: List[ExpectedNote] = []
        self._outcomes: Dict[int, str] = {}
        self._playhead_ms = 0.0

        self.setMinimumHeight(220)
        self.setMinimumWidth(400)

    def set_notes(self, notes: List[ExpectedNote]) -> None:
        self._notes = sorted(notes, key=lambda n: n.start_ms)
        self._outcomes = {}
        self.update()

    def set_playhead_ms(self, t_ms: float) -> None:
        self._playhead_ms = t_ms
        self.update()

    @property
    def playhead_ms(self) -> float:
        return self._playhead_ms

    def set_note_outcome(self, note_id: int, outcome: str) -> None:
        self._outcomes[note_id] = outcome
        self.update()

    def reset_outcomes(self) -> None:
        self._outcomes = {}
        self.update()

    def _time_to_y(self, t_ms: float, hit_line_y: float) -> float:
        return hit_line_y - (t_ms - self._playhead_ms) / self._lookahead_ms * hit_line_y

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        width = self.width()
        height = self.height()
        hit_line_y = height * HIT_LINE_FRACTION

        earliest_visible = self._playhead_ms - self._lookbehind_ms
        latest_visible = self._playhead_ms + self._lookahead_ms

        for note in self._notes:
            if note.end_ms < earliest_visible or note.start_ms > latest_visible:
                continue

            y_top = self._time_to_y(note.end_ms, hit_line_y)
            y_bottom = self._time_to_y(note.start_ms, hit_line_y)
            y_top = max(0.0, y_top)
            y_bottom = min(float(height), y_bottom)
            if y_bottom <= y_top:
                continue

            center_x = geom.key_center_x(note.pitch_midi, self._min_midi, self._max_midi, width)
            key_w = geom.key_width(note.pitch_midi, self._min_midi, self._max_midi, width)
            note_w = key_w * 0.78
            rect = QRectF(center_x - note_w / 2, y_top, note_w, y_bottom - y_top)

            outcome = self._outcomes.get(note.note_id, "pending")
            color = QColor(self._color_for_outcome(outcome))
            painter.setPen(QPen(QColor(theme.EBONY), 1))
            painter.setBrush(color)
            painter.drawRoundedRect(rect, 3, 3)

        painter.setPen(QPen(QColor(theme.BRASS), 2, Qt.DashLine))
        painter.drawLine(0, int(hit_line_y), width, int(hit_line_y))
        painter.end()

    @staticmethod
    def _color_for_outcome(outcome: str) -> str:
        return {
            "pending": theme.IVORY_MUTED,
            "correct": theme.CORRECT_GREEN,
            "late": theme.LATE_AMBER,
            "early": theme.EARLY_BLUE,
            "missing": theme.MISS_RED,
            "extra": theme.MISS_RED,
            "uncertain": theme.UNCERTAIN_GREY,
        }.get(outcome, theme.IVORY_MUTED)
