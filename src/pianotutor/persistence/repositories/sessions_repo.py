"""Repository for practice sessions and their per-event history."""

from __future__ import annotations

import json
from typing import List, Optional

from pianotutor.persistence.db import Database
from pianotutor.persistence.models import PracticeSessionRecord, SessionEventRecord


class SessionsRepository:
    def __init__(self, db: Database):
        self._db = db

    def start_session(self, session: PracticeSessionRecord) -> int:
        cur = self._db.execute(
            """
            INSERT INTO practice_sessions (song_id, section_id, mode)
            VALUES (?, ?, ?)
            """,
            (session.song_id, session.section_id, session.mode),
        )
        return int(cur.lastrowid)

    def update_progress(self, session_id: int, session: PracticeSessionRecord) -> None:
        """Persist an intermediate loop pass's score/loop_count without finalizing
        the session (``ended_at`` is left untouched — see :meth:`end_session`)."""
        self._db.execute(
            """
            UPDATE practice_sessions
            SET total_score = ?,
                note_accuracy_score = ?,
                chord_completeness_score = ?,
                timing_score = ?,
                consistency_score = ?,
                loop_count = ?,
                mastered = ?
            WHERE id = ?
            """,
            (
                session.total_score,
                session.note_accuracy_score,
                session.chord_completeness_score,
                session.timing_score,
                session.consistency_score,
                session.loop_count,
                int(session.mastered),
                session_id,
            ),
        )

    def end_session(self, session_id: int, session: PracticeSessionRecord) -> None:
        self._db.execute(
            """
            UPDATE practice_sessions
            SET ended_at = datetime('now'),
                total_score = ?,
                note_accuracy_score = ?,
                chord_completeness_score = ?,
                timing_score = ?,
                consistency_score = ?,
                loop_count = ?,
                mastered = ?
            WHERE id = ?
            """,
            (
                session.total_score,
                session.note_accuracy_score,
                session.chord_completeness_score,
                session.timing_score,
                session.consistency_score,
                session.loop_count,
                int(session.mastered),
                session_id,
            ),
        )

    def add_event(self, event: SessionEventRecord) -> int:
        cur = self._db.execute(
            """
            INSERT INTO session_events (session_id, t_ms, event_type,
                                         related_pitches_json, score_delta, message)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event.session_id,
                event.t_ms,
                event.event_type,
                json.dumps(event.related_pitches),
                event.score_delta,
                event.message,
            ),
        )
        return int(cur.lastrowid)

    def get_session(self, session_id: int) -> Optional[PracticeSessionRecord]:
        row = self._db.query(
            "SELECT * FROM practice_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    def list_sessions_for_song(self, song_id: int) -> List[PracticeSessionRecord]:
        rows = self._db.query(
            "SELECT * FROM practice_sessions WHERE song_id = ? ORDER BY started_at DESC",
            (song_id,),
        ).fetchall()
        return [self._row_to_session(r) for r in rows]

    def get_events(self, session_id: int) -> List[SessionEventRecord]:
        rows = self._db.query(
            "SELECT * FROM session_events WHERE session_id = ? ORDER BY t_ms",
            (session_id,),
        ).fetchall()
        return [
            SessionEventRecord(
                id=r["id"],
                session_id=r["session_id"],
                t_ms=r["t_ms"],
                event_type=r["event_type"],
                related_pitches=json.loads(r["related_pitches_json"]),
                score_delta=r["score_delta"],
                message=r["message"],
            )
            for r in rows
        ]

    @staticmethod
    def _row_to_session(row) -> PracticeSessionRecord:
        return PracticeSessionRecord(
            id=row["id"],
            song_id=row["song_id"],
            section_id=row["section_id"],
            mode=row["mode"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            total_score=row["total_score"],
            note_accuracy_score=row["note_accuracy_score"],
            chord_completeness_score=row["chord_completeness_score"],
            timing_score=row["timing_score"],
            consistency_score=row["consistency_score"],
            loop_count=row["loop_count"],
            mastered=bool(row["mastered"]),
        )
