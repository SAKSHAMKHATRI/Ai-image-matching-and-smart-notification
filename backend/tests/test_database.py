import sqlite3

import pytest

from app.database import db, repositories


@pytest.fixture
def database_path(tmp_path, monkeypatch):
    path = tmp_path / "foundation.db"
    monkeypatch.setattr(db, "get_database_path", lambda: path)
    db.initialize_database()
    return path


def test_schema_is_repeatable_and_enables_foreign_keys(database_path) -> None:
    db.initialize_database()
    db.initialize_database()

    with db.get_connection() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]

    assert {"users", "lost_items", "found_items", "matches", "claims", "audit_events"} <= tables
    assert version == db.SCHEMA_VERSION
    assert foreign_keys == 1


def test_existing_phase_two_profiles_are_migrated_to_users(tmp_path, monkeypatch) -> None:
    path = tmp_path / "legacy.db"
    monkeypatch.setattr(db, "get_database_path", lambda: path)
    with db.get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE student_profiles (
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
        connection.execute(
            """
            INSERT INTO student_profiles
                (firebase_uid, full_name, roll_number, class_section,
                 course_program, semester, phone_number, university_email, campus)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-user",
                "Legacy Student",
                "OLD-001",
                "A",
                "Computer Science",
                2,
                "+1 555 000 0000",
                "legacy@example.edu",
                "Main Campus",
            ),
        )

    db.initialize_database()

    assert db.get_user_id("legacy-user") is not None


def test_foreign_keys_reject_records_for_unknown_users(database_path) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        repositories.create_lost_item(999, "Backpack")

    assert repositories.get_lost_item(1) is None


def test_repository_relationships_and_status_audit(database_path) -> None:
    user_id = db.ensure_user("firebase-user-1")
    lost_item_id = repositories.create_lost_item(
        user_id,
        "Backpack",
        category="Bags",
        campus="North Campus",
    )
    found_item_id = repositories.create_found_item(user_id, campus="North Campus")
    match_id = repositories.create_match(found_item_id, lost_item_id, score=0.75)
    claim_id = repositories.create_claim(match_id, user_id)

    assert repositories.get_lost_item(lost_item_id)["status"] == "ACTIVE"
    assert repositories.get_found_item(found_item_id)["status"] == "REPORTED"
    assert repositories.get_match(match_id)["status"] == "SUGGESTED"
    assert repositories.get_claim(claim_id)["status"] == "SUGGESTED"

    assert repositories.change_status(
        "claims",
        claim_id,
        "OWNER_VERIFICATION",
        actor_user_id=user_id,
        details={"reason": "manual review"},
    )

    claim = repositories.get_claim(claim_id)
    assert claim["status"] == "OWNER_VERIFICATION"
    with db.get_connection() as connection:
        audit = connection.execute(
            "SELECT * FROM audit_events WHERE entity_type = 'claims' AND entity_id = ?",
            (claim_id,),
        ).fetchone()
    assert audit["action"] == "STATUS_CHANGED"
    assert audit["actor_user_id"] == user_id


def test_status_constraints_and_duplicate_matches_are_enforced(database_path) -> None:
    user_id = db.ensure_user("firebase-user-1")
    lost_item_id = repositories.create_lost_item(user_id, "Notebook")
    found_item_id = repositories.create_found_item(user_id)
    repositories.create_match(found_item_id, lost_item_id)

    with pytest.raises(sqlite3.IntegrityError):
        repositories.create_match(found_item_id, lost_item_id)

    match_id = repositories.get_match(1)["id"]
    claim_id = repositories.create_claim(match_id, user_id)
    with pytest.raises(sqlite3.IntegrityError):
        repositories.change_status("claims", claim_id, "NOT_A_REAL_STATUS")


def test_migration_from_v5_users_without_role_column(tmp_path, monkeypatch) -> None:
    """Regression test: existing v5 database with users table lacking 'role' is safely upgraded."""
    path = tmp_path / "v5_legacy.db"
    monkeypatch.setattr(db, "get_database_path", lambda: path)

    # 1. Create older v5 schema database manually
    with db.get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                firebase_uid TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE', 'SUSPENDED', 'CLOSED')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE student_profiles (
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

            CREATE TABLE lost_items (
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

            CREATE TABLE found_items (
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

            CREATE TABLE matches (
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

            CREATE TABLE claims (
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

            CREATE TABLE audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_user_id INTEGER,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE SET NULL
            );

            PRAGMA user_version = 5;
            """
        )

        # Insert pre-existing user in older schema
        connection.execute(
            "INSERT INTO users (firebase_uid, status) VALUES ('old-student-uid', 'ACTIVE')"
        )

    # Verify older schema has no role column
    with db.get_connection() as connection:
        cols_before = [r[1] for r in connection.execute("PRAGMA table_info(users)").fetchall()]
        assert "role" not in cols_before

    # 2. Run initialization / migration
    db.initialize_database()

    # 3. Verify upgraded schema and data preservation
    with db.get_connection() as connection:
        cols_after = [r[1] for r in connection.execute("PRAGMA table_info(users)").fetchall()]
        assert "role" in cols_after
        user_row = connection.execute(
            "SELECT id, firebase_uid, status, role FROM users WHERE firebase_uid = 'old-student-uid'"
        ).fetchone()
        assert user_row["role"] == "STUDENT"
        assert user_row["status"] == "ACTIVE"

    # 4. Verify ensure_user works for both existing user and new user
    existing_id = db.ensure_user("old-student-uid")
    assert existing_id == user_row["id"]

    new_id = db.ensure_user("new-student-uid")
    assert new_id > existing_id
    new_user = db.get_user_record(new_id)
    assert new_user["role"] == "STUDENT"
