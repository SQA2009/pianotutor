"""Shared event/topic names used on the in-process event bus.

Keeping topic names centralized avoids typos causing silently-dropped
subscriptions, and documents, in one place, the full set of cross-subsystem
events flowing through the app.
"""

from __future__ import annotations

from enum import Enum


class Topic(str, Enum):
    """Event bus topic names.

    The string value is what actually flows over the bus, so topics stay
    stable even if the enum member names are refactored.
    """

    # Audio subsystem
    AUDIO_FRAME_READY = "audio.frame_ready"
    AUDIO_DEVICE_LIST_CHANGED = "audio.device_list_changed"
    AUDIO_LEVEL_UPDATED = "audio.level_updated"
    AUDIO_STREAM_STARTED = "audio.stream_started"
    AUDIO_STREAM_STOPPED = "audio.stream_stopped"
    AUDIO_STREAM_ERROR = "audio.stream_error"

    # Recognition subsystem
    NOTE_DETECTED = "recognition.note_detected"
    CHORD_DETECTED = "recognition.chord_detected"

    # MIDI / song import
    SONG_IMPORTED = "midi.song_imported"
    SONG_IMPORT_FAILED = "midi.song_import_failed"

    # Practice engine
    PRACTICE_FEEDBACK = "practice.feedback"
    PRACTICE_SCORE_UPDATED = "practice.score_updated"
    PRACTICE_SESSION_STARTED = "practice.session_started"
    PRACTICE_SESSION_ENDED = "practice.session_ended"
    PRACTICE_EXCERPT_LOOPED = "practice.excerpt_looped"
    PRACTICE_MASTERY_ACHIEVED = "practice.mastery_achieved"
    PRACTICE_PLAYHEAD_UPDATED = "practice.playhead_updated"

    # Calibration
    CALIBRATION_STEP_CHANGED = "calibration.step_changed"
    CALIBRATION_SAMPLE_COLLECTED = "calibration.sample_collected"
    CALIBRATION_COMPLETED = "calibration.completed"

    # App lifecycle
    APP_ERROR = "app.error"
