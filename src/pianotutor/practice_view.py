"""Practice view: falling notes + keyboard + live feedback + scoring.

Owns the transport timer that drives ``PracticeEngine.advance()`` — the
engine itself is purely reactive to being told how much time has passed,
which keeps its core logic UI-framework-agnostic and unit-testable without
Qt (see ``tests/unit/test_practice_engine.py``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pianotutor.audio.stream import AudioStreamError
from pianotutor.midi.importer import ImportedSong
from pianotutor.midi.sections import Section
from pianotutor.midi.timeline import ExpectedNote
from pianotutor.practice.feedback import FeedbackType, PracticeFeedbackEvent
from pianotutor.practice.modes import PracticeMode
from pianotutor.ui import theme
from pianotutor.ui.viewmodels.practice_vm import PracticeViewModel
from pianotutor.ui.widgets.input_meter_widget import InputMeterPanel
from pianotutor.ui.widgets.piano_roll_widget import PianoRollWidget
from pianotutor.ui.widgets.piano_widget import PianoWidget

if TYPE_CHECKING:
    from pianotutor.app import Application

TICK_INTERVAL_MS = 33  # ~30fps transport tick
PITCH_HIGHLIGHT_DECAY_MS = 700
NEAREST_NOTE_SEARCH_WINDOW_MS = 1500.0

_FEEDBACK_ROLE = {
    FeedbackType.CORRECT: "feedback-correct",
    FeedbackType.LATE: "feedback-late",
    FeedbackType.EARLY: "feedback-early",
    FeedbackType.MISSING: "feedback-missing",
    FeedbackType.EXTRA: "feedback-extra",
    FeedbackType.UNCERTAIN: "feedback-uncertain",
    FeedbackType.PROGRESS: "feedback-progress",
}
_FEEDBACK_COLOR = {
    FeedbackType.CORRECT: theme.CORRECT_GREEN,
    FeedbackType.LATE: theme.LATE_AMBER,
    FeedbackType.EARLY: theme.EARLY_BLUE,
    FeedbackType.MISSING: theme.MISS_RED,
    FeedbackType.EXTRA: theme.MISS_RED,
    FeedbackType.UNCERTAIN: theme.UNCERTAIN_GREY,
    FeedbackType.PROGRESS: theme.BRASS,
}


class PracticeView(QWidget):
    def __init__(self, app: "Application", parent=None):
        super().__init__(parent)
        self._app = app
        self._vm = PracticeViewModel(app.event_bus)

        self._song: Optional[ImportedSong] = None
        self._sections: List[Section] = []
        self._section_notes: List[ExpectedNote] = []
        self._active_pitch_states: Dict[int, str] = {}

        self._title_label = QLabel("No song loaded")
        self._title_label.setProperty("role", "heading")

        self._section_combo = QComboBox()
        self._mode_combo = QComboBox()
        self._mode_combo.addItem("Guided (wait for me)", PracticeMode.GUIDED)
        self._mode_combo.addItem("Continuous (play along)", PracticeMode.CONTINUOUS)

        self._start_button = QPushButton("Start")
        self._start_button.setProperty("role", "primary")
        self._start_button.clicked.connect(self._on_start_clicked)
        self._stop_button = QPushButton("Stop")
        self._stop_button.clicked.connect(self._on_stop_clicked)
        self._stop_button.setEnabled(False)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Section:"))
        controls.addWidget(self._section_combo, 1)
        controls.addWidget(QLabel("Mode:"))
        controls.addWidget(self._mode_combo)
        controls.addWidget(self._start_button)
        controls.addWidget(self._stop_button)

        self._piano_roll = PianoRollWidget()
        self._piano = PianoWidget()

        self._meter_panel = InputMeterPanel()
        self._mastery_label = QLabel("")
        self._mastery_label.setProperty("role", "subheading")

        self._score_bar = QProgressBar()
        self._score_bar.setRange(0, 100)
        self._score_bar.setFormat("Score: %p%")
        self._score_detail_label = QLabel("")
        self._score_detail_label.setProperty("role", "subheading")

        self._feedback_list = QListWidget()
        self._feedback_list.setMaximumHeight(140)

        top_row = QHBoxLayout()
        top_row.addWidget(self._title_label, 1)
        top_row.addWidget(self._meter_panel)

        score_row = QHBoxLayout()
        score_row.addWidget(self._score_bar, 1)
        score_row.addWidget(self._mastery_label)

        layout = QVBoxLayout(self)
        layout.addLayout(top_row)
        layout.addLayout(controls)
        layout.addWidget(self._piano_roll, 1)
        layout.addWidget(self._piano)
        layout.addLayout(score_row)
        layout.addWidget(self._score_detail_label)
        layout.addWidget(self._feedback_list)

        self._timer = QTimer(self)
        self._timer.setInterval(TICK_INTERVAL_MS)
        self._timer.timeout.connect(self._on_tick)
        self._last_tick_ms = 0.0

        self._vm.feedback_received.connect(self._on_feedback)
        self._vm.score_updated.connect(self._on_score_updated)
        self._vm.playhead_updated.connect(self._on_playhead_updated)
        self._vm.excerpt_looped.connect(self._on_pass_finished)
        self._vm.mastery_achieved.connect(self._on_pass_finished)
        self._vm.level_updated.connect(self._meter_panel.set_level)
        self._vm.stream_error.connect(self._on_stream_error)

    def load_song(self, song_id: int) -> None:
        self._song = self._app.load_song(song_id)
        self._sections = self._song.sections
        self._title_label.setText(self._song.title)

        self._section_combo.clear()
        for section in self._sections:
            self._section_combo.addItem(section.label)

        self._piano_roll.set_notes(self._song.expected_notes)
        self._piano_roll.set_playhead_ms(0.0)
        self._feedback_list.clear()
        self._score_bar.setValue(0)
        self._mastery_label.setText("")

    # --- Transport ----------------------------------------------------------------
    def _on_start_clicked(self) -> None:
        if self._song is None or self._section_combo.currentIndex() < 0:
            return
        section = self._sections[self._section_combo.currentIndex()]
        mode: PracticeMode = self._mode_combo.currentData()

        try:
            self._app.start_practice_session(self._song, section, mode)
        except AudioStreamError as exc:
            QMessageBox.warning(self, "Couldn't start listening", str(exc))
            return

        self._section_notes = [
            n for n in self._song.expected_notes if section.start_ms <= n.start_ms < section.end_ms
        ]
        self._piano_roll.set_notes(self._section_notes)
        self._piano_roll.set_playhead_ms(section.start_ms)
        self._feedback_list.clear()
        self._active_pitch_states = {}
        self._piano.clear_active_states()

        self._last_tick_ms = self._app.clock.now_ms()
        self._timer.start()
        self._start_button.setEnabled(False)
        self._stop_button.setEnabled(True)
        self._section_combo.setEnabled(False)
        self._mode_combo.setEnabled(False)

    def _on_stop_clicked(self) -> None:
        self._stop_practice(user_initiated=True)

    def _stop_practice(self, user_initiated: bool) -> None:
        self._timer.stop()
        self._app.stop_practice_session()
        self._start_button.setEnabled(True)
        self._stop_button.setEnabled(False)
        self._section_combo.setEnabled(True)
        self._mode_combo.setEnabled(True)

    def _on_tick(self) -> None:
        engine = self._app.practice_engine
        if engine is None:
            self._timer.stop()
            return
        now = self._app.clock.now_ms()
        elapsed = max(0.0, now - self._last_tick_ms)
        self._last_tick_ms = now
        engine.advance(elapsed)

    # --- Live updates ---------------------------------------------------------------
    def _on_playhead_updated(self, t_ms: float) -> None:
        self._piano_roll.set_playhead_ms(t_ms)
        upcoming = {
            n.pitch_midi
            for n in self._section_notes
            if t_ms <= n.start_ms <= t_ms + 200.0
        }
        self._piano.set_expected_pitches(upcoming)

    def _on_feedback(self, feedback: PracticeFeedbackEvent) -> None:
        item = QListWidgetItem(feedback.message)
        item.setForeground(QColor(_FEEDBACK_COLOR.get(feedback.type, theme.IVORY)))
        self._feedback_list.insertItem(0, item)
        while self._feedback_list.count() > 50:
            self._feedback_list.takeItem(self._feedback_list.count() - 1)

        if feedback.type == FeedbackType.PROGRESS:
            return

        for pitch in feedback.related_pitches:
            self._active_pitch_states[pitch] = feedback.type.value
            self._piano.set_active_states(dict(self._active_pitch_states))
            QTimer.singleShot(PITCH_HIGHLIGHT_DECAY_MS, lambda p=pitch: self._clear_pitch_state(p))

            near_ms = self._piano_roll.playhead_ms
            note = self._find_nearest_note(pitch, near_ms)
            if note is not None:
                self._piano_roll.set_note_outcome(note.note_id, feedback.type.value)

    def _clear_pitch_state(self, pitch: int) -> None:
        self._active_pitch_states.pop(pitch, None)
        self._piano.set_active_states(dict(self._active_pitch_states))

    def _find_nearest_note(self, pitch_midi: int, near_ms: float) -> Optional[ExpectedNote]:
        candidates = [n for n in self._section_notes if n.pitch_midi == pitch_midi]
        if not candidates:
            return None
        nearest = min(candidates, key=lambda n: abs(n.start_ms - near_ms))
        if abs(nearest.start_ms - near_ms) > NEAREST_NOTE_SEARCH_WINDOW_MS:
            return None
        return nearest

    def _on_score_updated(self, payload: dict) -> None:
        total = payload.get("total", 0.0)
        self._score_bar.setValue(int(round(total * 100)))
        self._score_detail_label.setText(
            "Notes {:.0%} · Chords {:.0%} · Timing {:.0%} · Consistency {:.0%}".format(
                payload.get("note_accuracy", 0.0),
                payload.get("chord_completeness", 0.0),
                payload.get("timing", 0.0),
                payload.get("consistency", 0.0),
            )
        )

    def _on_pass_finished(self, result) -> None:
        self._mastery_label.setText(
            f"Streak {result.mastery.consecutive_passes} · Loop {result.loop_count}"
            + (" · Mastered!" if result.mastery.mastered else "")
        )
        if result.mastery.mastered:
            self._stop_practice(user_initiated=False)

    def _on_stream_error(self, message: str) -> None:
        QMessageBox.warning(self, "Audio error", message)
        self._stop_practice(user_initiated=False)
