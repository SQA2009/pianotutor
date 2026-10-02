"""Key-value settings repository."""

from __future__ import annotations

from typing import Optional

from pianotutor.persistence.db import Database


class SettingsRepository:
    def __init__(self, db: Database):
        self._db = db

    def get(self, key: str) -> Optional[str]:
        row = self._db.query("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row["value"])

    def set(self, key: str, value: str) -> None:
        self._db.execute(
            """
            INSERT INTO app_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
