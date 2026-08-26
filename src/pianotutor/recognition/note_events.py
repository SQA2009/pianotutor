"""
Compatibility re-export module for recognition-facing event models.
Use `pianotutor.services.event_types` as the canonical definitions.
"""

from pianotutor.services.event_types import (  # noqa: F401
    AudioFrameReady,
    DetectedChordEvent,
    DetectedNoteEvent,
    NoteState,
)
