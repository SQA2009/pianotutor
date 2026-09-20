"""Main window: tabbed navigation between the home/practice/calibration/progress views."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMainWindow, QTabWidget

from pianotutor.ui.views.calibration_view import CalibrationView
from pianotutor.ui.views.home_view import HomeView
from pianotutor.ui.views.practice_view import PracticeView
from pianotutor.ui.views.progress_view import ProgressView

if TYPE_CHECKING:
    from pianotutor.app import Application

TAB_HOME = 0
TAB_PRACTICE = 1
TAB_CALIBRATION = 2
TAB_PROGRESS = 3


class MainWindow(QMainWindow):
    def __init__(self, app: "Application"):
        super().__init__()
        self._app = app
        self.setWindowTitle("PianoTutor")
        self.resize(1150, 820)

        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)

        self._home_view = HomeView(app)
        self._practice_view = PracticeView(app)
        self._calibration_view = CalibrationView(app)
        self._progress_view = ProgressView(app)

        self._tabs.addTab(self._home_view, "Home")
        self._tabs.addTab(self._practice_view, "Practice")
        self._tabs.addTab(self._calibration_view, "Calibrate")
        self._tabs.addTab(self._progress_view, "Progress")

        self._home_view.practice_requested.connect(self._on_practice_requested)
        self._home_view.calibrate_requested.connect(lambda: self._tabs.setCurrentIndex(TAB_CALIBRATION))
        self._calibration_view.finished.connect(self._on_calibration_finished)
        self._tabs.currentChanged.connect(self._on_tab_changed)

    def _on_practice_requested(self, song_id: int) -> None:
        self._practice_view.load_song(song_id)
        self._tabs.setCurrentIndex(TAB_PRACTICE)

    def _on_calibration_finished(self) -> None:
        self._tabs.setCurrentIndex(TAB_HOME)

    def _on_tab_changed(self, index: int) -> None:
        if index == TAB_HOME:
            self._home_view.refresh()
        elif index == TAB_PROGRESS:
            self._progress_view.refresh()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        self._app.shutdown()
        super().closeEvent(event)
