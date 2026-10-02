"""Shared piano-key geometry helpers for keyboard and roll widgets."""

from __future__ import annotations

_WHITE_CLASSES = {0, 2, 4, 5, 7, 9, 11}
_BLACK_OFFSETS = {1: 0.65, 3: 1.55, 6: 3.45, 8: 4.35, 10: 5.25}


def _is_white(pitch_midi: int) -> bool:
    return pitch_midi % 12 in _WHITE_CLASSES


def _white_index_from_min(pitch_midi: int, min_midi: int) -> int:
    idx = 0
    for p in range(min_midi, pitch_midi):
        if _is_white(p):
            idx += 1
    return idx


def _white_key_count(min_midi: int, max_midi: int) -> int:
    return sum(1 for p in range(min_midi, max_midi + 1) if _is_white(p))


def key_width(pitch_midi: int, min_midi: int, max_midi: int, total_width: float) -> float:
    white_w = total_width / max(1, _white_key_count(min_midi, max_midi))
    return white_w if _is_white(pitch_midi) else white_w * 0.62


def key_center_x(pitch_midi: int, min_midi: int, max_midi: int, total_width: float) -> float:
    white_w = total_width / max(1, _white_key_count(min_midi, max_midi))
    octave = pitch_midi // 12
    pitch_class = pitch_midi % 12
    white_before = _white_index_from_min(pitch_midi, min_midi)

    if _is_white(pitch_midi):
        return (white_before + 0.5) * white_w

    octave_start = octave * 12
    white_before_octave_start = _white_index_from_min(octave_start, min_midi)
    offset = _BLACK_OFFSETS.get(pitch_class, 0.5)
    return (white_before_octave_start + offset) * white_w
