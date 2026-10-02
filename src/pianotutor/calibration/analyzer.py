"""Derives a stable calibration profile from collected samples."""

from __future__ import annotations

from pianotutor.audio.latency import estimate_latency
from pianotutor.calibration.profiles import CalibrationProfile


def analyze_calibration(
    *,
    profile_name: str,
    device_name: str,
    samples,
    noise_floor_rms: float,
) -> CalibrationProfile:
    latency = estimate_latency(list(samples))
    onset_threshold = max(noise_floor_rms * 3.0, 0.02)

    return CalibrationProfile(
        name=profile_name,
        device_name=device_name,
        latency_ms=latency.mean_ms,
        latency_stddev_ms=latency.stddev_ms,
        noise_floor_rms=noise_floor_rms,
        recommended_onset_threshold=onset_threshold,
        sample_count=latency.sample_count,
    )
