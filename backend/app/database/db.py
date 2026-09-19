import json
import os
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[2] / "data" / "profiles.db"
SCHEMA_VERSION = 1


def get_database_path() -> Path:
    configured_path = os.getenv("PROFILE_DATABASE_PATH")
    return Path(configured_path) if configured_path else DEFAULT_DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    database_path = get_database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            firebase_uid TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'ACTIVE'
                CHECK (status IN ('ACTIVE', 'SUSPENDED', 'CLOSED')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS student_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            firebase_uid TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            roll_number TEXT NOT NULL,
            class_section TEXT NOT NULL,
            course_program TEXT NOT NULL,
            semester INTEGER NOT NULL,
            phone_number TEXT NOT NULL,
            university_email TEXT NOT NULL,
            campus TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS lost_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE'
                CHECK (status IN ('DRAFT', 'ACTIVE', 'MATCHED', 'RETURNED', 'CLOSED')),
            item_name TEXT NOT NULL,
            category TEXT,
            campus TEXT,
            lost_at TEXT,
            location TEXT,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS found_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'REPORTED'
                CHECK (status IN ('REPORTED', 'ANALYZING', 'ANALYZED', 'RETURNED', 'CLOSED')),
            campus TEXT,
            found_at TEXT,
            location TEXT,
            image_reference TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            found_item_id INTEGER NOT NULL,
            lost_item_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'SUGGESTED'
                CHECK (status IN ('SUGGESTED', 'REVIEWED', 'REJECTED', 'CLAIMED')),
            score REAL,
            explanation_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (found_item_id) REFERENCES found_items(id) ON DELETE RESTRICT,
            FOREIGN KEY (lost_item_id) REFERENCES lost_items(id) ON DELETE RESTRICT,
            UNIQUE (found_item_id, lost_item_id)
        );

        CREATE TABLE IF NOT EXISTS claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER NOT NULL,
            claimant_user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'SUGGESTED'
                CHECK (status IN (
                    'SUGGESTED', 'CLAIM_REQUESTED', 'OWNER_VERIFICATION',
                    'ADMIN_REVIEW', 'APPROVED', 'REJECTED', 'RETURNED'
                )),
            verification_notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE RESTRICT,
            FOREIGN KEY (claimant_user_id) REFERENCES users(id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_user_id INTEGER,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            details_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_lost_items_user_id ON lost_items(user_id);
        CREATE INDEX IF NOT EXISTS idx_lost_items_status ON lost_items(status);
        CREATE INDEX IF NOT EXISTS idx_found_items_user_id ON found_items(user_id);
        CREATE INDEX IF NOT EXISTS idx_found_items_status ON found_items(status);
        CREATE INDEX IF NOT EXISTS idx_matches_found_item_id ON matches(found_item_id);
        CREATE INDEX IF NOT EXISTS idx_matches_lost_item_id ON matches(lost_item_id);
        CREATE INDEX IF NOT EXISTS idx_claims_match_id ON claims(match_id);
        CREATE INDEX IF NOT EXISTS idx_claims_claimant_user_id ON claims(claimant_user_id);
        CREATE INDEX IF NOT EXISTS idx_audit_events_entity
            ON audit_events(entity_type, entity_id);
        """
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO users (firebase_uid, created_at, updated_at)
        SELECT firebase_uid, created_at, updated_at FROM student_profiles
        """
    )


def initialize_database() -> None:
    with get_connection() as connection:
        current_version = connection.execute("PRAGMA user_version").fetchone()[0]
        if current_version > SCHEMA_VERSION:
            raise RuntimeError("Database schema version is newer than this application.")
        _create_schema(connection)
        if current_version < SCHEMA_VERSION:
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def profile_row_to_dict(row: sqlite3.Row) -> dict[str, object]:
    return dict(row)


def get_profile(firebase_uid: str) -> dict[str, object] | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM student_profiles WHERE firebase_uid = ?",
            (firebase_uid,),
        ).fetchone()
    return profile_row_to_dict(row) if row else None


def create_profile(firebase_uid: str, profile: dict[str, object]) -> dict[str, object]:
    columns = (
        "firebase_uid",
        "full_name",
        "roll_number",
        "class_section",
        "course_program",
        "semester",
        "phone_number",
        "university_email",
        "campus",
    )
    values = (firebase_uid, *(profile[column] for column in columns[1:]))
    placeholders = ", ".join("?" for _ in columns)
    with get_connection() as connection:
        connection.execute(
            f"INSERT INTO student_profiles ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )
        connection.execute(
            "INSERT OR IGNORE INTO users (firebase_uid) VALUES (?)",
            (firebase_uid,),
        )
    return get_profile(firebase_uid)  # type: ignore[return-value]


def update_profile(firebase_uid: str, profile: dict[str, object]) -> dict[str, object] | None:
    assignments = ", ".join(f"{column} = ?" for column in profile)
    values = (*profile.values(), firebase_uid)
    with get_connection() as connection:
        cursor = connection.execute(
            f"""
            UPDATE student_profiles
            SET {assignments}, updated_at = CURRENT_TIMESTAMP
            WHERE firebase_uid = ?
            """,
            values,
        )
        if cursor.rowcount == 0:
            return None
    return get_profile(firebase_uid)


def ensure_user(firebase_uid: str) -> int:
    with get_connection() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO users (firebase_uid) VALUES (?)",
            (firebase_uid,),
        )
        row = connection.execute(
            "SELECT id FROM users WHERE firebase_uid = ?",
            (firebase_uid,),
        ).fetchone()
    if row is None:
        raise RuntimeError("User could not be created.")
    return int(row[0])


def get_user_id(firebase_uid: str) -> int | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id FROM users WHERE firebase_uid = ?",
            (firebase_uid,),
        ).fetchone()
    return int(row[0]) if row else None


def insert_record(table: str, values: dict[str, Any]) -> int:
    allowed_tables = {"lost_items", "found_items", "matches", "claims"}
    if table not in allowed_tables:
        raise ValueError("Unsupported database table.")
    columns = tuple(values)
    placeholders = ", ".join("?" for _ in columns)
    with get_connection() as connection:
        cursor = connection.execute(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(values[column] for column in columns),
        )
        return int(cursor.lastrowid)


def get_record(table: str, record_id: int) -> dict[str, Any] | None:
    allowed_tables = {"lost_items", "found_items", "matches", "claims"}
    if table not in allowed_tables:
        raise ValueError("Unsupported database table.")
    with get_connection() as connection:
        row = connection.execute(
            f"SELECT * FROM {table} WHERE id = ?",
            (record_id,),
        ).fetchone()
    return dict(row) if row else None


def update_record_status(
    table: str,
    record_id: int,
    status: str,
    actor_user_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> bool:
    allowed_tables = {"lost_items", "found_items", "matches", "claims"}
    if table not in allowed_tables:
        raise ValueError("Unsupported database table.")
    with get_connection() as connection:
        cursor = connection.execute(
            f"""
            UPDATE {table}
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, record_id),
        )
        if cursor.rowcount == 0:
            return False
        connection.execute(
            """
            INSERT INTO audit_events
                (actor_user_id, entity_type, entity_id, action, details_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                actor_user_id,
                table,
                record_id,
                "STATUS_CHANGED",
                json.dumps(details) if details else None,
            ),
        )
    return True
