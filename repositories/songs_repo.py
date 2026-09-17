"""Repository for songs, their notes, and their practice sections."""

from __future__ import annotations

from typing import List, Optional

from pianotutor.persistence.db import Database
from pianotutor.persistence.models import (
    SongNoteRecord,
    SongRecord,
    SongSectionRecord,
)


class SongsRepository:
    def __init__(self, db: Database):
        self._db = db

    def insert_song(self, song: SongRecord) -> int:
        cur = self._db.execute(
            """
            INSERT INTO songs (title, source_path, ppq, duration_ms,
                                tempo_map_json, time_signature_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                song.title,
                song.source_path,
                song.ppq,
                song.duration_ms,
                song.tempo_map_json,
                song.time_signature_json,
            ),
        )
        return int(cur.lastrowid)

    def insert_notes(self, song_id: int, notes: List[SongNoteRecord]) -> None:
        self._db.executemany(
            """
            INSERT INTO song_notes (song_id, note_index, pitch_midi, start_ms,
                                     end_ms, hand, track_id, velocity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    song_id,
                    n.note_index,
                    n.pitch_midi,
                    n.start_ms,
                    n.end_ms,
                    n.hand,
                    n.track_id,
                    n.velocity,
                )
                for n in notes
            ],
        )

    def insert_sections(self, song_id: int, sections: List[SongSectionRecord]) -> None:
        self._db.executemany(
            """
            INSERT INTO song_sections (song_id, section_index, label, start_ms, end_ms)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (song_id, s.section_index, s.label, s.start_ms, s.end_ms)
                for s in sections
            ],
        )

    def get_song(self, song_id: int) -> Optional[SongRecord]:
        row = self._db.query("SELECT * FROM songs WHERE id = ?", (song_id,)).fetchone()
        if row is None:
            return None
        return SongRecord(
            id=row["id"],
            title=row["title"],
            source_path=row["source_path"],
            ppq=row["ppq"],
            duration_ms=row["duration_ms"],
            tempo_map_json=row["tempo_map_json"],
            time_signature_json=row["time_signature_json"],
            imported_at=row["imported_at"],
        )

    def list_songs(self) -> List[SongRecord]:
        rows = self._db.query("SELECT * FROM songs ORDER BY imported_at DESC").fetchall()
        return [
            SongRecord(
                id=r["id"],
                title=r["title"],
                source_path=r["source_path"],
                ppq=r["ppq"],
                duration_ms=r["duration_ms"],
                tempo_map_json=r["tempo_map_json"],
                time_signature_json=r["time_signature_json"],
                imported_at=r["imported_at"],
            )
            for r in rows
        ]

    def get_notes(self, song_id: int) -> List[SongNoteRecord]:
        rows = self._db.query(
            "SELECT * FROM song_notes WHERE song_id = ? ORDER BY start_ms, note_index",
            (song_id,),
        ).fetchall()
        return [
            SongNoteRecord(
                id=r["id"],
                song_id=r["song_id"],
                note_index=r["note_index"],
                pitch_midi=r["pitch_midi"],
                start_ms=r["start_ms"],
                end_ms=r["end_ms"],
                hand=r["hand"],
                track_id=r["track_id"],
                velocity=r["velocity"],
            )
            for r in rows
        ]

    def get_sections(self, song_id: int) -> List[SongSectionRecord]:
        rows = self._db.query(
            "SELECT * FROM song_sections WHERE song_id = ? ORDER BY section_index",
            (song_id,),
        ).fetchall()
        return [
            SongSectionRecord(
                id=r["id"],
                song_id=r["song_id"],
                section_index=r["section_index"],
                label=r["label"],
                start_ms=r["start_ms"],
                end_ms=r["end_ms"],
            )
            for r in rows
        ]

    def delete_song(self, song_id: int) -> None:
        self._db.execute("DELETE FROM songs WHERE id = ?", (song_id,))
