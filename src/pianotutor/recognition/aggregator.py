"""Worker-thread pipeline turning buffered audio frames into note/chord events.

Subscribes to ``Topic.AUDIO_FRAME_READY`` with a queue hand-off callback that
is safe to call on the audio callback thread (an O(1) ``put_nowait``, never
blocks, drops a frame rather than risk stalling capture). All filtering,
onset detection, pitch/chord estimation, confidence scoring, and
started/sustained/released state tracking happens on a dedicated worker
thread that pulls from that queue, per the runtime architecture's threading
model.
"""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np

from pianotutor.audio.latency import compensate_timestamp
from pianotutor.audio.monitor import SignalMonitor
from pianotutor.audio.ring_buffer import RingBuffer
from pianotutor.audio.stream import AudioFrameReady
from pianotutor.dsp.filters import dc_block, piano_bandpass
from pianotutor.dsp.onset import OnsetDetector
from pianotutor.dsp.spectrum import compute_magnitude_spectrum, freq_to_midi
from pianotutor.recognition.confidence import (
    monophonic_confidence,
    polyphonic_confidence,
    snr_ratio,
)
from pianotutor.recognition.note_events import DetectedNoteEvent, NoteState
from pianotutor.recognition.pitch_tracker import estimate_pitch_yin
from pianotutor.recognition.polyphony import estimate_chord_pitches
from pianotutor.services.clock import Clock
from pianotutor.services.event_bus import EventBus
from pianotutor.services.event_types import Topic

logger = logging.getLogger(__name__)

SUSTAIN_PUBLISH_THROTTLE_MS = 150.0


@dataclass
class _ActiveNote:
    pitch_midi: int
    confidence: float
    last_seen_t_ms: float
    started_t_ms: float
    last_sustain_publish_ms: float


