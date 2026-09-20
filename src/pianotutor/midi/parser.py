"""Parses a raw MIDI file into an intermediate, tick-based song structure.

This module only understands MIDI ticks — converting to milliseconds (which
requires walking the tempo map) is ``midi.timeline``'s job. Keeping the two
separate makes both independently testable: this module can be tested with
plain tick arithmetic, and ``timeline`` can be tested against a synthetic
``ParsedSong`` without needing a real ``.mid`` file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import mido


class MidiParseError(Exception):
    """Raised when a MIDI file cannot be parsed into a usable song."""


@dataclass
class TempoEvent:
    tick: int
    microseconds_per_beat: int


@dataclass
class TimeSignatureEvent:
    tick: int
    numerator: int
    denominator: int


@dataclass
class ParsedNote:
    note_index: int
    pitch_midi: int
    start_tick: int
    end_tick: int
    velocity: int
    track_id: int
    channel: int


@dataclass
class ParsedSong:
    title: str
    ppq: int
    total_ticks: int
    tracks_count: int
    notes: List[ParsedNote] = field(default_factory=list)
    tempo_map: List[TempoEvent] = field(default_factory=list)
    time_signatures: List[TimeSignatureEvent] = field(default_factory=list)


DEFAULT_TEMPO_MICROSECONDS_PER_BEAT = 500_000  # 120 BPM
DEFAULT_TIME_SIGNATURE = (4, 4)


def parse_midi_file(path: str | Path) -> ParsedSong:
    """Parse a Standard MIDI File (.mid) into a :class:`ParsedSong`.

    Handles both format-0 (single track) and format-1 (multiple synchronous
    tracks) files. Note-on events with velocity 0 are treated as note-off,
    per the MIDI spec. Any note left "on" at end-of-file is closed at the
    file's final tick so a malformed file never produces a dangling note.
    """
    path = Path(path)
    if not path.exists():
        raise MidiParseError(f"MIDI file not found: {path}")

    try:
        midi_file = mido.MidiFile(str(path))
    except (OSError, EOFError, ValueError) as exc:
        raise MidiParseError(f"Could not parse MIDI file {path.name}: {exc}") from exc

    if midi_file.type == 2:
        raise MidiParseError(
            "Type-2 (asynchronous multi-track) MIDI files are not supported in v1."
        )

    ppq = midi_file.ticks_per_beat
    if not ppq or ppq <= 0:
        raise MidiParseError("MIDI file has an invalid ticks-per-beat (PPQ) value.")

    notes: List[ParsedNote] = []
    tempo_map: List[TempoEvent] = [TempoEvent(0, DEFAULT_TEMPO_MICROSECONDS_PER_BEAT)]
    time_signatures: List[TimeSignatureEvent] = [
        TimeSignatureEvent(0, *DEFAULT_TIME_SIGNATURE)
    ]
    title = path.stem
    max_tick = 0
    note_index = 0

    for track_id, track in enumerate(midi_file.tracks):
        abs_tick = 0
        # pitch -> list of (start_tick, velocity, channel) still sounding,
        # supporting the same pitch overlapping itself (rare but legal).
        open_notes: dict[tuple[int, int], List[tuple[int, int]]] = {}

        for msg in track:
            abs_tick += msg.time

            if msg.is_meta:
                if msg.type == "track_name" and track_id == 0 and msg.name.strip():
                    title = msg.name.strip()
                elif msg.type == "set_tempo":
                    tempo_map.append(TempoEvent(abs_tick, msg.tempo))
                elif msg.type == "time_signature":
                    time_signatures.append(
                        TimeSignatureEvent(abs_tick, msg.numerator, msg.denominator)
                    )
                continue

            if msg.type == "note_on" and msg.velocity > 0:
                key = (msg.channel, msg.note)
                open_notes.setdefault(key, []).append((abs_tick, msg.velocity))
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                key = (msg.channel, msg.note)
                pending = open_notes.get(key)
                if pending:
                    start_tick, velocity = pending.pop(0)
                    end_tick = max(abs_tick, start_tick + 1)
                    notes.append(
                        ParsedNote(
                            note_index=note_index,
                            pitch_midi=msg.note,
                            start_tick=start_tick,
                            end_tick=end_tick,
                            velocity=velocity,
                            track_id=track_id,
                            channel=msg.channel,
                        )
                    )
                    note_index += 1

        # Close out any notes still open at end-of-track so we never lose data.
        for (channel, pitch), pending in open_notes.items():
            for start_tick, velocity in pending:
                notes.append(
                    ParsedNote(
                        note_index=note_index,
                        pitch_midi=pitch,
                        start_tick=start_tick,
                        end_tick=max(abs_tick, start_tick + 1),
                        velocity=velocity,
                        track_id=track_id,
                        channel=channel,
                    )
                )
                note_index += 1

        max_tick = max(max_tick, abs_tick)

    if not notes:
        raise MidiParseError("MIDI file contains no playable notes.")

    tempo_map.sort(key=lambda e: e.tick)
    time_signatures.sort(key=lambda e: e.tick)
    notes.sort(key=lambda n: (n.start_tick, n.pitch_midi))
    # Re-number note_index in final chronological order for stable downstream IDs.
    for i, n in enumerate(notes):
        n.note_index = i

    return ParsedSong(
        title=title,
        ppq=ppq,
        total_ticks=max_tick,
        tracks_count=len(midi_file.tracks),
        notes=notes,
        tempo_map=tempo_map,
        time_signatures=time_signatures,
    )
