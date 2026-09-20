"""Windowed FFT helpers and frequency <-> MIDI pitch conversion."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

A4_MIDI = 69
A4_FREQ_HZ = 440.0


def midi_to_freq(midi_pitch: float) -> float:
    return A4_FREQ_HZ * (2.0 ** ((midi_pitch - A4_MIDI) / 12.0))


def freq_to_midi(freq_hz: float) -> float:
    if freq_hz <= 0:
        return float("nan")
    return A4_MIDI + 12.0 * np.log2(freq_hz / A4_FREQ_HZ)


def nearest_midi_pitch(freq_hz: float) -> int:
    return int(round(freq_to_midi(freq_hz)))


def cents_offset(freq_hz: float, midi_pitch: int) -> float:
    """How far ``freq_hz`` is from ``midi_pitch``'s exact frequency, in cents."""
    if freq_hz <= 0:
        return 0.0
    return 1200.0 * float(np.log2(freq_hz / midi_to_freq(midi_pitch)))


@dataclass(frozen=True)
class MagnitudeSpectrum:
    freqs_hz: np.ndarray
    magnitudes: np.ndarray
    sample_rate: int
    fft_size: int


def compute_magnitude_spectrum(
    samples: np.ndarray, sample_rate: int, fft_size: int | None = None
) -> MagnitudeSpectrum:
    """Compute a Hann-windowed magnitude spectrum, zero-padded to ``fft_size``.

    Zero-padding (rather than requiring the caller to supply exactly
    ``fft_size`` samples) increases frequency-bin resolution/interpolation
    smoothness without requiring more actual audio, which matters for
    resolving closely-spaced low piano notes from short analysis blocks.
    """
    n = samples.shape[0]
    if n == 0:
        return MagnitudeSpectrum(np.zeros(0), np.zeros(0), sample_rate, fft_size or 0)

    if fft_size is None:
        fft_size = 1
        while fft_size < n:
            fft_size *= 2
    fft_size = max(fft_size, n)

    window = np.hanning(n).astype(np.float64)
    windowed = samples.astype(np.float64) * window

    spectrum = np.fft.rfft(windowed, n=fft_size)
    magnitudes = np.abs(spectrum)
    freqs = np.fft.rfftfreq(fft_size, d=1.0 / sample_rate)

    return MagnitudeSpectrum(freqs, magnitudes, sample_rate, fft_size)


def parabolic_interpolate_peak(magnitudes: np.ndarray, bin_index: int) -> float:
    """Sub-bin peak location via parabolic interpolation around ``bin_index``.

    Returns a fractional bin offset in [-0.5, 0.5] to add to ``bin_index``
    for a more accurate frequency estimate than the raw FFT bin resolution.
    """
    if bin_index <= 0 or bin_index >= len(magnitudes) - 1:
        return 0.0
    left = magnitudes[bin_index - 1]
    center = magnitudes[bin_index]
    right = magnitudes[bin_index + 1]
    denom = left - 2 * center + right
    if denom == 0:
        return 0.0
    return 0.5 * (left - right) / denom
