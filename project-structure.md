# Project Structure

```
pianotutor/
  pyproject.toml
  README.md
  docs/
    windows-development-plan.md
    project-structure.md

  src/
    pianotutor/
      __init__.py
      main.py                     # process entry point
      app.py                      # Application: wires every subsystem together

      ui/
        main_window.py            # QMainWindow, navigation between views
        views/
          home_view.py            # song library, "open song" / "start practice"
          practice_view.py        # falling notes + keyboard + live feedback
          calibration_view.py     # guided latency/threshold calibration UI
          progress_view.py        # session history, mastery, score trends
        widgets/
          piano_widget.py         # interactive/illustrative piano keyboard
          piano_roll_widget.py    # falling-notes timeline + playhead
          input_meter_widget.py   # live level meter / clipping indicator
        viewmodels/
          practice_vm.py          # bridges practice engine <-> practice_view
          calibration_vm.py       # bridges calibration workflow <-> calibration_view

      audio/
        devices.py                # input device enumeration/selection
        stream.py                 # non-blocking capture callback -> ring buffer
        ring_buffer.py            # bounded, thread-safe float32 ring buffer
        monitor.py                # level/clipping/noise-floor monitoring
        latency.py                # round-trip latency estimation

      dsp/
        filters.py                # DC-block, band-pass, notch
        spectrum.py                # windowed FFT helpers, frequency <-> MIDI
        onset.py                  # spectral-flux onset detector
        denoise.py                # noise-floor gate / spectral subtraction
        features.py               # pitch-salience spectrum, harmonic features

      recognition/
        note_events.py            # DetectedNoteEvent / DetectedChordEvent dataclasses
        pitch_tracker.py          # monophonic f0 tracking (YIN-style autocorrelation)
        polyphony.py              # basic multi-pitch (2-4 note) grouping
        confidence.py             # confidence scoring shared by mono/poly paths
        aggregator.py             # worker-thread pipeline: frames -> events

      midi/
        parser.py                 # raw MIDI file -> intermediate song structure
        timeline.py                # intermediate structure -> ExpectedNote timeline
        sections.py                # split a song into practice excerpts/sections
        importer.py                # orchestrates parse+timeline+persistence

      practice/
        tolerance.py               # tolerance-window configuration (guided/continuous)
        matcher.py                  # expected vs detected matching logic
        scoring.py                  # weighted score model
        mastery.py                  # consecutive-pass mastery condition
        feedback.py                 # PracticeFeedbackEvent construction
        modes.py                    # guided (wait) vs continuous mode policies
        engine.py                   # orchestrates matcher+scoring+mastery+feedback

      calibration/
        profiles.py                 # CalibrationProfile dataclass + persistence glue
        collector.py                 # collects single-note capture samples
        analyzer.py                  # derives latency/thresholds from samples
        workflow.py                  # step-by-step guided calibration session

      persistence/
        db.py                        # SQLite connection/migration runner
        models.py                    # persistence-facing dataclasses
        migrations/
          001_init.sql                # schema for songs/sessions/calibration/settings
        repositories/
          songs_repo.py
          sessions_repo.py
          calibration_repo.py
          settings_repo.py

      services/
        event_bus.py                 # in-process pub/sub event bus (thread-safe)
        event_types.py               # shared event/topic name constants
        clock.py                     # monotonic clock abstraction (testable)
        logger.py                    # logging setup
        config.py                    # AppConfig (tolerances, audio defaults, paths)

  tests/
    unit/                            # fast, hardware-free tests for pure logic
    integration/                     # multi-module tests (MIDI -> timeline -> matcher)
    fixtures/
      audio/
      midi/
```

## Data flow at runtime

1. `midi.importer` parses a `.mid` file into `midi.parser` intermediate structures,
   builds an `ExpectedNote` timeline (`midi.timeline`) and excerpt sections
   (`midi.sections`), and persists the song via `persistence.repositories.songs_repo`.
2. `audio.stream` opens the selected input device and, on its callback thread, pushes
   raw samples into `audio.ring_buffer` and posts `AudioFrameReady` notifications
   through `services.event_bus` — it never runs DSP or blocks.
3. `recognition.aggregator` runs on a worker thread, pulls frames from the ring buffer,
   applies `dsp.filters` / `dsp.denoise` / `dsp.onset` / `dsp.features`, runs
   `recognition.pitch_tracker` and `recognition.polyphony`, scores confidence via
   `recognition.confidence`, and emits `DetectedNoteEvent` / `DetectedChordEvent`
   objects onto the event bus.
4. `practice.engine` consumes those detection events plus the `ExpectedNote` timeline,
   uses `practice.tolerance` + `practice.matcher` to classify each event, updates the
   score via `practice.scoring`, checks `practice.mastery`, and emits
   `PracticeFeedbackEvent`s.
5. `ui.viewmodels.practice_vm` subscribes to those feedback events and updates
   `ui.views.practice_view`, `ui.widgets.piano_widget`, and
   `ui.widgets.piano_roll_widget` on the Qt main thread.
6. Session results are persisted via `persistence.repositories.sessions_repo` and shown
   in `ui.views.progress_view`.
