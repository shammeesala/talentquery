"""Fill the recruiting database with realistic fake data.

Run it with:  python -m talentquery.seed
              python -m talentquery.seed --profiles 500   (smaller, faster)

Everything here is made up. Names come from short lists, emails use the
reserved example.com domain, and phone numbers use the fictional 555-01xx range.
Dates are spread over the last 18 months, relative to today, so questions like
"applications in the last 30 days" always have data. Because of that, row counts
change a little from day to day, but two runs on the same day match exactly.
"""
import argparse
import random
import sqlite3
from datetime import datetime, timedelta

from talentquery.setup_db import DB_FILE, create_database

# ---------------------------------------------------------------------------
# Reference lists
# ---------------------------------------------------------------------------

FIRST_NAMES = [
    "Aisha", "Alex", "Ana", "Arjun", "Ben", "Carlos", "Chen", "Chloe", "Daniel", "Deepa",
    "Diego", "Emily", "Emma", "Fatima", "Grace", "Hannah", "Hiro", "Isabel", "Jamal", "James",
    "Jin", "Jordan", "Kavya", "Kofi", "Laura", "Leo", "Lucia", "Maya", "Mei", "Michael",
    "Mohammed", "Nia", "Noah", "Olivia", "Omar", "Priya", "Rahul", "Rosa", "Sam", "Sara",
    "Sofia", "Tariq", "Tom", "Uma", "Victor", "Wei", "Yara", "Yusuf", "Zoe", "Zara",
]

LAST_NAMES = [
    "Adams", "Ahmed", "Brown", "Chen", "Clark", "Davis", "Diaz", "Evans", "Garcia", "Gupta",
    "Hall", "Hernandez", "Ito", "Johnson", "Khan", "Kim", "Lee", "Lopez", "Martin", "Mensah",
    "Miller", "Moore", "Nguyen", "Okafor", "Patel", "Perez", "Reddy", "Robinson", "Rossi", "Sato",
    "Shah", "Singh", "Smith", "Taylor", "Thomas", "Walker", "Wang", "White", "Williams", "Wilson",
]

CITIES = [
    ("Seattle", "WA"), ("Tacoma", "WA"), ("Portland", "OR"), ("San Francisco", "CA"),
    ("Los Angeles", "CA"), ("San Diego", "CA"), ("Phoenix", "AZ"), ("Denver", "CO"),
    ("Dallas", "TX"), ("Austin", "TX"), ("Houston", "TX"), ("Chicago", "IL"),
    ("Atlanta", "GA"), ("Miami", "FL"), ("New York", "NY"), ("Boston", "MA"),
]

# Field hierarchy for retail stores: store -> district -> area -> region.
REGION_BY_STATE = {
    "WA": "Pacific Northwest", "OR": "Pacific Northwest", "CA": "California",
    "AZ": "Southwest", "CO": "Southwest", "TX": "South Central", "IL": "Midwest",
    "GA": "Southeast", "FL": "Southeast", "NY": "Northeast", "MA": "Northeast",
}

# Pay ranges are higher in these states.
HIGH_COST_STATES = {"CA", "NY", "MA", "WA"}

COMPANIES = [
    "Acme Retail", "Blue Harbor Foods", "Cedar Logistics", "Delta Grocers", "Evergreen Tech",
    "Fern Systems", "Granite Bank", "Harbor Health", "Ironwood Labs", "Juniper Hotels",
    "Kestrel Media", "Lakeside Markets", None,  # None = no current company
]

MAJORS = [
    "Business", "Computer Science", "Finance", "Hospitality", "Marketing", "Psychology",
    "Supply Chain Management", "Communications", "Accounting", "Information Systems",
]

