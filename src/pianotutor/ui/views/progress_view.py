"""Progress view: per-song session history, scores, and mastery status."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from pianotutor.app import Application


class ProgressView(QWidget):
    def __init__(self, app: "Application", parent=None):
        super().__init__(parent)
        self._app = app

        heading = QLabel("Progress")
        heading.setProperty("role", "heading")
        subtitle = QLabel("Track session quality, mastery progress, and loop consistency.")
        subtitle.setProperty("role", "subheading")

        self._song_combo = QComboBox()
        self._song_combo.currentIndexChanged.connect(self._on_song_changed)

        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Song:"))
        header_row.addWidget(self._song_combo, 1)

        self._table = QTableWidget(0, 8)
        self._table.setHorizontalHeaderLabels(
            ["Started", "Mode", "Total", "Notes", "Chords", "Timing", "Consistency", "Loops"]
        )
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.setSelectionMode(QAbstractItemView.NoSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)

        self._empty_label = QLabel("No sessions yet for this song.")
        self._empty_label.setProperty("role", "hint")

        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(subtitle)
        layout.addLayout(header_row)
        layout.addWidget(self._table)
        layout.addWidget(self._empty_label)

    def refresh(self) -> None:
        current_song_id = self._song_combo.currentData()
        self._song_combo.blockSignals(True)
        self._song_combo.clear()
        for song in self._app.songs_repo.list_songs():
            self._song_combo.addItem(song.title, song.id)
        if current_song_id is not None:
            idx = self._song_combo.findData(current_song_id)
            if idx >= 0:
                self._song_combo.setCurrentIndex(idx)
        self._song_combo.blockSignals(False)
        self._reload_table()

    def _on_song_changed(self, _index: int) -> None:
        self._reload_table()

    def _reload_table(self) -> None:
        song_id = self._song_combo.currentData()
        self._table.setRowCount(0)
        if song_id is None:
            self._empty_label.setVisible(True)
            return

        sessions = self._app.sessions_repo.list_sessions_for_song(int(song_id))
        self._table.setRowCount(len(sessions))
        self._empty_label.setVisible(len(sessions) == 0)
        for row, session in enumerate(sessions):
            self._table.setItem(row, 0, QTableWidgetItem(session.started_at or ""))
            mode_text = session.mode + (" · mastered" if session.mastered else "")
            self._table.setItem(row, 1, QTableWidgetItem(mode_text))
            self._table.setItem(row, 2, QTableWidgetItem(self._fmt(session.total_score)))
            self._table.setItem(row, 3, QTableWidgetItem(self._fmt(session.note_accuracy_score)))
            self._table.setItem(row, 4, QTableWidgetItem(self._fmt(session.chord_completeness_score)))
            self._table.setItem(row, 5, QTableWidgetItem(self._fmt(session.timing_score)))
            self._table.setItem(row, 6, QTableWidgetItem(self._fmt(session.consistency_score)))
            self._table.setItem(row, 7, QTableWidgetItem(str(session.loop_count)))

    @staticmethod
    def _fmt(value) -> str:
        return f"{value:.0%}" if value is not None else "—"
