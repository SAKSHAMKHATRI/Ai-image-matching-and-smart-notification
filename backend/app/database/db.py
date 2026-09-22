import json
import os
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[2] / "data" / "profiles.db"
SCHEMA_VERSION = 6


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
            email TEXT,
            display_name TEXT,
            status TEXT NOT NULL DEFAULT 'ACTIVE'
                CHECK (status IN ('ACTIVE', 'SUSPENDED', 'CLOSED')),
            role TEXT NOT NULL DEFAULT 'STUDENT'
                CHECK (role IN ('STUDENT', 'ADMIN', 'STAFF')),
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
            color TEXT,
            brand TEXT,
            campus TEXT,
            lost_at TEXT,
            location TEXT,
            description TEXT,
            distinctive_features TEXT,
            image_reference TEXT,
            description_embedding_blob TEXT,
            image_embedding_blob TEXT,
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
            item_name TEXT,
            category TEXT,
            color TEXT,
            brand TEXT,
            description TEXT,
            distinctive_features TEXT,
            image_reference TEXT,
            ai_attributes_json TEXT,
            image_embedding_blob TEXT,
            analysis_status TEXT NOT NULL DEFAULT 'NOT_REQUESTED'
                CHECK (analysis_status IN ('NOT_REQUESTED', 'QUEUED', 'ANALYZED', 'UNAVAILABLE', 'FAILED')),
            analysis_error TEXT,
            analysis_requested_at TEXT,
            analysis_completed_at TEXT,
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

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL DEFAULT 'POSSIBLE_MATCH'
                CHECK (type IN ('POSSIBLE_MATCH', 'CLAIM_SUBMITTED', 'CLAIM_STATUS', 'CLAIM_UPDATE', 'STATUS_CHANGE', 'SYSTEM')),
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            entity_type TEXT,
            entity_id INTEGER,
            is_read INTEGER NOT NULL DEFAULT 0,
            email_status TEXT NOT NULL DEFAULT 'SKIPPED',
            email_recipient TEXT,
            email_error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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
        CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
        CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(is_read);
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

        # Idempotent column migrations for lost_items
        lost_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(lost_items)")
        }
        for column, definition in (
            ("color", "TEXT"),
            ("brand", "TEXT"),
            ("distinctive_features", "TEXT"),
            ("image_reference", "TEXT"),
            ("description_embedding_blob", "TEXT"),
            ("image_embedding_blob", "TEXT"),
        ):
            if column not in lost_columns:
                connection.execute(
                    f"ALTER TABLE lost_items ADD COLUMN {column} {definition}"
                )

        # Idempotent column migrations for found_items
        found_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(found_items)")
        }
        for column, definition in (
            ("analysis_status", "TEXT NOT NULL DEFAULT 'NOT_REQUESTED'"),
            ("analysis_error", "TEXT"),
            ("analysis_requested_at", "TEXT"),
            ("analysis_completed_at", "TEXT"),
            ("item_name", "TEXT"),
            ("category", "TEXT"),
            ("color", "TEXT"),
            ("brand", "TEXT"),
            ("description", "TEXT"),
            ("distinctive_features", "TEXT"),
            ("ai_attributes_json", "TEXT"),
            ("image_embedding_blob", "TEXT"),
        ):
            if column not in found_columns:
                connection.execute(
                    f"ALTER TABLE found_items ADD COLUMN {column} {definition}"
                )

        # Idempotent column migrations for users
        user_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(users)")
        }
        if "role" not in user_columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'STUDENT'"
            )
        if "status" not in user_columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'ACTIVE'"
            )
        if "email" not in user_columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN email TEXT"
            )
        if "display_name" not in user_columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN display_name TEXT"
            )

        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_firebase_uid ON users(firebase_uid)"
        )

        # Idempotent column migrations for notifications
        notif_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(notifications)")
        }
        for column, definition in (
            ("email_status", "TEXT NOT NULL DEFAULT 'SKIPPED'"),
            ("email_recipient", "TEXT"),
            ("email_error", "TEXT"),
        ):
            if column not in notif_columns:
                connection.execute(
                    f"ALTER TABLE notifications ADD COLUMN {column} {definition}"
                )

        # Backfill default values for existing user rows
        connection.execute(
            "UPDATE users SET role = 'STUDENT' WHERE role IS NULL OR role = ''"
        )
        connection.execute(
            "UPDATE users SET status = 'ACTIVE' WHERE status IS NULL OR status = ''"
        )
        connection.execute(
            """
            UPDATE users
            SET email = (
                SELECT university_email FROM student_profiles
                WHERE student_profiles.firebase_uid = users.firebase_uid
            )
            WHERE email IS NULL AND EXISTS (
                SELECT 1 FROM student_profiles
                WHERE student_profiles.firebase_uid = users.firebase_uid
            )
            """
        )

        # Backfill missing embeddings for existing lost and found reports with text
        try:
            from app.services.embedding_service import (
                generate_semantic_feature_vector,
                serialize_embedding,
            )
            lost_rows = connection.execute(
                "SELECT id, item_name, description FROM lost_items WHERE description_embedding_blob IS NULL"
            ).fetchall()
            for r in lost_rows:
                txt = r["description"] or r["item_name"]
                if txt and str(txt).strip():
                    vec = generate_semantic_feature_vector(str(txt).strip())
                    connection.execute(
                        "UPDATE lost_items SET description_embedding_blob = ? WHERE id = ?",
                        (serialize_embedding(vec), r["id"]),
                    )

            found_rows = connection.execute(
                "SELECT id, item_name, description FROM found_items WHERE image_embedding_blob IS NULL"
            ).fetchall()
            for r in found_rows:
                txt = r["description"] or r["item_name"]
                if txt and str(txt).strip():
                    vec = generate_semantic_feature_vector(str(txt).strip())
                    connection.execute(
                        "UPDATE found_items SET image_embedding_blob = ? WHERE id = ?",
                        (serialize_embedding(vec), r["id"]),
                    )
        except Exception:
            pass

        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")




