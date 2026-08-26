# Proposed Project Structure

```text
pianotutor/
  pyproject.toml
  README.md
  docs/
    windows-development-plan.md
    project-structure.md

  src/
    pianotutor/
      __init__.py
      main.py
      app.py

      ui/
        __init__.py
        main_window.py
        views/
          __init__.py
          home_view.py
          practice_view.py
          calibration_view.py
          progress_view.py
        widgets/
          __init__.py
          piano_widget.py
          piano_roll_widget.py
          input_meter_widget.py
        viewmodels/
          __init__.py
          practice_vm.py
          calibration_vm.py

      audio/
        __init__.py
        devices.py
        stream.py
        ring_buffer.py
        monitor.py
        latency.py

      dsp/
        __init__.py
        filters.py
        onset.py
        spectrum.py
        denoise.py
        features.py

      recognition/
        __init__.py
        note_events.py
        pitch_tracker.py
        polyphony.py
        confidence.py
        aggregator.py

      midi/
        __init__.py
        importer.py
        parser.py
        timeline.py
        sections.py

      practice/
        __init__.py
        engine.py
        matcher.py
        tolerance.py
        scoring.py
        mastery.py
        feedback.py
        modes.py

      calibration/
        __init__.py
        profiles.py
        collector.py
        analyzer.py
        workflow.py

      persistence/
        __init__.py
        db.py
        models.py
        repositories/
          __init__.py
          songs_repo.py
          sessions_repo.py
          calibration_repo.py
          settings_repo.py
        migrations/
          001_init.sql

      services/
        __init__.py
        event_bus.py
        event_types.py
        clock.py
        logger.py
        config.py

  tests/
    unit/
    integration/
    fixtures/
      audio/
      midi/