# department -> list of (job_code, title, seniority_level, usual employment_type)
# The job code identifies the kind of job. Every requisition for that job shares it.
DEPARTMENTS = {
    "Retail Operations": [
        ("RET-101", "Barista", "entry", "part_time"),
        ("RET-102", "Shift Supervisor", "mid", "part_time"),
        ("RET-103", "Assistant Store Manager", "senior", "full_time"),
        ("RET-104", "Store Manager", "manager", "full_time"),
        ("RET-105", "District Manager", "director", "full_time"),
    ],
    "Supply Chain": [
        ("SCM-201", "Warehouse Associate", "entry", "full_time"),
        ("SCM-202", "Logistics Coordinator", "mid", "full_time"),
        ("SCM-203", "Supply Chain Analyst", "mid", "full_time"),
        ("SCM-204", "Distribution Center Manager", "manager", "full_time"),
    ],
    "Technology": [
        ("TEC-301", "Software Engineer", "mid", "full_time"),
        ("TEC-302", "Senior Software Engineer", "senior", "full_time"),
        ("TEC-303", "Data Engineer", "mid", "full_time"),
        ("TEC-304", "DevOps Engineer", "senior", "full_time"),
        ("TEC-305", "Engineering Intern", "entry", "internship"),
    ],
    "Finance": [
        ("FIN-401", "Financial Analyst", "mid", "full_time"),
        ("FIN-402", "Payroll Specialist", "mid", "contract"),
        ("FIN-403", "Finance Manager", "manager", "full_time"),
    ],
    "Human Resources": [
        ("HRS-501", "Recruiter", "mid", "full_time"),
        ("HRS-502", "HR Coordinator", "entry", "full_time"),
        ("HRS-503", "HR Business Partner", "senior", "full_time"),
    ],
    "Marketing": [
        ("MKT-601", "Marketing Specialist", "mid", "full_time"),
        ("MKT-602", "Social Media Coordinator", "entry", "contract"),
        ("MKT-603", "Brand Manager", "manager", "full_time"),
    ],
}

# job_code -> (low end of range, high end of range, pay frequency), before any location adjustment
PAY_RANGES = {
    "RET-101": (15.00, 19.50, "hourly"), "RET-102": (18.00, 23.50, "hourly"),
    "RET-103": (52000, 70000, "annual"), "RET-104": (65000, 92000, "annual"),
    "RET-105": (95000, 130000, "annual"),
    "SCM-201": (17.50, 22.00, "hourly"), "SCM-202": (55000, 72000, "annual"),
    "SCM-203": (68000, 92000, "annual"), "SCM-204": (105000, 140000, "annual"),
    "TEC-301": (110000, 150000, "annual"), "TEC-302": (140000, 190000, "annual"),
    "TEC-303": (115000, 155000, "annual"), "TEC-304": (135000, 180000, "annual"),
    "TEC-305": (28.00, 38.00, "hourly"),
    "FIN-401": (70000, 95000, "annual"), "FIN-402": (27.00, 36.00, "hourly"),
    "FIN-403": (115000, 150000, "annual"),
    "HRS-501": (65000, 90000, "annual"), "HRS-502": (48000, 62000, "annual"),
    "HRS-503": (100000, 135000, "annual"),
    "MKT-601": (62000, 85000, "annual"), "MKT-602": (24.00, 32.00, "hourly"),
    "MKT-603": (105000, 140000, "annual"),
}

# Within a department, some jobs are opened far more often than others.
# Jobs not listed here get weight 1.
JOB_WEIGHTS = {"RET-101": 12, "RET-102": 6, "RET-103": 3, "RET-104": 2, "RET-105": 1}

# Retail hires the most, so it gets the most positions.
DEPARTMENT_WEIGHTS = {
    "Retail Operations": 45, "Supply Chain": 15, "Technology": 15,
    "Finance": 8, "Human Resources": 7, "Marketing": 10,
}

SOURCES = ["career_site", "referral", "linkedin", "job_board", "agency", "campus", "hiring_event"]
SOURCE_WEIGHTS = [35, 12, 18, 20, 5, 4, 6]

# Hiring funnel: chance of moving to the next stage, and how many days that takes.
NEXT_STAGE = {"applied": "screening", "screening": "interview", "interview": "offer", "offer": "hired"}
PASS_RATE = {"applied": 0.55, "screening": 0.50, "interview": 0.40, "offer": 0.80}
DAYS_IN_STAGE = {"applied": (1, 7), "screening": (3, 14), "interview": (5, 21), "offer": (3, 14)}

EARLY_REJECTION_REASONS = ["not_qualified", "position_filled", "location_mismatch", "no_response"]
LATE_REJECTION_REASONS = ["failed_interview", "salary_mismatch", "position_filled"]

