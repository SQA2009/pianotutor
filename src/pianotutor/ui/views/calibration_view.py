"""Calibration view: device selection plus the guided latency/threshold workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pianotutor.audio.stream import AudioStreamError
from pianotutor.calibration.profiles import CalibrationProfile
from pianotutor.calibration.workflow import CalibrationStep, CalibrationStepState
from pianotutor.practice.feedback import pitch_name
from pianotutor.ui.viewmodels.calibration_vm import CalibrationViewModel
from pianotutor.ui.widgets.input_meter_widget import InputMeterPanel

if TYPE_CHECKING:
    from pianotutor.app import Application

TICK_INTERVAL_MS = 100


class CalibrationView(QWidget):
    finished = Signal()

    def __init__(self, app: "Application", parent=None):
        super().__init__(parent)
        self._app = app
        self._vm = CalibrationViewModel(app.event_bus)
        self._last_tick_ms = 0.0

        heading = QLabel("Calibrate your setup")
        heading.setProperty("role", "heading")

        self._device_combo = QComboBox()
        refresh_button = QPushButton("Refresh devices")
        refresh_button.clicked.connect(self._refresh_devices)

        device_row = QHBoxLayout()
        device_row.addWidget(QLabel("Input device:"))
        device_row.addWidget(self._device_combo, 1)
        device_row.addWidget(refresh_button)

        self._instructions_label = QLabel(
            "Pick your microphone or audio interface, then start calibration. "
            "You'll be asked to stay quiet for a moment, then play a few cued notes."
        )
        self._instructions_label.setWordWrap(True)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setTextVisible(True)

        self._meter_panel = InputMeterPanel()

        self._start_button = QPushButton("Start calibration")
        self._start_button.setProperty("role", "primary")
        self._start_button.clicked.connect(self._on_start_clicked)

        self._done_button = QPushButton("Done")
        self._done_button.clicked.connect(self.finished.emit)
        self._done_button.setEnabled(False)

        button_row = QHBoxLayout()
        button_row.addWidget(self._start_button)
        button_row.addWidget(self._done_button)
        button_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addLayout(device_row)
        layout.addWidget(self._instructions_label)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._meter_panel)
        layout.addLayout(button_row)
        layout.addStretch(1)

        self._timer = QTimer(self)
        self._timer.setInterval(TICK_INTERVAL_MS)
        self._timer.timeout.connect(self._on_tick)

        self._vm.step_changed.connect(self._on_step_changed)
        self._vm.completed.connect(self._on_completed)
        self._vm.level_updated.connect(self._meter_panel.set_level)

        self._refresh_devices()

    def _refresh_devices(self) -> None:
        self._device_combo.clear()
        for device in self._app.list_input_devices():
            label = f"{device.name} ({device.host_api_name})"
            self._device_combo.addItem(label, device.index)

    def _on_start_clicked(self) -> None:
        if self._device_combo.currentIndex() < 0:
            QMessageBox.information(self, "No device", "No audio input device was found.")
            return
        device_index = self._device_combo.currentData()

        try:
            self._app.start_calibration(device_index)
        except AudioStreamError as exc:
            QMessageBox.warning(self, "Couldn't start listening", str(exc))
            return

        self._start_button.setEnabled(False)
        self._done_button.setEnabled(False)
        self._device_combo.setEnabled(False)
        self._last_tick_ms = self._app.clock.now_ms()
        self._timer.start()

    def _on_tick(self) -> None:
        workflow = self._app.calibration_workflow
        if workflow is None:
            self._timer.stop()
            return
        now = self._app.clock.now_ms()
        elapsed = max(0.0, now - self._last_tick_ms)
        self._last_tick_ms = now
        workflow.advance(elapsed)

    def _on_step_changed(self, state: CalibrationStepState) -> None:
        if state.step == CalibrationStep.MEASURE_NOISE_FLOOR:
            self._instructions_label.setText(state.message or "Measuring background noise...")
            self._progress_bar.setValue(0)
            self._progress_bar.setFormat("Listening...")
        elif state.step == CalibrationStep.COLLECT_SAMPLES:
            note_text = f" ({pitch_name(state.cue_pitch_midi)})" if state.cue_pitch_midi is not None else ""
            self._instructions_label.setText(f"Play the note shown on the keyboard now{note_text}.")
            pct = int(100 * state.trial_index / max(1, state.trials_required))
            self._progress_bar.setValue(pct)
            self._progress_bar.setFormat(f"Trial {state.trial_index}/{state.trials_required}")
        elif state.step == CalibrationStep.ANALYZING:
            self._instructions_label.setText("Analyzing your calibration samples...")
            self._progress_bar.setValue(100)
            self._progress_bar.setFormat("Analyzing...")
        elif state.step == CalibrationStep.DONE:
            self._instructions_label.setText(state.message or "Calibration complete.")
            self._progress_bar.setValue(100)
            self._progress_bar.setFormat("Done")

    def _on_completed(self, profile: CalibrationProfile) -> None:
        self._timer.stop()
        self._app.stop_calibration()
        self._start_button.setEnabled(True)
        self._device_combo.setEnabled(True)
        self._done_button.setEnabled(True)
        self._instructions_label.setText(
            f"Calibration complete. Estimated latency {profile.latency_ms:.0f}ms "
            f"(±{profile.latency_stddev_ms:.0f}ms) from {profile.sample_count} samples."
        )
