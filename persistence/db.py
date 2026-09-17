"""SQLite connection management and migration runner.

Migrations are plain ``.sql`` files in ``persistence/migrations/``, named
``NNN_description.sql`` and applied in filename order. Applied versions are
tracked in the ``schema_version`` table (one row per applied migration
number, so ``MAX(version)`` gives the current schema version).
"""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_MIGRATION_FILENAME_RE = re.compile(r"^(\d+)_.*\.sql$")


class Database:
    """Owns a single SQLite connection and applies migrations on construction.

    Not thread-safe by itself — callers that need cross-thread access (e.g.
    persisting session events emitted from a worker thread) should either
    marshal writes through a single owner thread/queue, or construct one
    ``Database`` per thread pointed at the same file (SQLite handles that
    fine with WAL mode, which is enabled here).
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA foreign_keys=ON;")
        self._migrate()

    def _discover_migrations(self) -> list[tuple[int, Path]]:
        found = []
        for path in _MIGRATIONS_DIR.glob("*.sql"):
            match = _MIGRATION_FILENAME_RE.match(path.name)
            if match:
                found.append((int(match.group(1)), path))
        return sorted(found, key=lambda pair: pair[0])

    def _current_version(self) -> int:
        cur = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )
        if cur.fetchone() is None:
            return 0
        row = self.conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
        return row["v"] if row and row["v"] is not None else 0

    def _migrate(self) -> None:
        current = self._current_version()
        migrations = self._discover_migrations()
        applied = 0
        for version, path in migrations:
            if version <= current:
                continue
            logger.info("Applying migration %s", path.name)
            script = path.read_text(encoding="utf-8")
            with self.conn:
                self.conn.executescript(script)
                self.conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)", (version,)
                )
            applied += 1
        if applied:
            logger.info("Applied %d migration(s); schema now at version %d",
                        applied, self._current_version())

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self.conn:
            return self.conn.execute(sql, params)

    def executemany(self, sql: str, seq_of_params) -> sqlite3.Cursor:
        with self.conn:
            return self.conn.executemany(sql, seq_of_params)

    def query(self, sql: str, params: tuple = ()) -> Iterator[sqlite3.Row]:
        return self.conn.execute(sql, params)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
