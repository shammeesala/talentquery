-- Views are the only thing the LLM will be allowed to query.
-- Each view leaves out the columns a role should not see.
--
--   analyst   : leadership and HR analytics. No names, contact details,
--               free text, or row-level demographics.
--   recruiter : everything an analyst sees, plus contact details and
--               message/feedback text for day-to-day recruiting.
--
-- Nobody gets row-level gender or ethnicity through this tool. Demographics
-- are only available as counts in vw_diversity_summary, with small groups hidden.
-- Which role can use which view is listed in talentquery/roles.py.


-- ===================== Analyst views (no PII) =====================

CREATE VIEW vw_profiles AS
SELECT profile_id, title, current_company, location_city, location_state, location_country,
       exp_years, highest_degree, latest_major, seniority_level, num_skills,
       has_resume, is_thin_profile, created_ts
FROM profiles;

CREATE VIEW vw_positions AS
SELECT position_id, ats_job_id, job_code, title, department, location_city, location_state,
       employment_type, seniority_level, store_number, req_status, is_posted,
       min_pay, mid_pay, max_pay, pay_frequency,
       hiring_manager, recruiter, created_ts, closed_ts
FROM positions;

CREATE VIEW vw_stores AS
SELECT store_number, store_name, location_city, location_state, district, area, region, open_date
FROM stores;

CREATE VIEW vw_applications AS
SELECT application_id, profile_id, position_id, source_type, current_stage,
       rejection_reason, application_ts, stage_updated_ts, hired_ts
FROM applications;

CREATE VIEW vw_stage_history AS
SELECT history_id, application_id, from_stage, to_stage, changed_ts
FROM application_stage_history;

-- Scores only. Reviewer and comments are in vw_feedback_details.
CREATE VIEW vw_interview_feedback AS
SELECT feedback_id, application_id, profile_id, interview_type, status,
       rating, recommendation, requested_ts, submitted_ts
FROM profile_feedback;

-- Who sent what, when. No sender address, subject or body.
CREATE VIEW vw_message_stats AS
SELECT message_id, profile_id, application_id, direction, channel, sender_type, sent_ts
FROM user_messages;

CREATE VIEW vw_email_delivery AS
SELECT delivery_id, message_id, event_type, bounce_reason, event_ts
FROM email_delivery_feedback;

CREATE VIEW vw_hiring_events AS
SELECT event_id, name, event_type, location_city, location_state, event_date, capacity
FROM hiring_events;

CREATE VIEW vw_event_attendance AS
SELECT attendance_id, event_id, profile_id, status, registered_ts, checked_in_ts
FROM event_attendance;

-- error_message is left out because some messages contain candidate emails.
CREATE VIEW vw_writeback_events AS
SELECT writeback_id, application_id, target_system, attempt_number, status,
       error_code, attempted_ts
FROM writeback_events;

-- Demographics as counts only, one dimension at a time (gender OR ethnicity,
-- never both), so a small group can't be narrowed down to a person.
-- Groups with fewer than 10 applications are hidden (small-cell suppression).
CREATE VIEW vw_diversity_summary AS
SELECT department, application_year, dimension, group_value, applications, hires
FROM (
    SELECT pos.department,
           substr(a.application_ts, 1, 4) AS application_year,
           'gender' AS dimension,
           p.gender AS group_value,
           COUNT(*) AS applications,
           SUM(a.current_stage = 'hired') AS hires
    FROM applications a
    JOIN profiles p ON p.profile_id = a.profile_id
    JOIN positions pos ON pos.position_id = a.position_id
    GROUP BY 1, 2, 3, 4

    UNION ALL

    SELECT pos.department,
           substr(a.application_ts, 1, 4),
           'ethnicity',
           p.ethnicity,
           COUNT(*),
           SUM(a.current_stage = 'hired')
    FROM applications a
    JOIN profiles p ON p.profile_id = a.profile_id
    JOIN positions pos ON pos.position_id = a.position_id
    GROUP BY 1, 2, 3, 4
)
WHERE applications >= 10;


-- ===================== Recruiter-only views (contain PII) =====================

CREATE VIEW vw_candidate_contacts AS
SELECT profile_id, candidate_id, first_name, last_name, email, phone
FROM profiles;

CREATE VIEW vw_messages AS
SELECT message_id, profile_id, application_id, direction, channel, sender_type,
       email_from, subject, body, sent_ts
FROM user_messages;

CREATE VIEW vw_feedback_details AS
SELECT feedback_id, application_id, reviewer_email, comments
FROM profile_feedback;

CREATE VIEW vw_writeback_errors AS
SELECT writeback_id, application_id, target_system, error_code, error_message, attempted_ts
FROM writeback_events
WHERE status = 'failed';
