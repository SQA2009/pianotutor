"""The ``DetectedNoteEvent`` / ``DetectedChordEvent`` contracts, Recognition -> Practice."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class NoteState(str, Enum):
    STARTED = "started"
    SUSTAINED = "sustained"
    RELEASED = "released"


@dataclass(frozen=True)
class DetectedNoteEvent:
    pitch_midi: int
    state: NoteState
    t_ms: float
    confidence: float
    velocity_like: Optional[float] = None


@dataclass(frozen=True)
class DetectedChordEvent:
    pitches_midi: List[int]
    t_start_ms: float
    t_end_ms: float
    confidence: float
