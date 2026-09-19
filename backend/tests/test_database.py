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
