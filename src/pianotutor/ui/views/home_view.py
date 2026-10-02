"""Home view: song library, import, and navigation actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
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
        subtitle = QLabel("Import MIDI files, then launch practice sessions from your library.")
        subtitle.setProperty("role", "subheading")

        self._songs_list = QListWidget()
        self._songs_list.currentItemChanged.connect(self._on_song_selection_changed)
        self._songs_list.itemDoubleClicked.connect(lambda _item: self._on_start_practice_clicked())

        self._empty_state_label = QLabel(
            "No songs yet. Use “Import MIDI” to add your first piece."
        )
        self._empty_state_label.setProperty("role", "hint")

        self._song_details_label = QLabel("Select a song to see details.")
        self._song_details_label.setProperty("role", "hint")
        self._song_details_label.setWordWrap(True)
        self._song_details_label.setMinimumHeight(44)

        details_frame = QFrame()
        details_layout = QVBoxLayout(details_frame)
        details_layout.setContentsMargins(10, 10, 10, 10)
        details_layout.addWidget(self._song_details_label)
        details_layout.addWidget(self._empty_state_label)

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
        layout.addWidget(subtitle)
        layout.addWidget(self._songs_list, 1)
        layout.addWidget(details_frame)
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
        if self._songs_list.currentItem() is None and self._songs_list.count() > 0:
            self._songs_list.setCurrentRow(0)
        self._update_details_panel()

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
            imported = self._app.import_song(path)
        except MidiParseError as exc:
            QMessageBox.warning(self, "Import failed", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Import failed", f"Unexpected error: {exc}")
            return

        self.refresh()
        QMessageBox.information(
            self,
            "Song imported",
            f"Imported “{imported.title}” with {len(imported.sections)} section(s).",
        )

    def _on_start_practice_clicked(self) -> None:
        song_id = self._selected_song_id()
        if song_id is None:
            QMessageBox.information(self, "No song selected", "Please select a song first.")
            return
        self.practice_requested.emit(int(song_id))

    def _on_song_selection_changed(self, _current, _previous) -> None:
        self._update_details_panel()

    def _update_details_panel(self) -> None:
        song_id = self._selected_song_id()
        has_songs = self._songs_list.count() > 0
        self._empty_state_label.setVisible(not has_songs)
        self._practice_button.setEnabled(song_id is not None)

        if song_id is None:
            self._song_details_label.setText("Select a song to see details.")
            return

        song = self._app.songs_repo.get_song(int(song_id))
        sections = self._app.songs_repo.get_sections(int(song_id))
        notes = self._app.songs_repo.get_notes(int(song_id))
        if song is None:
            self._song_details_label.setText("Selected song details are unavailable.")
            return

        source_name = Path(song.source_path).name
        duration_seconds = int(song.duration_ms // 1000)
        mins, secs = divmod(duration_seconds, 60)
        self._song_details_label.setText(
            f"{source_name} · {mins}:{secs:02d} · {len(notes)} notes · {len(sections)} sections"
        )
