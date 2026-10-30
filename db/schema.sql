-- Raw tables, shaped like a recruiting platform's data warehouse.
-- Later on, the LLM will NOT query these directly. It will only see views.
-- Dates are stored as ISO text ('2026-10-30 14:05:00') so SQLite's date functions work.

CREATE TABLE jobs (
    job_id          INTEGER PRIMARY KEY,
    requisition_id  TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    department      TEXT NOT NULL,
    location_city   TEXT NOT NULL,
    location_state  TEXT NOT NULL,
    employment_type TEXT NOT NULL CHECK (employment_type IN ('full_time', 'part_time', 'contract', 'internship')),
    status          TEXT NOT NULL CHECK (status IN ('open', 'on_hold', 'closed')),
    hiring_manager  TEXT NOT NULL,
    opened_at       TEXT NOT NULL,
    closed_at       TEXT
);

CREATE TABLE candidates (
    candidate_id INTEGER PRIMARY KEY,
    first_name   TEXT NOT NULL,
    last_name    TEXT NOT NULL,
    email        TEXT NOT NULL,
    phone        TEXT,
    city         TEXT,
    state        TEXT,
    source       TEXT NOT NULL CHECK (source IN ('career_site', 'referral', 'linkedin', 'job_board', 'agency', 'campus')),
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

-- A candidate can have several versions of their profile. Only one is current.
CREATE TABLE profiles (
    profile_id        INTEGER PRIMARY KEY,
    candidate_id      INTEGER NOT NULL REFERENCES candidates (candidate_id),
    version           INTEGER NOT NULL,
    is_current        INTEGER NOT NULL CHECK (is_current IN (0, 1)),
    current_title     TEXT,
    years_experience  REAL,
    highest_education TEXT CHECK (highest_education IN ('high_school', 'associate', 'bachelor', 'master', 'doctorate')),
    resume_text       TEXT,
    created_at        TEXT NOT NULL,
    UNIQUE (candidate_id, version)
);

CREATE TABLE applications (
    application_id   INTEGER PRIMARY KEY,
    candidate_id     INTEGER NOT NULL REFERENCES candidates (candidate_id),
    profile_id       INTEGER NOT NULL REFERENCES profiles (profile_id),
    job_id           INTEGER NOT NULL REFERENCES jobs (job_id),
    status           TEXT NOT NULL CHECK (status IN ('applied', 'screening', 'interview', 'offer', 'hired', 'rejected', 'withdrawn')),
    rejection_reason TEXT,
    applied_at       TEXT NOT NULL,
    stage_updated_at TEXT NOT NULL,
    hired_at         TEXT
);

-- One row every time an application moves to a new stage.
CREATE TABLE application_stage_events (
    event_id       INTEGER PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications (application_id),
    from_stage     TEXT,
    to_stage       TEXT NOT NULL,
    changed_at     TEXT NOT NULL
);

CREATE TABLE user_messages (
    message_id     INTEGER PRIMARY KEY,
    candidate_id   INTEGER NOT NULL REFERENCES candidates (candidate_id),
    application_id INTEGER REFERENCES applications (application_id),
    direction      TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    channel        TEXT NOT NULL CHECK (channel IN ('email', 'sms', 'chat')),
    sender_type    TEXT NOT NULL CHECK (sender_type IN ('candidate', 'recruiter', 'system')),
    body           TEXT NOT NULL,
    sent_at        TEXT NOT NULL
);

-- Each attempt to push an application to a downstream system (HR system, background check, onboarding).
CREATE TABLE writeback_events (
    event_id       INTEGER PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications (application_id),
    target_system  TEXT NOT NULL CHECK (target_system IN ('hris', 'background_check', 'onboarding')),
    attempt_number INTEGER NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('success', 'failed')),
    error_code     TEXT,
    error_message  TEXT,
    attempted_at   TEXT NOT NULL
);

CREATE INDEX idx_applications_candidate ON applications (candidate_id);
CREATE INDEX idx_applications_job ON applications (job_id);
CREATE INDEX idx_applications_applied_at ON applications (applied_at);
CREATE INDEX idx_stage_events_application ON application_stage_events (application_id);
CREATE INDEX idx_messages_candidate ON user_messages (candidate_id);
CREATE INDEX idx_writeback_application ON writeback_events (application_id);
