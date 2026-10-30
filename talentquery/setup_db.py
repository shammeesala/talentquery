"""Create an empty recruiting database from db/schema.sql.

Run it with:  python -m talentquery.setup_db
"""
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FILE = PROJECT_ROOT / "db" / "schema.sql"
DB_FILE = PROJECT_ROOT / "data" / "recruiting.db"


def create_database(db_path=DB_FILE):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Start fresh every time, so the schema file is always the source of truth.
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_FILE.read_text())
    conn.commit()

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    conn.close()

    print(f"Created {db_path}")
    for (name,) in tables:
        print(f"  - {name}")


if __name__ == "__main__":
    create_database()