WRITEBACK_ERRORS = {
    "TIMEOUT": "Request to downstream system timed out after 30s",
    "VALIDATION_ERROR": "Field start_date failed validation",
    "MISSING_REQUIRED_FIELD": "Required field cost_center is missing",
    "AUTH_FAILED": "Downstream system rejected the service credentials",
    "DUPLICATE_RECORD": "Duplicate record found for {email}",  # contains PII on purpose
}

# Anchor to midnight so running the seed twice on the same day gives identical data.
NOW = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
HISTORY_START = NOW - timedelta(days=540)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def ts(dt):
    """Format a datetime the way the schema stores it."""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def random_time_between(start, end):
    seconds = int((end - start).total_seconds())
    return start + timedelta(seconds=random.randint(0, max(seconds, 0)))


def days_later(dt, low, high):
    return dt + timedelta(days=random.randint(low, high), hours=random.randint(0, 8))


def fake_phone():
    return f"+1-{random.randint(200, 989)}-555-{random.randint(100, 199):04d}"


def person_email(first, last, number, domain="example.com"):
    return f"{first.lower()}.{last.lower()}{number}@{domain}"


def recruiter_email(full_name):
    return full_name.lower().replace(" ", ".") + "@talentquery.example"


def insert_rows(conn, table, rows):
    """Insert a list of dicts. All dicts must have the same keys."""
    if not rows:
        return
    columns = list(rows[0].keys())
    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    conn.executemany(sql, [tuple(row[c] for c in columns) for row in rows])


# ---------------------------------------------------------------------------
# Generators, one per table (or pair of tables)
# ---------------------------------------------------------------------------

def make_profiles(count):
    profiles = []
    for profile_id in range(1, count + 1):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        city, state = random.choice(CITIES)
        has_resume = 1 if random.random() < 0.85 else 0
        num_skills = random.randint(0, 3) if not has_resume else random.randint(3, 40)
        created = random_time_between(HISTORY_START, NOW - timedelta(days=1))
        profiles.append({
            "profile_id": profile_id,
            "candidate_id": f"CAND-{100000 + profile_id}",
            "first_name": first,
            "last_name": last,
            "email": person_email(first, last, profile_id),
            "phone": fake_phone() if random.random() < 0.9 else None,
            "title": random.choice(DEPARTMENTS[random.choice(list(DEPARTMENTS))])[1],
            "current_company": random.choice(COMPANIES),
            "location_city": city,
            "location_state": state,
            "location_country": "US",
            "exp_years": round(random.uniform(0, 25), 1),
            "highest_degree": random.choices(
                ["high_school", "associate", "bachelor", "master", "doctorate"], [30, 15, 38, 14, 3])[0],
            "latest_major": random.choice(MAJORS) if random.random() < 0.7 else None,
            "seniority_level": random.choices(
                ["entry", "mid", "senior", "manager", "director"], [35, 35, 15, 10, 5])[0],
            "num_skills": num_skills,
            "has_resume": has_resume,
            "is_thin_profile": 1 if num_skills < 5 else 0,
            "gender": random.choices(["female", "male", "non_binary", "declined"], [47, 45, 2, 6])[0],
            "ethnicity": random.choices(
                ["asian", "black", "hispanic", "white", "two_or_more", "other", "declined"],
                [12, 13, 19, 44, 4, 2, 6])[0],
            "created_ts": ts(created),
            "last_modified_ts": ts(random_time_between(created, NOW)),
        })
    return profiles


def make_stores():
    """3-6 stores per city. Each city's stores fall into one or two districts."""
    stores = []
    areas = {}  # state -> area name, numbered in the order states appear
    for city_index, (city, state) in enumerate(CITIES):
        areas.setdefault(state, f"Area {len(areas) + 1}")
        store_count = random.randint(3, 6)
        for n in range(1, store_count + 1):
            # Bigger cities are split into two districts.
            district_offset = n % 2 if store_count >= 4 else 0
            stores.append({
                "store_number": str(10001 + len(stores)),
                "store_name": f"{city} #{n}",
                "location_city": city,
                "location_state": state,
                "district": f"District {101 + city_index * 2 + district_offset}",
                "area": areas[state],
                "region": REGION_BY_STATE[state],
                "open_date": (NOW - timedelta(days=random.randint(365 * 2, 365 * 15))).strftime("%Y-%m-%d"),
            })
    return stores