class RecognitionAggregator:
    """Consumes buffered audio and emits ``NOTE_DETECTED`` / ``CHORD_DETECTED`` events."""

    def __init__(
        self,
        ring_buffer: RingBuffer,
        event_bus: EventBus,
        clock: Clock,
        sample_rate: int,
        analysis_window_ms: float = 100.0,
        mono_clarity_threshold: float = 0.5,
        note_timeout_ms: float = 400.0,
        max_queue_size: int = 64,
        latency_compensation_ms: float = 0.0,
    ):
        self._ring_buffer = ring_buffer
        self._event_bus = event_bus
        self._clock = clock
        self._sample_rate = sample_rate
        self._analysis_window_samples = max(1, int(sample_rate * analysis_window_ms / 1000.0))
        self._mono_clarity_threshold = mono_clarity_threshold
        self._note_timeout_ms = note_timeout_ms
        self._latency_compensation_ms = latency_compensation_ms

        self._queue: "queue.Queue[AudioFrameReady]" = queue.Queue(maxsize=max_queue_size)
        self._onset_detector = OnsetDetector(sample_rate)
        self._monitor = SignalMonitor()
        self._active_notes: Dict[int, _ActiveNote] = {}

        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._dropped_frames = 0
        self._unsubscribe = None

    @property
    def dropped_frame_count(self) -> int:
        return self._dropped_frames

    def set_latency_compensation_ms(self, latency_ms: float) -> None:
        self._latency_compensation_ms = latency_ms

    def start(self) -> None:
        self._running.set()
        self._unsubscribe = self._event_bus.subscribe(Topic.AUDIO_FRAME_READY, self._on_frame_ready)
        self._thread = threading.Thread(
            target=self._run_loop, name="RecognitionWorker", daemon=True
        )
        self._thread.start()
        logger.info("Recognition aggregator started")

    def stop(self) -> None:
        self._running.clear()
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("Recognition aggregator stopped")

    # --- Audio thread: must never block. -----------------------------------
    def _on_frame_ready(self, frame: AudioFrameReady) -> None:
        try:
            self._queue.put_nowait(frame)
        except queue.Full:
            self._dropped_frames += 1

    # --- Worker thread. -------------------------------------------------------
    def _run_loop(self) -> None:
        while self._running.is_set():
            try:
                frame = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            try:
                self._process_frame(frame)
            except Exception:  # noqa: BLE001 - one bad block must not kill the worker
                logger.exception("Error processing audio frame in recognition worker")

    def _process_frame(self, frame: AudioFrameReady) -> None:
        t_ms = frame.timestamp_ms

        level = self._monitor.process(frame.samples)
        self._event_bus.publish(Topic.AUDIO_LEVEL_UPDATED, level)

        if level.is_silence:
            self._release_all_active_notes(t_ms)
            return

        analysis = self._ring_buffer.read_latest(self._analysis_window_samples)
        conditioned = dc_block(analysis, self._sample_rate)
        conditioned = piano_bandpass(conditioned, self._sample_rate)

        onset = self._onset_detector.process(conditioned, t_ms)
        onset_strength_ratio = (
            min(1.0, onset.flux / (onset.threshold * 2)) if onset.threshold > 0 else 0.0
        )
        snr = snr_ratio(level.rms, level.noise_floor_rms)

        if onset.is_onset:
            self._handle_onset(conditioned, t_ms, snr, onset_strength_ratio)
        else:
            self._update_sustain_and_release(conditioned, t_ms)

    def _handle_onset(
        self, conditioned: np.ndarray, t_ms: float, snr: float, onset_strength_ratio: float
    ) -> None:
        yin = estimate_pitch_yin(conditioned, self._sample_rate)

        if yin is not None and yin.clarity >= self._mono_clarity_threshold:
            pitch = int(round(freq_to_midi(yin.freq_hz)))
            confidence = monophonic_confidence(yin.clarity, snr, onset_strength_ratio)
            self._start_note(pitch, t_ms, confidence, onset_strength_ratio)
            return

        spectrum = compute_magnitude_spectrum(conditioned, self._sample_rate)
        candidates = estimate_chord_pitches(spectrum)
        if not candidates:
            return

        peak_salience = max(c.salience for c in candidates)
        confidences = []
        for candidate in candidates:
            confidence = polyphonic_confidence(
                candidate.salience, peak_salience, snr, onset_strength_ratio
            )
            confidences.append(confidence)
            self._start_note(candidate.pitch_midi, t_ms, confidence, onset_strength_ratio)

        if len(candidates) >= 2:
            self._event_bus.publish(
                Topic.CHORD_DETECTED,
                {
                    "pitches_midi": [c.pitch_midi for c in candidates],
                    "t_start_ms": t_ms,
                    "t_end_ms": t_ms,
                    "confidence": float(np.mean(confidences)),
                },
            )

    def _update_sustain_and_release(self, conditioned: np.ndarray, t_ms: float) -> None:
        if not self._active_notes:
            return

        spectrum = compute_magnitude_spectrum(conditioned, self._sample_rate)
        still_present = {c.pitch_midi for c in estimate_chord_pitches(spectrum, max_notes=6)}

        for pitch, active in list(self._active_notes.items()):
            if pitch in still_present:
                active.last_seen_t_ms = t_ms
                if t_ms - active.last_sustain_publish_ms >= SUSTAIN_PUBLISH_THROTTLE_MS:
                    active.last_sustain_publish_ms = t_ms
                    self._publish_note_event(pitch, NoteState.SUSTAINED, t_ms, active.confidence, None)
            elif t_ms - active.last_seen_t_ms > self._note_timeout_ms:
                self._release_note(pitch, t_ms)

    def _release_all_active_notes(self, t_ms: float) -> None:
        for pitch in list(self._active_notes.keys()):
            self._release_note(pitch, t_ms)

    def _start_note(
        self, pitch_midi: int, t_ms: float, confidence: float, onset_strength_ratio: float
    ) -> None:
        if pitch_midi in self._active_notes:
            # A fresh onset on an already-sounding pitch is a retrigger/repeat
            # strike, not a continuation: close out the old instance first.
            self._release_note(pitch_midi, t_ms)

        self._active_notes[pitch_midi] = _ActiveNote(
            pitch_midi=pitch_midi,
            confidence=confidence,
            last_seen_t_ms=t_ms,
            started_t_ms=t_ms,
            last_sustain_publish_ms=t_ms,
        )
        self._publish_note_event(
            pitch_midi, NoteState.STARTED, t_ms, confidence, onset_strength_ratio
        )

    def _release_note(self, pitch_midi: int, t_ms: float) -> None:
        active = self._active_notes.pop(pitch_midi, None)
        if active is None:
            return
        self._publish_note_event(pitch_midi, NoteState.RELEASED, t_ms, active.confidence, None)

    def _publish_note_event(
        self,
        pitch_midi: int,
        state: NoteState,
        t_ms: float,
        confidence: float,
        velocity_like: Optional[float],
    ) -> None:
        compensated_t_ms = compensate_timestamp(t_ms, self._latency_compensation_ms)
        event = DetectedNoteEvent(
            pitch_midi=pitch_midi,
            state=state,
            t_ms=compensated_t_ms,
            confidence=confidence,
            velocity_like=velocity_like,
        )
        self._event_bus.publish(Topic.NOTE_DETECTED, event)
