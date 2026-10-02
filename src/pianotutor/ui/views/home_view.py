"""Home view: song library, import, and navigation actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pianotutor.midi.parser import MidiParseError

if TYPE_CHECKING:
    from pianotutor.app import Application


class HomeView(QWidget):
    practice_requested = Signal(int)
    calibrate_requested = Signal()

    def __init__(self, app: "Application", parent=None):
        super().__init__(parent)
        self._app = app

        heading = QLabel("Song Library")
        heading.setProperty("role", "heading")

        self._songs_list = QListWidget()

        import_button = QPushButton("Import MIDI")
        import_button.setProperty("role", "primary")
        import_button.clicked.connect(self._on_import_clicked)

        self._practice_button = QPushButton("Start practice")
        self._practice_button.clicked.connect(self._on_start_practice_clicked)

        calibrate_button = QPushButton("Calibrate input")
        calibrate_button.clicked.connect(self.calibrate_requested.emit)

        button_row = QHBoxLayout()
        button_row.addWidget(import_button)
        button_row.addWidget(self._practice_button)
        button_row.addWidget(calibrate_button)
        button_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(self._songs_list, 1)
        layout.addLayout(button_row)

        self.refresh()

    def refresh(self) -> None:
        selected_song_id = self._selected_song_id()
        self._songs_list.clear()

        songs = self._app.songs_repo.list_songs()
        for song in songs:
            item = QListWidgetItem(song.title)
            item.setData(32, song.id)
            self._songs_list.addItem(item)
            if song.id == selected_song_id:
                self._songs_list.setCurrentItem(item)

        self._practice_button.setEnabled(self._songs_list.count() > 0)

    def _selected_song_id(self) -> int | None:
        current = self._songs_list.currentItem()
        if current is None:
            return None
        return current.data(32)

    def _on_import_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import MIDI file",
            "",
            "MIDI files (*.mid *.midi)",
        )
        if not path:
            return

        try:
            self._app.import_song(path)
        except MidiParseError as exc:
            QMessageBox.warning(self, "Import failed", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Import failed", f"Unexpected error: {exc}")
            return

        self.refresh()

    def _on_start_practice_clicked(self) -> None:
        song_id = self._selected_song_id()
        if song_id is None:
            QMessageBox.information(self, "No song selected", "Please select a song first.")
            return
        self.practice_requested.emit(int(song_id))