def pay_range(job_code, state):
    low, high, frequency = PAY_RANGES[job_code]
    factor = 1.15 if state in HIGH_COST_STATES else 1.0
    low, high = low * factor, high * factor
    if frequency == "hourly":
        low, high = round(low * 4) / 4, round(high * 4) / 4  # nearest quarter
    else:
        low, high = round(low, -3), round(high, -3)  # nearest thousand
    return low, (low + high) / 2, high, frequency


def make_positions(count, stores):
    positions = []
    departments = list(DEPARTMENT_WEIGHTS)
    weights = list(DEPARTMENT_WEIGHTS.values())
    for position_id in range(1, count + 1):
        department = random.choices(departments, weights)[0]
        jobs = DEPARTMENTS[department]
        job_weights = [JOB_WEIGHTS.get(job[0], 1) for job in jobs]
        job_code, title, seniority, employment_type = random.choices(jobs, job_weights)[0]

        # Store jobs belong to a store. Corporate jobs (and district managers) don't.
        store = None
        if department == "Retail Operations" and title != "District Manager":
            store = random.choice(stores)
            city, state = store["location_city"], store["location_state"]
        else:
            city, state = random.choice(CITIES)

        created = random_time_between(HISTORY_START, NOW - timedelta(days=5))
        closed = None
        if random.random() < 0.55:
            closed = days_later(created, 30, 200)
            if closed > NOW:
                closed = None

        # Closed positions become 'filled' or 'cancelled' later, once we know
        # whether anyone was hired (see finalize_positions).
        if closed:
            status = "filled"
        else:
            status = "on_hold" if random.random() < 0.1 else "open"

        min_pay, mid_pay, max_pay, pay_frequency = pay_range(job_code, state)
        positions.append({
            "position_id": position_id,
            "ats_job_id": f"REQ-{20000 + position_id}",
            "job_code": job_code,
            "title": title,
            "department": department,
            "location_city": city,
            "location_state": state,
            "employment_type": employment_type,
            "seniority_level": seniority,
            "store_number": store["store_number"] if store else None,
            "req_status": status,
            "is_posted": 1 if status == "open" and random.random() < 0.85 else 0,
            "min_pay": min_pay,
            "mid_pay": mid_pay,
            "max_pay": max_pay,
            "pay_frequency": pay_frequency,
            "hiring_manager": f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            "recruiter": f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            "created_ts": ts(created),
            "closed_ts": ts(closed) if closed else None,
            "last_modified_ts": ts(closed or random_time_between(created, NOW)),
        })
    return positions


def finalize_positions(positions, applications):
    """A closed requisition is 'filled' if someone was hired for it, otherwise 'cancelled'.

    A hire can land a little after the requisition stopped taking applicants,
    so a filled requisition closes on its last hire date if that is later.
    """
    last_hire = {}
    for app in applications:
        if app["hired_ts"]:
            position_id = app["position_id"]
            last_hire[position_id] = max(last_hire.get(position_id, ""), app["hired_ts"])

    for position in positions:
        if position["closed_ts"] is None:
            continue
        hired_at = last_hire.get(position["position_id"])
        if hired_at:
            position["req_status"] = "filled"
            position["closed_ts"] = max(position["closed_ts"], hired_at)
        else:
            position["req_status"] = "cancelled"
        position["last_modified_ts"] = position["closed_ts"]


def walk_funnel(application_id, applied_at):
    """Move one application through the hiring stages.

    Returns (final_stage, rejection_reason, hired_at, history_rows).
    If the next step would happen in the future, the application stays
    in its current stage, which is what an in-progress application looks like.
    """
    stage = "applied"
    entered_at = applied_at
    history = [(None, "applied", applied_at)]

    while stage != "hired":
        low, high = DAYS_IN_STAGE[stage]
        next_time = days_later(entered_at, low, high)
        if next_time > NOW:
            return stage, None, None, history  # still in progress

        if random.random() < PASS_RATE[stage]:
            new_stage = NEXT_STAGE[stage]
            history.append((stage, new_stage, next_time))
            stage, entered_at = new_stage, next_time
            continue

        # The application ends here.
        if stage == "offer":
            end_stage, reason = "withdrawn", None  # candidate declined the offer
        elif random.random() < 0.85:
            end_stage = "rejected"
            reasons = EARLY_REJECTION_REASONS if stage in ("applied", "screening") else LATE_REJECTION_REASONS
            reason = random.choice(reasons)
        else:
            end_stage, reason = "withdrawn", None
        history.append((stage, end_stage, next_time))
        return end_stage, reason, None, history

    return "hired", None, entered_at, history


