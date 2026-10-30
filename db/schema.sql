-- TalentQuery recruiting schema.
-- Modeled on the entities a talent platform exposes (profiles, positions, applications,
-- feedback, messages, events), with generic names and fake data.
--
-- These are the RAW tables. Later, the LLM will only query views built on top of them,
-- so sensitive columns (names, contact details, demographics, free text) can be hidden.
--
-- Conventions:
--   * Timestamps end in _ts and are stored as ISO text, e.g. '2026-10-30 14:05:00'.
--   * Flags are INTEGER 0/1 (SQLite has no boolean type).
--   * CHECK constraints list every allowed value, so the LLM never has to guess them.

-- The main person record. One profile per person.
CREATE TABLE profiles (
    profile_id       INTEGER PRIMARY KEY,
    candidate_id     TEXT NOT NULL UNIQUE,   -- the person's ID in the ATS
    first_name       TEXT NOT NULL,
    last_name        TEXT NOT NULL,
    email            TEXT NOT NULL,
    phone            TEXT,
    title            TEXT,                   -- current job title
    current_company  TEXT,
    location_city    TEXT,
    location_state   TEXT,
    location_country TEXT NOT NULL DEFAULT 'US',
    exp_years        REAL,
    highest_degree   TEXT CHECK (highest_degree IN ('high_school', 'associate', 'bachelor', 'master', 'doctorate')),
    latest_major     TEXT,
    seniority_level  TEXT CHECK (seniority_level IN ('entry', 'mid', 'senior', 'manager', 'director')),
    num_skills       INTEGER NOT NULL DEFAULT 0,
    has_resume       INTEGER NOT NULL CHECK (has_resume IN (0, 1)),
    is_thin_profile  INTEGER NOT NULL CHECK (is_thin_profile IN (0, 1)),  -- too little data to match well
    gender           TEXT CHECK (gender IN ('female', 'male', 'non_binary', 'declined')),
    ethnicity        TEXT CHECK (ethnicity IN ('asian', 'black', 'hispanic', 'white', 'two_or_more', 'other', 'declined')),
    created_ts       TEXT NOT NULL,
    last_modified_ts TEXT NOT NULL
);

-- A job opening. ats_job_id links it back to the ATS requisition.
CREATE TABLE positions (
    position_id      INTEGER PRIMARY KEY,
    ats_job_id       TEXT NOT NULL UNIQUE,
    title            TEXT NOT NULL,
    department       TEXT NOT NULL,
    location_city    TEXT NOT NULL,
    location_state   TEXT NOT NULL,
    employment_type  TEXT NOT NULL CHECK (employment_type IN ('full_time', 'part_time', 'contract', 'internship')),
    seniority_level  TEXT NOT NULL CHECK (seniority_level IN ('entry', 'mid', 'senior', 'manager', 'director')),
    is_open          INTEGER NOT NULL CHECK (is_open IN (0, 1)),
    is_posted        INTEGER NOT NULL CHECK (is_posted IN (0, 1)),  -- visible on the career site
    hiring_manager   TEXT NOT NULL,
    recruiter        TEXT NOT NULL,
    created_ts       TEXT NOT NULL,
    closed_ts        TEXT,
    last_modified_ts TEXT NOT NULL
);

-- A profile applying to a position. One person can have many applications.
CREATE TABLE applications (
    application_id   INTEGER PRIMARY KEY,
    profile_id       INTEGER NOT NULL REFERENCES profiles (profile_id),
    position_id      INTEGER NOT NULL REFERENCES positions (position_id),
    source_type      TEXT NOT NULL CHECK (source_type IN ('career_site', 'referral', 'linkedin', 'job_board', 'agency', 'campus', 'hiring_event')),
    current_stage    TEXT NOT NULL CHECK (current_stage IN ('applied', 'screening', 'interview', 'offer', 'hired', 'rejected', 'withdrawn')),
    rejection_reason TEXT,
    application_ts   TEXT NOT NULL,
    stage_updated_ts TEXT NOT NULL,
    hired_ts         TEXT,
    last_modified_ts TEXT NOT NULL
);

-- One row every time an application moves to a new stage.
CREATE TABLE application_stage_history (
    history_id     INTEGER PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications (application_id),
    from_stage     TEXT,                     -- NULL for the first 'applied' row
    to_stage       TEXT NOT NULL,
    changed_ts     TEXT NOT NULL
);

