"""Wires every subsystem together: audio, recognition, MIDI, practice,
calibration, persistence, and services. This is the one place in the
codebase that knows about all of them; every other module only knows its
own layer plus the small set of contracts it consumes/produces.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from pianotutor.audio.devices import DeviceManager, InputDevice
from pianotutor.audio.ring_buffer import RingBuffer
from pianotutor.audio.stream import AudioStream, AudioStreamError
from pianotutor.calibration.collector import CalibrationCollector
from pianotutor.calibration.profiles import CalibrationProfile
from pianotutor.calibration.workflow import CalibrationWorkflow
from pianotutor.midi.importer import ImportedSong, import_midi_file, load_song_timeline
from pianotutor.midi.sections import Section
from pianotutor.persistence.db import Database
from pianotutor.persistence.models import (
    PracticeSessionRecord,
    SessionEventRecord,
)
from pianotutor.persistence.repositories.calibration_repo import CalibrationRepository
from pianotutor.persistence.repositories.sessions_repo import SessionsRepository
from pianotutor.persistence.repositories.settings_repo import SettingsRepository
from pianotutor.persistence.repositories.songs_repo import SongsRepository
from pianotutor.practice.engine import PracticeEngine
from pianotutor.practice.modes import PracticeMode
from pianotutor.recognition.aggregator import RecognitionAggregator
from pianotutor.services.clock import SystemClock
from pianotutor.services.config import AppConfig
from pianotutor.services.event_bus import EventBus
from pianotutor.services.event_types import Topic
from pianotutor.services.logger import configure_logging

logger = logging.getLogger(__name__)

SETTING_LAST_DEVICE_INDEX = "last_device_index"


class Application:
    """Owns every subsystem's lifetime and exposes the operations the UI needs."""

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()
        self.config.ensure_directories()
        configure_logging(self.config.log_dir)

        self.event_bus = EventBus()
        self.clock = SystemClock()

        self.db = Database(self.config.db_path)
        self.songs_repo = SongsRepository(self.db)
        self.sessions_repo = SessionsRepository(self.db)
        self.calibration_repo = CalibrationRepository(self.db)
        self.settings_repo = SettingsRepository(self.db)

        self.device_manager = DeviceManager()

        self._ring_buffer = RingBuffer(
            capacity_samples=int(self.config.audio.sample_rate * self.config.audio.ring_buffer_seconds)
        )
        self._audio_stream: Optional[AudioStream] = None
        self._aggregator: Optional[RecognitionAggregator] = None

        self._practice_engine: Optional[PracticeEngine] = None
        self._practice_session_id: Optional[int] = None
        self._last_pass_result = None
        self._session_finalized = False

        self._calibration_collector: Optional[CalibrationCollector] = None
        self._calibration_workflow: Optional[CalibrationWorkflow] = None

        self._wire_session_persistence()
        logger.info("Application initialized. App data dir: %s", self.config.app_data_dir)

    # --- Devices / listening ---------------------------------------------------
    def list_input_devices(self) -> list[InputDevice]:
        return self.device_manager.list_input_devices()

    @property
    def is_listening(self) -> bool:
        return self._audio_stream is not None and self._audio_stream.is_running

    def start_listening(self, device_index: Optional[int] = None) -> None:
        if self.is_listening and device_index is None:
            return
        if self.is_listening:
            self.stop_listening()

        if device_index is None:
            stored = self.settings_repo.get(SETTING_LAST_DEVICE_INDEX)
            device_index = int(stored) if stored is not None else self.device_manager.get_default_input_index()
        if device_index is None:
            raise AudioStreamError("No audio input device is available.")

        self.device_manager.select_device(device_index)
        self.settings_repo.set(SETTING_LAST_DEVICE_INDEX, str(device_index))

        self._ring_buffer.clear()
        self._audio_stream = AudioStream(
            device_index=device_index,
            sample_rate=self.config.audio.sample_rate,
            block_size=self.config.audio.block_size,
            channels=self.config.audio.channels,
            ring_buffer=self._ring_buffer,
            event_bus=self.event_bus,
            clock=self.clock,
        )
        self._aggregator = RecognitionAggregator(
            ring_buffer=self._ring_buffer,
            event_bus=self.event_bus,
            clock=self.clock,
            sample_rate=self.config.audio.sample_rate,
        )
        active_profile = self.active_calibration_profile()
        if active_profile is not None:
            self._aggregator.set_latency_compensation_ms(active_profile.latency_ms)

        self._aggregator.start()
        self._audio_stream.start()

    def stop_listening(self) -> None:
        if self._audio_stream is not None:
            self._audio_stream.stop()
            self._audio_stream = None
        if self._aggregator is not None:
            self._aggregator.stop()
            self._aggregator = None

    def active_calibration_profile(self) -> Optional[CalibrationProfile]:
        record = self.calibration_repo.get_active_profile()
        return CalibrationProfile.from_record(record) if record is not None else None

    # --- Songs -------------------------------------------------------------------
    def import_song(self, path: str | Path) -> ImportedSong:
        return import_midi_file(path, self.songs_repo)

    def load_song(self, song_id: int) -> ImportedSong:
        return load_song_timeline(song_id, self.songs_repo)

    # --- Practice ------------------------------------------------------------------
    def start_practice_session(
        self, song: ImportedSong, section: Section, mode: PracticeMode
    ) -> PracticeEngine:
        if not self.is_listening:
            self.start_listening()

        if self._practice_engine is not None:
            self.stop_practice_session()

        self._practice_engine = PracticeEngine(
            expected_notes=song.expected_notes,
            section_start_ms=section.start_ms,
            section_end_ms=section.end_ms,
            config=self.config,
            mode=mode,
            event_bus=self.event_bus,
            clock=self.clock,
        )

        record = PracticeSessionRecord(id=None, song_id=song.song_id, mode=mode.value)
        self._practice_session_id = self.sessions_repo.start_session(record)
        self._last_pass_result = None
        self._session_finalized = False

        self._practice_engine.start_session()
        return self._practice_engine

    def stop_practice_session(self) -> None:
        if self._practice_engine is not None:
            self._practice_engine.stop_session()
            self._practice_engine = None
        if (
            self._practice_session_id is not None
            and self._last_pass_result is not None
            and not self._session_finalized
        ):
            # A manual stop before mastery was reached still finalizes the
            # session row with whatever the last completed pass scored.
            self._finalize_session_record(self._last_pass_result, mastered_override=False)
        self._practice_session_id = None
        self._last_pass_result = None
        self._session_finalized = False

    @property
    def practice_engine(self) -> Optional[PracticeEngine]:
        return self._practice_engine

    def _wire_session_persistence(self) -> None:
        self.event_bus.subscribe(Topic.PRACTICE_FEEDBACK, self._on_feedback_for_persistence)
        self.event_bus.subscribe(Topic.PRACTICE_EXCERPT_LOOPED, self._on_excerpt_looped_for_persistence)
        self.event_bus.subscribe(Topic.PRACTICE_MASTERY_ACHIEVED, self._on_mastery_achieved_for_persistence)

    def _on_feedback_for_persistence(self, feedback) -> None:
        if self._practice_session_id is None:
            return
        self.sessions_repo.add_event(
            SessionEventRecord(
                id=None,
                session_id=self._practice_session_id,
                t_ms=self.clock.now_ms(),
                event_type=feedback.type.value,
                related_pitches=list(feedback.related_pitches),
                score_delta=feedback.score_delta,
                message=feedback.message,
            )
        )

    def _on_excerpt_looped_for_persistence(self, result) -> None:
        self._last_pass_result = result
        if self._practice_session_id is None:
            return
        self.sessions_repo.update_progress(self._practice_session_id, self._result_to_record(result))

    def _on_mastery_achieved_for_persistence(self, result) -> None:
        self._last_pass_result = result
        if self._practice_session_id is None:
            return
        self._finalize_session_record(result, mastered_override=None)
        self._session_finalized = True

    def _finalize_session_record(self, result, mastered_override: Optional[bool]) -> None:
        record = self._result_to_record(result)
        if mastered_override is not None:
            record.mastered = mastered_override
        self.sessions_repo.end_session(self._practice_session_id, record)

    @staticmethod
    def _result_to_record(result) -> PracticeSessionRecord:
        return PracticeSessionRecord(
            id=None,
            song_id=0,  # unused by update_progress/end_session (keyed on session_id)
            mode="",
            total_score=result.total_score,
            note_accuracy_score=result.score.note_accuracy,
            chord_completeness_score=result.score.chord_completeness,
            timing_score=result.score.timing,
            consistency_score=result.score.consistency,
            loop_count=result.loop_count,
            mastered=result.mastery.mastered,
        )

    # --- Calibration -----------------------------------------------------------------
    def start_calibration(self, device_index: Optional[int] = None) -> CalibrationWorkflow:
        self.start_listening(device_index)
        device_name = self._device_name_for_index(
            self._audio_stream.device_index if self._audio_stream else -1
        )

        self._calibration_collector = CalibrationCollector(self.event_bus)
        self._calibration_workflow = CalibrationWorkflow(
            collector=self._calibration_collector,
            event_bus=self.event_bus,
            clock=self.clock,
            calibration_repo=self.calibration_repo,
            device_name=device_name,
        )
        self._calibration_workflow.start()
        return self._calibration_workflow

    def stop_calibration(self) -> None:
        if self._calibration_collector is not None:
            self._calibration_collector.close()
            self._calibration_collector = None
        self._calibration_workflow = None

    @property
    def calibration_workflow(self) -> Optional[CalibrationWorkflow]:
        return self._calibration_workflow

    def _device_name_for_index(self, index: int) -> str:
        for device in self.device_manager.list_input_devices():
            if device.index == index:
                return device.name
        return f"Device {index}"

    # --- Lifecycle ---------------------------------------------------------------------
    def shutdown(self) -> None:
        self.stop_practice_session()
        self.stop_calibration()
        self.stop_listening()
        self.db.close()
        logger.info("Application shut down cleanly")