def make_applications(profiles, positions):
    applications = []
    history_rows = []
    for profile in profiles:
        how_many = random.choices([1, 2, 3, 4], [60, 25, 10, 5])[0]
        applied_to = set()

        # People usually create a profile when they first apply, so the first
        # application comes right after the profile. Later ones are spread out.
        applied_at = datetime.fromisoformat(profile["created_ts"]) + timedelta(hours=random.randint(0, 72))

        for _ in range(how_many):
            if applied_at > NOW:
                break
            # Only positions that were open on that date, and not applied to already.
            open_then = [
                p for p in positions
                if p["position_id"] not in applied_to
                and datetime.fromisoformat(p["created_ts"]) <= applied_at
                and (p["closed_ts"] is None or datetime.fromisoformat(p["closed_ts"]) > applied_at)
            ]
            if not open_then:
                applied_at += timedelta(days=random.randint(5, 60))
                continue
            position = random.choice(open_then)
            applied_to.add(position["position_id"])

            application_id = len(applications) + 1
            stage, reason, hired_at, history = walk_funnel(application_id, applied_at)
            last_change = history[-1][2]

            applications.append({
                "application_id": application_id,
                "profile_id": profile["profile_id"],
                "position_id": position["position_id"],
                "source_type": random.choices(SOURCES, SOURCE_WEIGHTS)[0],
                "current_stage": stage,
                "rejection_reason": reason,
                "application_ts": ts(applied_at),
                "stage_updated_ts": ts(last_change),
                "hired_ts": ts(hired_at) if hired_at else None,
                "last_modified_ts": ts(last_change),
            })
            for from_stage, to_stage, changed_at in history:
                history_rows.append({
                    "history_id": len(history_rows) + 1,
                    "application_id": application_id,
                    "from_stage": from_stage,
                    "to_stage": to_stage,
                    "changed_ts": ts(changed_at),
                })

            # The next application, if any, comes a while later.
            applied_at += timedelta(days=random.randint(5, 120), hours=random.randint(0, 12))
    return applications, history_rows


