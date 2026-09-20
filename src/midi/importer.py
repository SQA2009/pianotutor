"""Orchestrates MIDI import: parse -> timeline -> sections -> persistence.

This is the module the UI's "Import Song" action calls. It returns a
:class:`ImportedSong` bundling everything the practice engine and UI need,
so callers don't have to immediately re-query the database after import.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

from pianotutor.midi.parser import MidiParseError, ParsedSong, parse_midi_file
from pianotutor.midi.sections import Section, build_sections
from pianotutor.midi.timeline import ExpectedNote, build_expected_notes, song_duration_ms
from pianotutor.persistence.models import SongNoteRecord, SongRecord, SongSectionRecord
from pianotutor.persistence.repositories.songs_repo import SongsRepository

logger = logging.getLogger(__name__)


@dataclass
class ImportedSong:
    song_id: int
    title: str
    duration_ms: float
    expected_notes: List[ExpectedNote]
    sections: List[Section]


def import_midi_file(
    path: str | Path,
    songs_repo: SongsRepository,
    measures_per_section: int = 4,
) -> ImportedSong:
    """Parse ``path``, build its timeline/sections, and persist it.

    Raises :class:`pianotutor.midi.parser.MidiParseError` on malformed or
    unsupported MIDI files; callers (typically the home view) should catch
    this and surface a friendly message rather than crashing the import flow.
    """
    parsed: ParsedSong = parse_midi_file(path)
    expected_notes = build_expected_notes(parsed)
    sections = build_sections(parsed, measures_per_section=measures_per_section)
    duration_ms = song_duration_ms(parsed)

    song_record = SongRecord(
        id=None,
        title=parsed.title,
        source_path=str(Path(path).resolve()),
        ppq=parsed.ppq,
        duration_ms=duration_ms,
        tempo_map_json=json.dumps(
            [{"tick": t.tick, "us_per_beat": t.microseconds_per_beat} for t in parsed.tempo_map]
        ),
        time_signature_json=json.dumps(
            [
                {"tick": s.tick, "numerator": s.numerator, "denominator": s.denominator}
                for s in parsed.time_signatures
            ]
        ),
    )
    song_id = songs_repo.insert_song(song_record)

    note_records = [
        SongNoteRecord(
            id=None,
            song_id=song_id,
            note_index=n.note_id,
            pitch_midi=n.pitch_midi,
            start_ms=n.start_ms,
            end_ms=n.end_ms,
            hand=n.hand,
            track_id=n.track_id,
            velocity=64,
        )
        for n in expected_notes
    ]
    songs_repo.insert_notes(song_id, note_records)

    section_records = [
        SongSectionRecord(
            id=None,
            song_id=song_id,
            section_index=s.section_index,
            label=s.label,
            start_ms=s.start_ms,
            end_ms=s.end_ms,
        )
        for s in sections
    ]
    songs_repo.insert_sections(song_id, section_records)

    logger.info(
        "Imported song %r (id=%d): %d notes, %d sections, %.0fms duration",
        parsed.title, song_id, len(expected_notes), len(sections), duration_ms,
    )

    return ImportedSong(
        song_id=song_id,
        title=parsed.title,
        duration_ms=duration_ms,
        expected_notes=expected_notes,
        sections=sections,
    )


def load_song_timeline(song_id: int, songs_repo: SongsRepository) -> ImportedSong:
    """Reconstruct an :class:`ImportedSong` from persisted data (no re-parse)."""
    song = songs_repo.get_song(song_id)
    if song is None:
        raise MidiParseError(f"No song with id {song_id} found in the library.")

    notes = songs_repo.get_notes(song_id)
    expected_notes = [
        ExpectedNote(
            note_id=n.note_index,
            pitch_midi=n.pitch_midi,
            start_ms=n.start_ms,
            end_ms=n.end_ms,
            hand=n.hand,  # type: ignore[arg-type]
            track_id=n.track_id,
        )
        for n in notes
    ]

    section_rows = songs_repo.get_sections(song_id)
    sections = [
        Section(
            section_index=s.section_index,
            label=s.label,
            start_ms=s.start_ms,
            end_ms=s.end_ms,
        )
        for s in section_rows
    ]

    return ImportedSong(
        song_id=song_id,
        title=song.title,
        duration_ms=song.duration_ms,
        expected_notes=expected_notes,
        sections=sections,
    )
