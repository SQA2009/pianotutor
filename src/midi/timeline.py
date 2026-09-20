"""Builds the millisecond-based practice timeline from a :class:`ParsedSong`.

This is where MIDI ticks (tempo-map dependent) become the absolute
millisecond timestamps that the audio-facing side of the app (recognition,
matching, falling-notes rendering) works in exclusively. Converting once,
here, means every other subsystem can treat time as a plain float in
milliseconds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal

from pianotutor.midi.parser import ParsedNote, ParsedSong, TempoEvent

Hand = Literal["left", "right", "unknown"]


@dataclass(frozen=True)
class ExpectedNote:
    """The ``ExpectedNote`` contract from MIDI/Timeline -> Practice."""

    note_id: int
    pitch_midi: int
    start_ms: float
    end_ms: float
    hand: Hand
    track_id: int


class TickTimeConverter:
    """Converts absolute MIDI ticks to absolute milliseconds using a tempo map.

    Precomputes the millisecond offset of every tempo-change tick once so
    that individual conversions are O(log n) via binary search rather than
    re-walking the whole tempo map per note.
    """

    def __init__(self, ppq: int, tempo_map: List[TempoEvent]):
        if ppq <= 0:
            raise ValueError("ppq must be positive")
        if not tempo_map:
            raise ValueError("tempo_map must contain at least one entry")

        ordered = sorted(tempo_map, key=lambda e: e.tick)
        self._ppq = ppq
        self._tick_breakpoints: List[int] = []
        self._ms_breakpoints: List[float] = []
        self._us_per_beat: List[int] = []

        ms_accum = 0.0
        prev_tick = ordered[0].tick
        prev_us = ordered[0].microseconds_per_beat
        self._tick_breakpoints.append(prev_tick)
        self._ms_breakpoints.append(ms_accum)
        self._us_per_beat.append(prev_us)

        for event in ordered[1:]:
            delta_ticks = event.tick - prev_tick
            if delta_ticks > 0:
                ms_accum += self._ticks_to_ms(delta_ticks, prev_us, ppq)
            self._tick_breakpoints.append(event.tick)
            self._ms_breakpoints.append(ms_accum)
            self._us_per_beat.append(event.microseconds_per_beat)
            prev_tick = event.tick
            prev_us = event.microseconds_per_beat

    @staticmethod
    def _ticks_to_ms(delta_ticks: int, microseconds_per_beat: int, ppq: int) -> float:
        return (delta_ticks / ppq) * (microseconds_per_beat / 1000.0)

    def tick_to_ms(self, tick: int) -> float:
        # Binary search for the last breakpoint at or before `tick`.
        lo, hi = 0, len(self._tick_breakpoints) - 1
        idx = 0
        while lo <= hi:
            mid = (lo + hi) // 2
            if self._tick_breakpoints[mid] <= tick:
                idx = mid
                lo = mid + 1
            else:
                hi = mid - 1

        delta_ticks = tick - self._tick_breakpoints[idx]
        ms = self._ms_breakpoints[idx]
        if delta_ticks > 0:
            ms += self._ticks_to_ms(delta_ticks, self._us_per_beat[idx], self._ppq)
        return ms


def infer_hand(note: ParsedNote, track_pitch_means: dict[int, float]) -> Hand:
    """Heuristic hand assignment for v1.

    Multi-track piano MIDI (the common export shape from notation software)
    typically separates right hand / left hand onto distinct tracks. When
    there are at least two tracks containing notes, the track with the
    lower average pitch is treated as "left" and the higher as "right".
    Single-track files fall back to a per-note middle-C split, which is a
    weaker but still useful signal. This is a v1 heuristic, not authoritative
    fingering data — it is used for optional visual hand-coloring only and
    never affects matching/scoring.
    """
    if len(track_pitch_means) >= 2:
        sorted_tracks = sorted(track_pitch_means.items(), key=lambda kv: kv[1])
        lowest_track_id = sorted_tracks[0][0]
        highest_track_id = sorted_tracks[-1][0]
        if note.track_id == lowest_track_id and note.track_id != highest_track_id:
            return "left"
        if note.track_id == highest_track_id and note.track_id != lowest_track_id:
            return "right"
        return "unknown"

    return "left" if note.pitch_midi < 60 else "right"


def build_expected_notes(parsed: ParsedSong) -> List[ExpectedNote]:
    """Convert a :class:`ParsedSong` into the millisecond-based practice timeline."""
    converter = TickTimeConverter(parsed.ppq, parsed.tempo_map)

    track_pitch_sums: dict[int, float] = {}
    track_pitch_counts: dict[int, int] = {}
    for note in parsed.notes:
        track_pitch_sums[note.track_id] = track_pitch_sums.get(note.track_id, 0.0) + note.pitch_midi
        track_pitch_counts[note.track_id] = track_pitch_counts.get(note.track_id, 0) + 1
    track_pitch_means = {
        track_id: track_pitch_sums[track_id] / track_pitch_counts[track_id]
        for track_id in track_pitch_sums
    }

    expected: List[ExpectedNote] = []
    for note in parsed.notes:
        expected.append(
            ExpectedNote(
                note_id=note.note_index,
                pitch_midi=note.pitch_midi,
                start_ms=converter.tick_to_ms(note.start_tick),
                end_ms=converter.tick_to_ms(note.end_tick),
                hand=infer_hand(note, track_pitch_means),
                track_id=note.track_id,
            )
        )
    expected.sort(key=lambda n: (n.start_ms, n.pitch_midi))
    return expected


def song_duration_ms(parsed: ParsedSong) -> float:
    converter = TickTimeConverter(parsed.ppq, parsed.tempo_map)
    return converter.tick_to_ms(parsed.total_ticks)
