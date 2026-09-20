"""Persistence-facing dataclasses.

These mirror the SQLite schema (``migrations/001_init.sql``) closely and are
what repositories return/accept. They are intentionally separate from the
runtime dataclasses in ``midi.timeline`` / ``practice.engine`` / etc. so that
storage-shape changes don't ripple into the real-time pipeline's types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SongRecord:
    id: Optional[int]
    title: str
    source_path: str
    ppq: int
    duration_ms: float
    tempo_map_json: str
    time_signature_json: str
    imported_at: Optional[str] = None


@dataclass
class SongNoteRecord:
    id: Optional[int]
    song_id: int
    note_index: int
    pitch_midi: int
    start_ms: float
    end_ms: float
    hand: str = "unknown"
    track_id: int = 0
    velocity: int = 64


@dataclass
class SongSectionRecord:
    id: Optional[int]
    song_id: int
    section_index: int
    label: str
    start_ms: float
    end_ms: float


@dataclass
class PracticeSessionRecord:
    id: Optional[int]
    song_id: int
    mode: str
    section_id: Optional[int] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    total_score: Optional[float] = None
    note_accuracy_score: Optional[float] = None
    chord_completeness_score: Optional[float] = None
    timing_score: Optional[float] = None
    consistency_score: Optional[float] = None
    loop_count: int = 0
    mastered: bool = False


@dataclass
class SessionEventRecord:
    id: Optional[int]
    session_id: int
    t_ms: float
    event_type: str
    related_pitches: List[int] = field(default_factory=list)
    score_delta: float = 0.0
    message: str = ""


@dataclass
class CalibrationProfileRecord:
    id: Optional[int]
    name: str
    device_name: str
    latency_ms: float
    latency_stddev_ms: float
    noise_floor_rms: float
    recommended_onset_threshold: float
    sample_count: int
    is_active: bool = False
    created_at: Optional[str] = None
