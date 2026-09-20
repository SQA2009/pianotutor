"""Splits a song into practice excerpts ("sections") for excerpt looping.

v1 approach: derive measure boundaries from the time-signature map (assuming,
as is near-universal in practical MIDI exports, that time-signature changes
land on measure boundaries), then group consecutive measures into
fixed-size chunks. A "Full Song" section spanning the whole piece is always
included first so a learner can practice the whole thing before drilling
into excerpts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from pianotutor.midi.parser import ParsedSong
from pianotutor.midi.timeline import TickTimeConverter

DEFAULT_MEASURES_PER_SECTION = 4


@dataclass(frozen=True)
class Section:
    section_index: int
    label: str
    start_ms: float
    end_ms: float


def _measure_boundary_ticks(parsed: ParsedSong) -> List[int]:
    """Return ascending tick positions of every measure's downbeat, plus the final tick."""
    signatures = sorted(parsed.time_signatures, key=lambda e: e.tick)
    boundaries: List[int] = [0]

    for i, sig in enumerate(signatures):
        segment_start = max(sig.tick, boundaries[-1])
        segment_end = (
            signatures[i + 1].tick if i + 1 < len(signatures) else parsed.total_ticks
        )
        ticks_per_measure = max(
            1, round(parsed.ppq * sig.numerator * (4.0 / sig.denominator))
        )
        tick = segment_start
        while tick < segment_end:
            if tick != boundaries[-1]:
                boundaries.append(tick)
            tick += ticks_per_measure

    if boundaries[-1] < parsed.total_ticks:
        boundaries.append(parsed.total_ticks)

    return boundaries


def build_sections(
    parsed: ParsedSong, measures_per_section: int = DEFAULT_MEASURES_PER_SECTION
) -> List[Section]:
    """Build the "Full Song" section plus fixed-size measure-chunk excerpts."""
    if measures_per_section < 1:
        raise ValueError("measures_per_section must be >= 1")

    converter = TickTimeConverter(parsed.ppq, parsed.tempo_map)
    boundary_ticks = _measure_boundary_ticks(parsed)
    duration_ms = converter.tick_to_ms(parsed.total_ticks)

    sections: List[Section] = [
        Section(section_index=0, label="Full Song", start_ms=0.0, end_ms=duration_ms)
    ]

    # boundary_ticks has one entry per measure downbeat plus the final tick,
    # so there are len(boundary_ticks) - 1 measures.
    num_measures = max(0, len(boundary_ticks) - 1)
    section_index = 1
    measure = 0
    while measure < num_measures:
        chunk_end_measure = min(measure + measures_per_section, num_measures)
        start_tick = boundary_ticks[measure]
        end_tick = boundary_ticks[chunk_end_measure]
        label = (
            f"Measures {measure + 1}-{chunk_end_measure}"
            if chunk_end_measure - measure > 1
            else f"Measure {measure + 1}"
        )
        sections.append(
            Section(
                section_index=section_index,
                label=label,
                start_ms=converter.tick_to_ms(start_tick),
                end_ms=converter.tick_to_ms(end_tick),
            )
        )
        section_index += 1
        measure = chunk_end_measure

    return sections