-- Interview scorecards.
CREATE TABLE profile_feedback (
    feedback_id    INTEGER PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications (application_id),
    profile_id     INTEGER NOT NULL REFERENCES profiles (profile_id),
    reviewer_email TEXT NOT NULL,
    interview_type TEXT NOT NULL CHECK (interview_type IN ('phone_screen', 'technical', 'behavioral', 'panel', 'hiring_manager')),
    status         TEXT NOT NULL CHECK (status IN ('requested', 'submitted', 'cancelled')),
    rating         INTEGER CHECK (rating BETWEEN 1 AND 5),   -- NULL until submitted
    recommendation TEXT CHECK (recommendation IN ('strong_yes', 'yes', 'no', 'strong_no')),
    comments       TEXT,
    requested_ts   TEXT NOT NULL,
    submitted_ts   TEXT
);

-- Emails, texts and chat messages between recruiters and candidates.
CREATE TABLE user_messages (
    message_id     INTEGER PRIMARY KEY,
    profile_id     INTEGER NOT NULL REFERENCES profiles (profile_id),
    application_id INTEGER REFERENCES applications (application_id),
    direction      TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    channel        TEXT NOT NULL CHECK (channel IN ('email', 'sms', 'chat')),
    sender_type    TEXT NOT NULL CHECK (sender_type IN ('candidate', 'recruiter', 'system')),
    email_from     TEXT,
    subject        TEXT,
    body           TEXT NOT NULL,
    sent_ts        TEXT NOT NULL
);

-- What happened to an outbound email after it was sent.
CREATE TABLE email_delivery_feedback (
    delivery_id   INTEGER PRIMARY KEY,
    message_id    INTEGER NOT NULL REFERENCES user_messages (message_id),
    event_type    TEXT NOT NULL CHECK (event_type IN ('delivered', 'bounced', 'opened', 'clicked', 'unsubscribed')),
    bounce_reason TEXT,
    event_ts      TEXT NOT NULL
);

-- Hiring events (job fairs, virtual events, campus visits).
CREATE TABLE hiring_events (
    event_id       INTEGER PRIMARY KEY,
    name           TEXT NOT NULL,
    event_type     TEXT NOT NULL CHECK (event_type IN ('in_person', 'virtual', 'campus')),
    location_city  TEXT,
    location_state TEXT,
    event_date     TEXT NOT NULL,
    capacity       INTEGER NOT NULL,
    created_ts     TEXT NOT NULL
);

-- Who registered for an event and whether they showed up.
CREATE TABLE event_attendance (
    attendance_id INTEGER PRIMARY KEY,
    event_id      INTEGER NOT NULL REFERENCES hiring_events (event_id),
    profile_id    INTEGER NOT NULL REFERENCES profiles (profile_id),
    status        TEXT NOT NULL CHECK (status IN ('registered', 'attended', 'no_show', 'cancelled')),
    registered_ts TEXT NOT NULL,
    checked_in_ts TEXT,
    UNIQUE (event_id, profile_id)
);

-- Each attempt to push an application to a downstream system.
-- A failed attempt is usually retried; attempt_number counts the tries.
CREATE TABLE writeback_events (
    writeback_id   INTEGER PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications (application_id),
    target_system  TEXT NOT NULL CHECK (target_system IN ('ats', 'hris', 'background_check', 'onboarding')),
    attempt_number INTEGER NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('success', 'failed')),
    error_code     TEXT,
    error_message  TEXT,
    attempted_ts   TEXT NOT NULL
);

CREATE INDEX idx_applications_profile ON applications (profile_id);
CREATE INDEX idx_applications_position ON applications (position_id);
CREATE INDEX idx_applications_ts ON applications (application_ts);
CREATE INDEX idx_stage_history_application ON application_stage_history (application_id);
CREATE INDEX idx_feedback_application ON profile_feedback (application_id);
CREATE INDEX idx_messages_profile ON user_messages (profile_id);
CREATE INDEX idx_delivery_message ON email_delivery_feedback (message_id);
CREATE INDEX idx_attendance_event ON event_attendance (event_id);
CREATE INDEX idx_writeback_application ON writeback_events (application_id);
