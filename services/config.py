"""Central application configuration.

Holds the tunable defaults called out in section 4/5 of the development
plan (tolerance windows, chord grouping window, confidence thresholds,
scoring weights) plus audio and filesystem defaults. A single ``AppConfig``
instance is created once in ``pianotutor.app.Application`` and passed down
to every subsystem that needs it, rather than subsystems reaching for
globals — this keeps everything unit-testable with alternate configs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def default_app_data_dir() -> Path:
    """Return the per-user app-data directory, honoring Windows conventions."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "PianoTutor"
    # Non-Windows fallback (development/CI on Linux/macOS).
    return Path.home() / ".pianotutor"


@dataclass(frozen=True)
class ToleranceConfig:
    """Matching tolerance defaults (v1), see development plan section 4."""

    guided_timing_tolerance_ms: float = 180.0
    continuous_timing_tolerance_ms: float = 120.0
    chord_grouping_window_ms: float = 80.0
    uncertain_confidence_threshold: float = 0.60
    hard_mismatch_confidence_threshold: float = 0.85


@dataclass(frozen=True)
class ScoringWeights:
    """Weighted scoring model defaults (v1), see development plan section 5."""

    note_accuracy: float = 0.40
    chord_completeness: float = 0.30
    timing: float = 0.20
    consistency: float = 0.10

    def __post_init__(self) -> None:
        total = self.note_accuracy + self.chord_completeness + self.timing + self.consistency
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Scoring weights must sum to 1.0, got {total}")


@dataclass(frozen=True)
class AudioConfig:
    """Audio capture defaults."""

    sample_rate: int = 44100
    block_size: int = 1024  # frames per callback (~23ms @ 44.1kHz)
    channels: int = 1
    ring_buffer_seconds: float = 5.0
    clipping_threshold: float = 0.98
    silence_rms_threshold: float = 0.01


@dataclass(frozen=True)
class MasteryConfig:
    """Excerpt loop-to-mastery defaults."""

    consecutive_passes_required: int = 3
    pass_score_threshold: float = 0.85


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration."""

    app_data_dir: Path = field(default_factory=default_app_data_dir)
    tolerance: ToleranceConfig = field(default_factory=ToleranceConfig)
    scoring: ScoringWeights = field(default_factory=ScoringWeights)
    audio: AudioConfig = field(default_factory=AudioConfig)
    mastery: MasteryConfig = field(default_factory=MasteryConfig)

    @property
    def db_path(self) -> Path:
        return self.app_data_dir / "pianotutor.db"

    @property
    def log_dir(self) -> Path:
        return self.app_data_dir / "logs"

    def ensure_directories(self) -> None:
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
