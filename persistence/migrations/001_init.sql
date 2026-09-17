-- PianoTutor v1 schema
-- Applied once by persistence.db.Database on first run (see schema_version table).

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    source_path TEXT NOT NULL,
    ppq INTEGER NOT NULL,
    duration_ms REAL NOT NULL,
    imported_at TEXT NOT NULL DEFAULT (datetime('now')),
    tempo_map_json TEXT NOT NULL,
    time_signature_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS song_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    note_index INTEGER NOT NULL,
    pitch_midi INTEGER NOT NULL,
    start_ms REAL NOT NULL,
    end_ms REAL NOT NULL,
    hand TEXT NOT NULL DEFAULT 'unknown',
    track_id INTEGER NOT NULL DEFAULT 0,
    velocity INTEGER NOT NULL DEFAULT 64
);

CREATE INDEX IF NOT EXISTS idx_song_notes_song_id ON song_notes(song_id);
CREATE INDEX IF NOT EXISTS idx_song_notes_start_ms ON song_notes(song_id, start_ms);

CREATE TABLE IF NOT EXISTS song_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    section_index INTEGER NOT NULL,
    label TEXT NOT NULL,
    start_ms REAL NOT NULL,
    end_ms REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_song_sections_song_id ON song_sections(song_id);

CREATE TABLE IF NOT EXISTS practice_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    section_id INTEGER REFERENCES song_sections(id) ON DELETE SET NULL,
    mode TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at TEXT,
    total_score REAL,
    note_accuracy_score REAL,
    chord_completeness_score REAL,
    timing_score REAL,
    consistency_score REAL,
    loop_count INTEGER NOT NULL DEFAULT 0,
    mastered INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_practice_sessions_song_id ON practice_sessions(song_id);

CREATE TABLE IF NOT EXISTS session_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES practice_sessions(id) ON DELETE CASCADE,
    t_ms REAL NOT NULL,
    event_type TEXT NOT NULL,
    related_pitches_json TEXT NOT NULL DEFAULT '[]',
    score_delta REAL NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_session_events_session_id ON session_events(session_id);

CREATE TABLE IF NOT EXISTS calibration_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    device_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    latency_ms REAL NOT NULL,
    latency_stddev_ms REAL NOT NULL,
    noise_floor_rms REAL NOT NULL,
    recommended_onset_threshold REAL NOT NULL,
    sample_count INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
