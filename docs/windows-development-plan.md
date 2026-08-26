# PianoTutor Windows Development Plan (v1 Scaffold)

## 1) v1 Scope Lock

Ship first:

1. MIDI import + internal timeline
2. Falling-note + piano keyboard visualization
3. Audio input selection + diagnostics
4. Latency calibration + timing compensation
5. Single-note recognition (reliable baseline)
6. Basic chord recognition (2–4 notes, confidence-aware)
7. Guided/wait mode + excerpt looping
8. Scoring (accuracy, timing, chord completeness)
9. Local progress persistence (SQLite)

Deferred (post-v1): advanced adaptive pedagogy, richer ML models, cloud sync.

---

## 2) Runtime Architecture

High-level pipeline:

**Audio subsystem → Recognition subsystem → Practice engine → UI**

### Subsystems

- **Audio subsystem**
  - Device enumeration and selection
  - Low-latency capture callbacks
  - Signal monitoring (level/clipping/noise floor)
  - Latency estimation

- **Recognition subsystem**
  - Filtering and denoise
  - Onset detection
  - Pitch candidates (single-note first)
  - Polyphonic grouping (basic v1)
  - Confidence scoring
  - Note/chord event emission

- **Practice engine**
  - Expected-note windows from MIDI timeline
  - Matching detected vs expected events
  - Tolerance rules (timing/chord window)
  - Scoring and mastery updates
  - Learner-facing feedback messages

- **UI subsystem**
  - Home/library/practice/progress/calibration
  - Falling notes + piano preview
  - Diagnostics view
  - Session summary

### Threading model

- Audio callback thread never blocks.
- Recognition runs in worker(s), consumes buffered frames.
- Practice engine consumes compact detection events, not raw audio.
- UI receives state snapshots/events only.

---

## 3) Interface Contracts

### Audio → Recognition

`AudioFrameReady`
- `timestamp_ms: float`
- `frame_id: int`
- `samples: np.ndarray` (float32 mono)
- `sample_rate: int`

### Recognition → Practice

`DetectedNoteEvent`
- `pitch_midi: int`
- `state: started|sustained|released`
- `t_ms: float` (latency-compensated available)
- `confidence: float`
- `velocity_like: float | None`

`DetectedChordEvent`
- `pitches_midi: list[int]`
- `t_start_ms: float`
- `t_end_ms: float`
- `confidence: float`

### MIDI/Timeline → Practice

`ExpectedNote`
- `note_id: int`
- `pitch_midi: int`
- `start_ms: float`
- `end_ms: float`
- `hand: left|right|unknown`
- `track_id: int`

### Practice → UI

`PracticeFeedbackEvent`
- `type: correct|missing|extra|late|early|uncertain|progress`
- `message: str`
- `related_pitches: list[int]`
- `score_delta: float`

---

## 4) Matching & Tolerance Defaults (v1)

Initial defaults (configurable):

- Note timing tolerance:
  - Guided mode: ±180 ms
  - Continuous mode: ±120 ms
- Chord grouping window: 80 ms
- Uncertain confidence threshold: < 0.60 (soft feedback)
- Hard mismatch threshold: ≥ 0.85 with wrong pitch
- Latency compensation applied before timing judgment

---

## 5) Scoring Model (v1)

Weighted score:

- Note accuracy: 40%
- Chord completeness: 30%
- Timing: 20%
- Consistency: 10%

Store score components separately; display both component scores and total.

---

## 6) Milestones & Acceptance Criteria

### Milestone A — MIDI + Visual Timeline
- Import MIDI, parse notes/measures/tempo map
- Render falling notes and current playhead

**Accept**
- Imported song displays correct note timing and measure positions.

### Milestone B — Audio I/O + Diagnostics
- Input device selection
- Live level meter and clipping indicators
- Baseline latency estimate

**Accept**
- User can verify active input and monitor signal quality.

### Milestone C — Single-Note Recognition
- Onset + monophonic pitch detection
- Calibration profile support (single-note samples)

**Accept**
- Controlled test set reaches target single-note precision/recall threshold.

### Milestone D — Basic Polyphony + Matching
- 2–4 note chord grouping
- Guided mode matching and feedback

**Accept**
- Chord completeness classification is stable on curated test fixtures.

### Milestone E — Loop-to-Mastery + Persistence
- Excerpt loop
- Mastery condition (consecutive passes)
- Session summaries + progress storage

**Accept**
- Loop exits only when mastery criteria are met and saved.

### Milestone F — Performance + Packaging
- CPU/latency profiling and tuning
- Windows packaging and smoke tests

**Accept**
- Stable realtime behavior on target hardware profile.

---

## 7) Sprint Backlog (Initial)

### Sprint 1
- App shell (PySide6)
- MIDI import/parser to DB
- Piano roll rendering
- Audio device enumeration + meter
- DB migration wiring
- Event bus skeleton

### Sprint 2
- Stream capture + ring buffer
- Single-note detection baseline
- Guided matching for single notes
- Feedback messaging
- Excerpt loop pass criteria
- Session persistence and summary

---

## 8) Testing Strategy

- Build fixture library early:
  - isolated notes, intervals, triads
  - wrong substitutions
  - early/late timing variants
- Automated tests:
  - Note precision/recall
  - Chord completeness accuracy
  - Timing error distribution after latency compensation
- Keep reproducible sample rates and reference metadata.

---

## 9) Primary Risks

1. Polyphonic false positives in low register
2. Device/driver latency variability
3. Over-penalization under low confidence
4. UI stalls from cross-thread contention

Mitigations:
- Confidence-aware scoring
- Strict callback non-blocking rule
- Clear tolerance tuning configs
- Ring buffer and bounded queues
