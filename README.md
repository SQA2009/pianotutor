# PianoTutor (Windows) — v1

A desktop piano-learning app for Windows. It imports MIDI songs, renders a falling-notes
practice view with a live piano keyboard, listens to the player through an audio input
device (mic or audio interface), recognizes what notes/chords were actually played in
real time, matches them against the expected notes from the song timeline, and scores
the performance. Progress is stored locally in SQLite.

This repository implements the **v1 scope** described in
[`docs/windows-development-plan.md`](docs/windows-development-plan.md):

- MIDI import + internal timeline
- Falling-note + piano keyboard visualization
- Audio input selection + diagnostics
- Latency calibration + timing compensation
- Single-note recognition (reliable baseline)
- Basic chord recognition (2–4 notes, confidence-aware)
- Guided/wait mode + excerpt looping
- Scoring (accuracy, timing, chord completeness)
- Local progress persistence (SQLite)

Advanced adaptive pedagogy, richer ML-based recognition models, and cloud sync are
explicitly **out of scope** for v1 (see the plan doc).

## Architecture

```
Audio subsystem → Recognition subsystem → Practice engine → UI
```

- **Audio subsystem** (`pianotutor.audio`): device enumeration/selection, low-latency
  capture on a dedicated callback thread, a lock-free-ish ring buffer, signal
  monitoring (level/clipping/noise floor), latency estimation.
- **DSP** (`pianotutor.dsp`): filtering, onset detection, spectral analysis, denoise,
  and feature extraction shared by the recognition layer.
- **Recognition subsystem** (`pianotutor.recognition`): turns raw audio frames into
  `DetectedNoteEvent` / `DetectedChordEvent` objects with confidence scores. Runs on
  worker thread(s), never on the audio callback thread.
- **MIDI / timeline** (`pianotutor.midi`): parses imported MIDI into an internal song
  representation and produces `ExpectedNote` windows plus practice-excerpt sections.
- **Practice engine** (`pianotutor.practice`): matches detected events against expected
  notes using tolerance windows, computes the weighted score, tracks mastery/looping,
  and emits `PracticeFeedbackEvent`s.
- **Calibration** (`pianotutor.calibration`): guided single-note capture session used to
  estimate round-trip latency and per-user recognition thresholds.
- **Persistence** (`pianotutor.persistence`): SQLite storage for songs, sessions,
  calibration profiles, and settings, behind small repository classes.
- **Services** (`pianotutor.services`): cross-cutting infrastructure — the in-process
  event bus, a monotonic clock abstraction, logging setup, and app configuration.
- **UI** (`pianotutor.ui`): PySide6 desktop UI — home/library, practice (falling notes +
  keyboard), calibration, progress, and diagnostics views, plus thin view-models that
  translate engine events into Qt signals/state snapshots.

See [`docs/project-structure.md`](docs/project-structure.md) for the full file layout
and a short description of every module.

## Threading model

- The audio callback thread **never blocks**: it only writes raw frames into a ring
  buffer and posts lightweight `AudioFrameReady` notifications.
- Recognition runs on worker thread(s) that consume buffered frames and emit compact
  `DetectedNoteEvent` / `DetectedChordEvent` objects onto the event bus.
- The practice engine consumes those compact events — never raw audio.
- The UI only ever receives immutable state snapshots/events over Qt signals (marshalled
  onto the Qt main thread by the event bus's Qt bridge).

## Getting started (development)

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -e ".[dev]"
pianotutor                        # launch the app
pytest                            # run the test suite
```

> On Windows, `python-rtmidi` and `sounddevice` will pull in prebuilt wheels for
> MIDI I/O and PortAudio; no separate driver install is normally required for class-
> compliant USB MIDI keyboards and audio interfaces / built-in microphones.

## Project status

This is the v1 scaffold: every module in the architecture above has a working, tested
implementation of its core responsibility (see `tests/unit`), wired end-to-end in
`pianotutor.app.Application`. Milestones A–F from the development plan map directly onto
the subsystems above; see `docs/windows-development-plan.md` for acceptance criteria.
