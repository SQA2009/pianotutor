# pianotutor

Piano keyboard helper.

## Architecture & Roadmap

This repository now includes planning/scaffold groundwork for a Python-based Windows desktop piano tutor focused on audio-input keyboards (no MIDI output required).

See:

- [`docs/windows-development-plan.md`](docs/windows-development-plan.md)
- [`docs/project-structure.md`](docs/project-structure.md)
- [`src/pianotutor/persistence/migrations/001_init.sql`](src/pianotutor/persistence/migrations/001_init.sql)
- [`src/pianotutor/services/event_types.py`](src/pianotutor/services/event_types.py)

These artifacts define:
- v1 scope and milestones
- subsystem boundaries and contracts
- runtime event models
- initial SQLite schema

Implementation of DSP/ML recognition is intentionally deferred until core architecture and data flow are stable.
