from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Sequence


class NoteState(str, Enum):
    STARTED = "started"
    SUSTAINED = "sustained"
    RELEASED = "released"


class FeedbackType(str, Enum):
    CORRECT = "correct"
    MISSING = "missing"
    EXTRA = "extra"
    LATE = "late"
    EARLY = "early"
    UNCERTAIN = "uncertain"
    PROGRESS = "progress"


@dataclass(frozen=True)
class AudioFrameReady:
    timestamp_ms: float
    frame_id: int
    sample_rate: int
    # Keep payload generic for scaffolding;
    # production type can be np.ndarray.
    samples: object


@dataclass(frozen=True)
class ExpectedNote:
    note_id: int
    pitch_midi: int
    start_ms: float
    end_ms: float
    hand: str = "unknown"  # left|right|unknown
    track_id: int = 0


@dataclass(frozen=True)
class DetectedNoteEvent:
    pitch_midi: int
    state: NoteState
    t_ms: float
    confidence: float
    velocity_like: Optional[float] = None
    raw_t_ms: Optional[float] = None
    latency_compensated: bool = True


@dataclass(frozen=True)
class DetectedChordEvent:
    pitches_midi: Sequence[int]
    t_start_ms: float
    t_end_ms: float
    confidence: float


@dataclass(frozen=True)
class PracticeFeedbackEvent:
    feedback_type: FeedbackType
    message: str
    related_pitches: Sequence[int] = field(default_factory=tuple)
    score_delta: float = 0.0
    confidence: Optional[float] = None


@dataclass(frozen=True)
class RenderState:
    playhead_ms: float
    expected_active_pitches: Sequence[int] = field(default_factory=tuple)
    detected_active_pitches: Sequence[int] = field(default_factory=tuple)
    current_measure: Optional[int] = None
    loop_enabled: bool = False
    loop_start_ms: Optional[float] = None
    loop_end_ms: Optional[float] = None
