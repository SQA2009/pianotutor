"""State machine for guided calibration sessions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pianotutor.calibration.analyzer import analyze_calibration
from pianotutor.services.event_types import Topic


class CalibrationStep(str, Enum):
    MEASURE_NOISE_FLOOR = "measure_noise_floor"
    COLLECT_SAMPLES = "collect_samples"
    ANALYZING = "analyzing"
    DONE = "done"


@dataclass(frozen=True)
class CalibrationStepState:
    step: CalibrationStep
    message: str = ""
    trial_index: int = 0
    trials_required: int = 0
    cue_pitch_midi: int | None = None


class CalibrationWorkflow:
    def __init__(
        self,
        collector,
        event_bus,
        clock,
        calibration_repo,
        device_name: str,
        trials_required: int = 6,
        noise_floor_duration_ms: float = 1500.0,
        inter_trial_delay_ms: float = 1200.0,
    ):
        self._collector = collector
        self._event_bus = event_bus
        self._clock = clock
        self._calibration_repo = calibration_repo
        self._device_name = device_name
        self._trials_required = trials_required
        self._noise_floor_duration_ms = noise_floor_duration_ms
        self._inter_trial_delay_ms = inter_trial_delay_ms

        self._cue_cycle = [60, 64, 67, 72]
        self._step = CalibrationStep.MEASURE_NOISE_FLOOR
        self._elapsed_in_step_ms = 0.0
        self._next_cue_due_t_ms = 0.0
        self._completed_trials = 0
        self._active_cue_pitch: int | None = None
        self._last_seen_sample_count = 0

    def start(self) -> None:
        self._step = CalibrationStep.MEASURE_NOISE_FLOOR
        self._elapsed_in_step_ms = 0.0
        self._completed_trials = 0
        self._last_seen_sample_count = self._collector.sample_count
        self._publish_state("Measuring background noise...")

    def advance(self, elapsed_ms: float) -> None:
        self._elapsed_in_step_ms += max(0.0, elapsed_ms)

        if self._step == CalibrationStep.MEASURE_NOISE_FLOOR:
            if self._elapsed_in_step_ms >= self._noise_floor_duration_ms:
                self._step = CalibrationStep.COLLECT_SAMPLES
                self._elapsed_in_step_ms = 0.0
                self._next_cue_due_t_ms = self._clock.now_ms()
                self._publish_state("Get ready for note cues.")
            return

        if self._step == CalibrationStep.COLLECT_SAMPLES:
            self._advance_collect_samples()
            return

        if self._step == CalibrationStep.ANALYZING:
            self._finalize_profile()

    def _advance_collect_samples(self) -> None:
        if self._collector.sample_count > self._last_seen_sample_count:
            self._completed_trials += 1
            self._last_seen_sample_count = self._collector.sample_count
            self._active_cue_pitch = None
            self._next_cue_due_t_ms = self._clock.now_ms() + self._inter_trial_delay_ms

            if self._completed_trials >= self._trials_required:
                self._step = CalibrationStep.ANALYZING
                self._publish_state("Analyzing your samples...")
                return

        now = self._clock.now_ms()
        if self._active_cue_pitch is None and now >= self._next_cue_due_t_ms:
            self._active_cue_pitch = self._cue_cycle[self._completed_trials % len(self._cue_cycle)]
            cue_t_ms = self._clock.now_ms()
            self._collector.arm_for_cue(cue_t_ms=cue_t_ms, cue_pitch_midi=self._active_cue_pitch)
            self._publish_state("Play the cued note now.")

    def _finalize_profile(self) -> None:
        profile = analyze_calibration(
            profile_name=f"{self._device_name} profile",
            device_name=self._device_name,
            samples=self._collector.samples,
            noise_floor_rms=self._collector.noise_floor_rms,
        )
        self._calibration_repo.insert_profile(profile.to_record(is_active=True))

        self._step = CalibrationStep.DONE
        self._publish_state("Calibration complete.")
        self._event_bus.publish(Topic.CALIBRATION_COMPLETED, profile)

    def _publish_state(self, message: str) -> None:
        trial_index = self._completed_trials + (1 if self._active_cue_pitch is not None else 0)
        state = CalibrationStepState(
            step=self._step,
            message=message,
            trial_index=min(trial_index, self._trials_required),
            trials_required=self._trials_required,
            cue_pitch_midi=self._active_cue_pitch,
        )
        self._event_bus.publish(Topic.CALIBRATION_STEP_CHANGED, state)
