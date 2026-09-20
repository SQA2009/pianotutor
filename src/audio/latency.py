"""Round-trip latency estimation statistics.

v1's calibration workflow (see ``pianotutor.calibration``) prompts the
learner to play a single cued note several times; each trial yields a
:class:`LatencySample` pairing the cue timestamp with the detected onset
timestamp. This module turns a batch of such samples into a robust latency
estimate (mean/stddev, with simple outlier rejection so one mis-timed or
missed trial doesn't skew the result), and applies that estimate to
subsequent detected-event timestamps during practice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np


@dataclass(frozen=True)
class LatencySample:
    cue_t_ms: float
    detected_t_ms: float

    @property
    def delta_ms(self) -> float:
        return self.detected_t_ms - self.cue_t_ms


@dataclass(frozen=True)
class LatencyEstimate:
    mean_ms: float
    stddev_ms: float
    sample_count: int
    rejected_count: int


def estimate_latency(
    samples: List[LatencySample], max_deviation_stddevs: float = 2.5
) -> LatencyEstimate:
    """Compute a robust mean/stddev latency estimate with outlier rejection.

    Two passes: an initial mean/stddev over all samples, then a second pass
    excluding anything more than ``max_deviation_stddevs`` away from that
    initial mean (guards against a rare double-hit or missed trial).
    Requires at least one sample; with fewer than 3 samples, no rejection is
    attempted (not enough data to distinguish an outlier from real spread).
    """
    if not samples:
        raise ValueError("At least one latency sample is required")

    deltas = np.array([s.delta_ms for s in samples], dtype=np.float64)

    if len(deltas) < 3:
        return LatencyEstimate(
            mean_ms=float(np.mean(deltas)),
            stddev_ms=float(np.std(deltas)),
            sample_count=len(deltas),
            rejected_count=0,
        )

    initial_mean = float(np.mean(deltas))
    initial_std = float(np.std(deltas)) or 1e-6

    keep_mask = np.abs(deltas - initial_mean) <= max_deviation_stddevs * initial_std
    kept = deltas[keep_mask]
    if kept.size == 0:
        kept = deltas  # degenerate case: rejection removed everything, keep all

    return LatencyEstimate(
        mean_ms=float(np.mean(kept)),
        stddev_ms=float(np.std(kept)),
        sample_count=int(kept.size),
        rejected_count=int(deltas.size - kept.size),
    )


def compensate_timestamp(detected_t_ms: float, latency_ms: float) -> float:
    """Shift a detected event's timestamp back by the estimated system latency.

    Recognition always reports an onset *after* the physical key press
    (capture buffering + DSP + detector lookahead). Subtracting the
    calibrated latency estimate aligns detected timestamps with the moment
    the key was actually pressed, which is what tolerance matching compares
    against the MIDI timeline.
    """
    return detected_t_ms - latency_ms
