"""Collects note-on timing samples for guided calibration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pianotutor.audio.latency import LatencySample
from pianotutor.recognition.note_events import NoteState
from pianotutor.services.event_types import Topic


@dataclass
class _PendingCue:
    cue_t_ms: float
    cue_pitch_midi: int


class CalibrationCollector:
    def __init__(self, event_bus):
        self._event_bus = event_bus
        self._pending: Optional[_PendingCue] = None
        self._samples: list[LatencySample] = []
        self._noise_floor_rms = 0.01
        self._subs = [
            event_bus.subscribe(Topic.NOTE_DETECTED, self._on_note_detected),
            event_bus.subscribe(Topic.AUDIO_LEVEL_UPDATED, self._on_level_updated),
        ]

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    @property
    def samples(self) -> list[LatencySample]:
        return list(self._samples)

    @property
    def noise_floor_rms(self) -> float:
        return self._noise_floor_rms

    def arm_for_cue(self, cue_t_ms: float, cue_pitch_midi: int) -> None:
        self._pending = _PendingCue(cue_t_ms=cue_t_ms, cue_pitch_midi=cue_pitch_midi)

    def _on_note_detected(self, event) -> None:
        if self._pending is None or event is None:
            return
        if event.state != NoteState.STARTED:
            return
        if event.pitch_midi != self._pending.cue_pitch_midi:
            return

        self._samples.append(
            LatencySample(cue_t_ms=self._pending.cue_t_ms, detected_t_ms=float(event.t_ms))
        )
        self._event_bus.publish(Topic.CALIBRATION_SAMPLE_COLLECTED, self._samples[-1])
        self._pending = None

    def _on_level_updated(self, level) -> None:
        if level is None:
            return
        floor = float(getattr(level, "noise_floor_rms", 0.01))
        self._noise_floor_rms = max(1e-5, floor)

    def close(self) -> None:
        for unsub in self._subs:
            unsub()
        self._subs = []
        self._pending = None
