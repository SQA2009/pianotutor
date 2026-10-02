from pianotutor.audio.monitor import LevelSnapshot
from pianotutor.recognition.note_events import DetectedNoteEvent, NoteState
from pianotutor.services.event_bus import EventBus
from pianotutor.services.event_types import Topic
from pianotutor.calibration.collector import CalibrationCollector


def test_collector_tracks_noise_floor_and_matching_cue_samples():
    bus = EventBus()
    collector = CalibrationCollector(bus)

    bus.publish(
        Topic.AUDIO_LEVEL_UPDATED,
        LevelSnapshot(
            rms=0.02,
            peak=0.05,
            is_clipping=False,
            is_silence=False,
            noise_floor_rms=0.012,
        ),
    )
    assert collector.noise_floor_rms == 0.012

    collector.arm_for_cue(cue_t_ms=1000.0, cue_pitch_midi=60)
    bus.publish(
        Topic.NOTE_DETECTED,
        DetectedNoteEvent(
            pitch_midi=61,
            state=NoteState.STARTED,
            t_ms=1120.0,
            confidence=0.9,
        ),
    )
    assert collector.sample_count == 0

    bus.publish(
        Topic.NOTE_DETECTED,
        DetectedNoteEvent(
            pitch_midi=60,
            state=NoteState.STARTED,
            t_ms=1130.0,
            confidence=0.95,
        ),
    )
    assert collector.sample_count == 1
    assert collector.samples[0].delta_ms == 130.0

    collector.close()