def make_feedback(applications, history_rows):
    """Phone screen feedback for screened applications, 1-3 scorecards for interviews."""
    # When did each application enter screening / interview, and did it get past that stage?
    entered = {}
    for row in history_rows:
        entered[(row["application_id"], row["to_stage"])] = datetime.fromisoformat(row["changed_ts"])

    feedback = []
    for app in applications:
        app_id = app["application_id"]
        for stage, interview_types, passed_stage in [
            ("screening", ["phone_screen"], "interview"),
            ("interview", random.sample(["technical", "behavioral", "panel", "hiring_manager"], random.randint(1, 3)), "offer"),
        ]:
            if (app_id, stage) not in entered:
                continue
            passed = (app_id, passed_stage) in entered
            for interview_type in interview_types:
                requested = entered[(app_id, stage)] + timedelta(hours=random.randint(1, 48))
                submitted = requested + timedelta(hours=random.randint(2, 96))
                if random.random() < 0.05:
                    status = "cancelled"
                elif submitted > NOW:
                    status = "requested"
                else:
                    status = "submitted"

                rating = recommendation = comments = None
                if status == "submitted":
                    rating = random.randint(3, 5) if passed else random.randint(1, 3)
                    if rating >= 4:
                        recommendation = "strong_yes" if rating == 5 else "yes"
                    else:
                        recommendation = "no" if rating == 3 else "strong_no"
                    comments = random.choice([
                        "Strong communication and clear examples.",
                        "Good experience but limited depth in the core skills.",
                        "Great culture add, would like to see more ownership.",
                        "Did not meet the bar for this level.",
                        "Solid answers, a little nervous at the start.",
                    ])

                feedback.append({
                    "feedback_id": len(feedback) + 1,
                    "application_id": app_id,
                    "profile_id": app["profile_id"],
                    "reviewer_email": recruiter_email(f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"),
                    "interview_type": interview_type,
                    "status": status,
                    "rating": rating,
                    "recommendation": recommendation,
                    "comments": comments,
                    "requested_ts": ts(requested),
                    "submitted_ts": ts(submitted) if status == "submitted" else None,
                })
    return feedback


def make_messages(applications, profiles_by_id, positions_by_id):
    """A confirmation email for every application, then a few back-and-forth messages."""
    messages = []
    deliveries = []

    def add_message(app, profile, direction, channel, sender_type, email_from, subject, body, sent_at):
        message_id = len(messages) + 1
        messages.append({
            "message_id": message_id,
            "profile_id": profile["profile_id"],
            "application_id": app["application_id"],
            "direction": direction,
            "channel": channel,
            "sender_type": sender_type,
            "email_from": email_from,
            "subject": subject,
            "body": body,
            "sent_ts": ts(sent_at),
        })
        if direction == "outbound" and channel == "email":
            add_delivery_events(message_id, sent_at)

    def add_delivery_events(message_id, sent_at):
        def add(event_type, when, reason=None):
            if when <= NOW:
                deliveries.append({
                    "delivery_id": len(deliveries) + 1,
                    "message_id": message_id,
                    "event_type": event_type,
                    "bounce_reason": reason,
                    "event_ts": ts(when),
                })

        if random.random() < 0.04:
            add("bounced", sent_at + timedelta(minutes=1),
                random.choice(["mailbox_full", "address_not_found", "blocked_by_recipient"]))
            return
        add("delivered", sent_at + timedelta(minutes=1))
        if random.random() < 0.6:
            opened = sent_at + timedelta(hours=random.randint(1, 72))
            add("opened", opened)
            if random.random() < 0.25:
                add("clicked", opened + timedelta(minutes=random.randint(1, 30)))
        if random.random() < 0.01:
            add("unsubscribed", sent_at + timedelta(days=random.randint(1, 5)))

    for app in applications:
        profile = profiles_by_id[app["profile_id"]]
        position = positions_by_id[app["position_id"]]
        applied_at = datetime.fromisoformat(app["application_ts"])
        recruiter = position["recruiter"]

        add_message(app, profile, "outbound", "email", "system", "no-reply@talentquery.example",
                    f"We received your application for {position['title']}",
                    f"Hi {profile['first_name']}, thanks for applying to {position['title']}. "
                    f"We'll be in touch soon.",
                    applied_at + timedelta(minutes=2))

        sent_at = applied_at
        for _ in range(random.randint(0, 4)):
            sent_at = sent_at + timedelta(days=random.randint(1, 10), hours=random.randint(0, 8))
            if sent_at > NOW:
                break
            channel = random.choices(["email", "sms", "chat"], [75, 20, 5])[0]
            if random.random() < 0.6:
                add_message(app, profile, "outbound", channel, "recruiter",
                            recruiter_email(recruiter) if channel == "email" else None,
                            f"Next steps for {position['title']}" if channel == "email" else None,
                            f"Hi {profile['first_name']}, this is {recruiter}. Are you free for a quick call this week?",
                            sent_at)
            else:
                add_message(app, profile, "inbound", channel, "candidate",
                            profile["email"] if channel == "email" else None,
                            f"Re: {position['title']}" if channel == "email" else None,
                            f"Thanks! I'm available Tuesday afternoon. My number is {profile['phone'] or 'on my profile'}.",
                            sent_at)
    return messages, deliveries


def make_events(profiles, count):
    events = []
    attendance = []
    for event_id in range(1, count + 1):
        event_type = random.choices(["in_person", "virtual", "campus"], [55, 30, 15])[0]
        city, state = random.choice(CITIES) if event_type != "virtual" else (None, None)
        # Most events are in the past, a few are coming up.
        event_date = random_time_between(HISTORY_START + timedelta(days=30), NOW + timedelta(days=45))
        event_date = event_date.replace(hour=random.choice([10, 13, 17]), minute=0, second=0)
        capacity = random.choice([50, 100, 150, 200, 300])
        label = {"in_person": "Hiring Day", "virtual": "Virtual Career Fair", "campus": "Campus Recruiting Day"}[event_type]

        events.append({
            "event_id": event_id,
            "name": f"{city or 'Online'} {label} {event_date:%b %Y}",
            "event_type": event_type,
            "location_city": city,
            "location_state": state,
            "event_date": ts(event_date),
            "capacity": capacity,
            "created_ts": ts(event_date - timedelta(days=random.randint(20, 60))),
        })

        # Only people whose profile existed before they registered can register.
        eligible = [p for p in profiles
                    if datetime.fromisoformat(p["created_ts"]) < event_date - timedelta(days=2)]
        registrants = random.sample(eligible, k=min(len(eligible), random.randint(capacity // 3, capacity)))
        for profile in registrants:
            earliest = max(datetime.fromisoformat(profile["created_ts"]), event_date - timedelta(days=30))
            registered = random_time_between(earliest, event_date - timedelta(days=1))
            checked_in = None
            if event_date > NOW:
                status = "registered"
            else:
                status = random.choices(["attended", "no_show", "cancelled"], [60, 30, 10])[0]
                if status == "attended":
                    checked_in = event_date + timedelta(minutes=random.randint(0, 90))
            attendance.append({
                "attendance_id": len(attendance) + 1,
                "event_id": event_id,
                "profile_id": profile["profile_id"],
                "status": status,
                "registered_ts": ts(registered),
                "checked_in_ts": ts(checked_in) if checked_in else None,
            })
    return events, attendance


def make_writebacks(applications, history_rows, profiles_by_id):
    """Push offers and hires to downstream systems. Some attempts fail and get retried."""
    reached_offer = {}
    for row in history_rows:
        if row["to_stage"] == "offer":
            reached_offer[row["application_id"]] = datetime.fromisoformat(row["changed_ts"])

    writebacks = []
    for app in applications:
        app_id = app["application_id"]
        targets = []
        if app_id in reached_offer:
            targets.append(("background_check", reached_offer[app_id]))
        if app["hired_ts"]:
            hired_at = datetime.fromisoformat(app["hired_ts"])
            targets += [("ats", hired_at), ("hris", hired_at), ("onboarding", hired_at)]

        for target_system, start in targets:
            attempted = start + timedelta(minutes=random.randint(5, 600))
            for attempt_number in (1, 2, 3):
                if attempted > NOW:
                    break
                failed = random.random() < (0.12 if attempt_number == 1 else 0.35)
                error_code = error_message = None
                if failed:
                    error_code = random.choice(list(WRITEBACK_ERRORS))
                    error_message = WRITEBACK_ERRORS[error_code].format(
                        email=profiles_by_id[app["profile_id"]]["email"])
                writebacks.append({
                    "writeback_id": len(writebacks) + 1,
                    "application_id": app_id,
                    "target_system": target_system,
                    "attempt_number": attempt_number,
                    "status": "failed" if failed else "success",
                    "error_code": error_code,
                    "error_message": error_message,
                    "attempted_ts": ts(attempted),
                })
                if not failed:
                    break
                attempted = attempted + timedelta(hours=random.randint(1, 6))
    return writebacks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed(db_path=DB_FILE, profile_count=3000, position_count=120, event_count=25, random_seed=42):
    random.seed(random_seed)
    create_database(db_path)

    profiles = make_profiles(profile_count)
    stores = make_stores()
    positions = make_positions(position_count, stores)
    applications, history_rows = make_applications(profiles, positions)
    finalize_positions(positions, applications)
    profiles_by_id = {p["profile_id"]: p for p in profiles}
    positions_by_id = {p["position_id"]: p for p in positions}
    feedback = make_feedback(applications, history_rows)
    messages, deliveries = make_messages(applications, profiles_by_id, positions_by_id)
    events, attendance = make_events(profiles, event_count)
    writebacks = make_writebacks(applications, history_rows, profiles_by_id)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite only checks foreign keys when asked
    tables = [
        ("profiles", profiles),
        ("stores", stores),
        ("positions", positions),
        ("applications", applications),
        ("application_stage_history", history_rows),
        ("profile_feedback", feedback),
        ("user_messages", messages),
        ("email_delivery_feedback", deliveries),
        ("hiring_events", events),
        ("event_attendance", attendance),
        ("writeback_events", writebacks),
    ]
    for table, rows in tables:
        insert_rows(conn, table, rows)
    conn.commit()

    print("\nRows loaded:")
    for table, _ in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<26} {count:>7,}")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fill the database with fake recruiting data.")
    parser.add_argument("--profiles", type=int, default=3000, help="how many people to create")
    parser.add_argument("--seed", type=int, default=42, help="random seed, for repeatable data")
    args = parser.parse_args()
    seed(profile_count=args.profiles, random_seed=args.seed)