def profile_row_to_dict(row: sqlite3.Row) -> dict[str, object]:
    return dict(row)


def get_profile(firebase_uid: str) -> dict[str, object] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT p.*, COALESCE(u.role, 'STUDENT') as role
            FROM student_profiles p
            LEFT JOIN users u ON p.firebase_uid = u.firebase_uid
            WHERE p.firebase_uid = ?
            """,
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


def ensure_user(
    firebase_uid: str,
    role: str = "STUDENT",
    email: str | None = None,
    display_name: str | None = None,
) -> int:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO users (firebase_uid, role, email, display_name)
            VALUES (?, ?, ?, ?)
            """,
            (firebase_uid, role, email, display_name),
        )
        updates: list[str] = []
        params: list[Any] = []
        if email is not None:
            updates.append("email = ?")
            params.append(email)
        if display_name is not None:
            updates.append("display_name = ?")
            params.append(display_name)
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(firebase_uid)
            connection.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE firebase_uid = ?",
                tuple(params),
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


def get_user_record(user_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, firebase_uid, email, display_name, status, role, created_at, updated_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def get_user_by_firebase_uid(firebase_uid: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, firebase_uid, email, display_name, status, role, created_at, updated_at FROM users WHERE firebase_uid = ?",
            (firebase_uid,),
        ).fetchone()
        return dict(row) if row else None


def update_user_status(user_id: int, status: str) -> dict[str, Any] | None:
    if status not in ("ACTIVE", "SUSPENDED", "CLOSED"):
        raise ValueError(f"Invalid user status: {status}")
    with get_connection() as connection:
        connection.execute(
            "UPDATE users SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, user_id),
        )
    return get_user_record(user_id)


def update_user_role(user_id: int, role: str) -> dict[str, Any] | None:
    if role not in ("STUDENT", "ADMIN", "STAFF"):
        raise ValueError(f"Invalid user role: {role}")
    with get_connection() as connection:
        connection.execute(
            "UPDATE users SET role = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (role, user_id),
        )
    return get_user_record(user_id)



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
