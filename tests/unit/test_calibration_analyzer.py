from pianotutor.audio.latency import LatencySample
from pianotutor.calibration.analyzer import analyze_calibration
from pianotutor.calibration.profiles import CalibrationProfile


def test_analyze_calibration_builds_profile():
    samples = [
        LatencySample(cue_t_ms=1000.0, detected_t_ms=1120.0),
        LatencySample(cue_t_ms=2000.0, detected_t_ms=2125.0),
        LatencySample(cue_t_ms=3000.0, detected_t_ms=3115.0),
    ]

    profile = analyze_calibration(
        profile_name="Test profile",
        device_name="Mic 1",
        samples=samples,
        noise_floor_rms=0.01,
    )

    assert isinstance(profile, CalibrationProfile)
    assert profile.name == "Test profile"
    assert profile.device_name == "Mic 1"
    assert 110.0 <= profile.latency_ms <= 130.0
    assert profile.sample_count == 3
    assert profile.recommended_onset_threshold >= 0.02


def test_calibration_profile_record_roundtrip():
    profile = CalibrationProfile(
        name="Roundtrip",
        device_name="Device A",
        latency_ms=88.0,
        latency_stddev_ms=9.0,
        noise_floor_rms=0.015,
        recommended_onset_threshold=0.05,
        sample_count=5,
    )

    record = profile.to_record(is_active=True)
    rebuilt = CalibrationProfile.from_record(record)

    assert rebuilt.name == profile.name
    assert rebuilt.device_name == profile.device_name
    assert rebuilt.latency_ms == profile.latency_ms
    assert rebuilt.sample_count == profile.sample_count
