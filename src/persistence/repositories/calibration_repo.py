"""Repository for calibration profiles.

Only one profile is "active" at a time (the one the practice engine and
recognition pipeline use for latency compensation / onset thresholds).
Activating a profile deactivates all others in the same transaction.
"""

from __future__ import annotations

from typing import List, Optional

from pianotutor.persistence.db import Database
from pianotutor.persistence.models import CalibrationProfileRecord


class CalibrationRepository:
    def __init__(self, db: Database):
        self._db = db

    def insert_profile(self, profile: CalibrationProfileRecord) -> int:
        cur = self._db.execute(
            """
            INSERT INTO calibration_profiles
                (name, device_name, latency_ms, latency_stddev_ms, noise_floor_rms,
                 recommended_onset_threshold, sample_count, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile.name,
                profile.device_name,
                profile.latency_ms,
                profile.latency_stddev_ms,
                profile.noise_floor_rms,
                profile.recommended_onset_threshold,
                profile.sample_count,
                int(profile.is_active),
            ),
        )
        new_id = int(cur.lastrowid)
        if profile.is_active:
            self.set_active(new_id)
        return new_id

    def set_active(self, profile_id: int) -> None:
        with self._db.conn:
            self._db.conn.execute("UPDATE calibration_profiles SET is_active = 0")
            self._db.conn.execute(
                "UPDATE calibration_profiles SET is_active = 1 WHERE id = ?",
                (profile_id,),
            )

    def get_active_profile(self) -> Optional[CalibrationProfileRecord]:
        row = self._db.query(
            "SELECT * FROM calibration_profiles WHERE is_active = 1 "
            "ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return self._row_to_profile(row)

    def list_profiles(self) -> List[CalibrationProfileRecord]:
        rows = self._db.query(
            "SELECT * FROM calibration_profiles ORDER BY created_at DESC"
        ).fetchall()
        return [self._row_to_profile(r) for r in rows]

    @staticmethod
    def _row_to_profile(row) -> CalibrationProfileRecord:
        return CalibrationProfileRecord(
            id=row["id"],
            name=row["name"],
            device_name=row["device_name"],
            latency_ms=row["latency_ms"],
            latency_stddev_ms=row["latency_stddev_ms"],
            noise_floor_rms=row["noise_floor_rms"],
            recommended_onset_threshold=row["recommended_onset_threshold"],
            sample_count=row["sample_count"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
        )
