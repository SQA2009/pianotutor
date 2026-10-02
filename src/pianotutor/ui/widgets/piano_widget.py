"""Simple piano keyboard widget with expected/active highlighting."""

from __future__ import annotations

from typing import Dict, Set

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from pianotutor.dsp.features import PIANO_MAX_MIDI, PIANO_MIN_MIDI
from pianotutor.ui import theme
from pianotutor.ui.widgets import keyboard_geometry as geom

_WHITE_CLASSES = {0, 2, 4, 5, 7, 9, 11}


class PianoWidget(QWidget):
    def __init__(self, min_midi: int = PIANO_MIN_MIDI, max_midi: int = PIANO_MAX_MIDI, parent=None):
        super().__init__(parent)
        self._min_midi = min_midi
        self._max_midi = max_midi
        self._expected_pitches: Set[int] = set()
        self._active_states: Dict[int, str] = {}
        self.setMinimumHeight(110)

    def set_expected_pitches(self, pitches: Set[int]) -> None:
        self._expected_pitches = set(pitches)
        self.update()

    def set_active_states(self, states: Dict[int, str]) -> None:
        self._active_states = dict(states)
        self.update()

    def clear_active_states(self) -> None:
        self._active_states = {}
        self.update()

    def _key_color(self, pitch: int, is_white: bool) -> str:
        state = self._active_states.get(pitch)
        if state == "correct":
            return theme.CORRECT_GREEN
        if state in {"late", "early"}:
            return theme.LATE_AMBER if state == "late" else theme.EARLY_BLUE
        if state in {"missing", "extra"}:
            return theme.MISS_RED
        if state == "uncertain":
            return theme.UNCERTAIN_GREY
        if pitch in self._expected_pitches:
            return theme.BRASS
        return theme.IVORY if is_white else theme.EBONY

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        w = float(self.width())
        h = float(self.height())

        white_keys = [p for p in range(self._min_midi, self._max_midi + 1) if p % 12 in _WHITE_CLASSES]
        black_keys = [p for p in range(self._min_midi, self._max_midi + 1) if p % 12 not in _WHITE_CLASSES]

        for pitch in white_keys:
            kw = geom.key_width(pitch, self._min_midi, self._max_midi, w)
            cx = geom.key_center_x(pitch, self._min_midi, self._max_midi, w)
            rect = QRectF(cx - kw / 2, 0, kw, h)
            painter.setPen(QPen(QColor(theme.EBONY), 1))
            painter.setBrush(QColor(self._key_color(pitch, True)))
            painter.drawRect(rect)

        bh = h * 0.62
        for pitch in black_keys:
            kw = geom.key_width(pitch, self._min_midi, self._max_midi, w)
            cx = geom.key_center_x(pitch, self._min_midi, self._max_midi, w)
            rect = QRectF(cx - kw / 2, 0, kw, bh)
            painter.setPen(QPen(QColor(theme.EBONY), 1))
            painter.setBrush(QColor(self._key_color(pitch, False)))
            painter.drawRoundedRect(rect, 2, 2)

        painter.end()
