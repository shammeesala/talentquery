"""Which views each role is allowed to query.

Run it with:  python -m talentquery.roles
That prints each role's views and checks that no analyst view leaks a sensitive column.
"""
import sqlite3

from talentquery.setup_db import DB_FILE

ANALYST_VIEWS = [
    "vw_profiles",
    "vw_positions",
    "vw_stores",
    "vw_applications",
    "vw_stage_history",
    "vw_interview_feedback",
    "vw_message_stats",
    "vw_email_delivery",
    "vw_hiring_events",
    "vw_event_attendance",
    "vw_writeback_events",
    "vw_diversity_summary",
]

RECRUITER_VIEWS = ANALYST_VIEWS + [
    "vw_candidate_contacts",
    "vw_messages",
    "vw_feedback_details",
    "vw_writeback_errors",
]

ROLES = {
    "analyst": ANALYST_VIEWS,
    "recruiter": RECRUITER_VIEWS,
}

# Columns that must never show up in an analyst view.
PII_COLUMNS = {
    "first_name", "last_name", "email", "phone", "candidate_id",
    "email_from", "subject", "body", "reviewer_email", "comments", "error_message",
}
# Columns that must never show up in ANY view, for any role.
DEMOGRAPHIC_COLUMNS = {"gender", "ethnicity"}


def views_for_role(role):
    if role not in ROLES:
        raise ValueError(f"Unknown role '{role}'. Choose one of: {', '.join(ROLES)}")
    return ROLES[role]


def view_columns(conn, view):
    return [row[1] for row in conn.execute(f"PRAGMA table_info({view})")]


def check_views(db_path=DB_FILE):
    """Print what each role can see and return a list of problems (empty = all good)."""
    conn = sqlite3.connect(db_path)
    existing = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'view'")}
    problems = []

    for role, views in ROLES.items():
        print(f"\n{role} can query {len(views)} views:")
        for view in views:
            if view not in existing:
                problems.append(f"{view} is listed for {role} but does not exist")
                continue
            columns = view_columns(conn, view)
            print(f"  {view:<24} {', '.join(columns)}")

            leaked = set(columns) & DEMOGRAPHIC_COLUMNS
            if role == "analyst":
                leaked |= set(columns) & PII_COLUMNS
            if leaked:
                problems.append(f"{view} exposes {sorted(leaked)} to {role}")

    unassigned = existing - set(RECRUITER_VIEWS)
    if unassigned:
        problems.append(f"views not assigned to any role: {sorted(unassigned)}")

    conn.close()
    return problems


if __name__ == "__main__":
    problems = check_views()
    print()
    if problems:
        print("PROBLEMS FOUND:")
        for problem in problems:
            print(f"  - {problem}")
    else:
        print("OK: no analyst view exposes PII, and no view exposes row-level demographics.")
