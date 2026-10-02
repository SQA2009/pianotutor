"""Calibration profile model and persistence conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from pianotutor.persistence.models import CalibrationProfileRecord


@dataclass(frozen=True)
class CalibrationProfile:
    name: str
    device_name: str
    latency_ms: float
    latency_stddev_ms: float
    noise_floor_rms: float
    recommended_onset_threshold: float
    sample_count: int
    created_at: str | None = None

    def to_record(self, is_active: bool = True) -> CalibrationProfileRecord:
        return CalibrationProfileRecord(
            id=None,
            name=self.name,
            device_name=self.device_name,
            latency_ms=self.latency_ms,
            latency_stddev_ms=self.latency_stddev_ms,
            noise_floor_rms=self.noise_floor_rms,
            recommended_onset_threshold=self.recommended_onset_threshold,
            sample_count=self.sample_count,
            is_active=is_active,
            created_at=self.created_at or datetime.now(timezone.utc).isoformat(),
        )

    @classmethod
    def from_record(cls, record: CalibrationProfileRecord) -> "CalibrationProfile":
        return cls(
            name=record.name,
            device_name=record.device_name,
            latency_ms=record.latency_ms,
            latency_stddev_ms=record.latency_stddev_ms,
            noise_floor_rms=record.noise_floor_rms,
            recommended_onset_threshold=record.recommended_onset_threshold,
            sample_count=record.sample_count,
            created_at=record.created_at,
        )
