import os
import sqlite3
from pathlib import Path
from typing import Iterator

DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[2] / "data" / "profiles.db"


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


def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
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
            )
            """
        )


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
