import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import database
from app.auth.firebase import AuthenticatedUser, get_current_user
from app.database import db
from app.main import app


PROFILE = {
    "full_name": "Ada Lovelace",
    "roll_number": "CS-001",
    "class_section": "A",
    "course_program": "Computer Science",
    "semester": 3,
    "phone_number": "+1 555 123 4567",
    "university_email": "ada@example.edu",
    "campus": "North Campus",
}


@pytest.fixture
def profile_client(tmp_path, monkeypatch):
    database_path = tmp_path / "profiles.db"
    monkeypatch.setattr(db, "get_database_path", lambda: database_path)
    db.initialize_database()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="firebase-user-1",
        email="ada@example.edu",
        email_verified=True,
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_profile_requires_authentication() -> None:
    response = TestClient(app).get("/api/profile")

    assert response.status_code == 401


def test_profile_can_be_created_read_and_updated(profile_client: TestClient) -> None:
    created = profile_client.post("/api/profile", json=PROFILE)
    assert created.status_code == 201
    assert created.json()["full_name"] == "Ada Lovelace"
    assert created.json()["firebase_uid"] == "firebase-user-1"

    loaded = profile_client.get("/api/profile")
    assert loaded.status_code == 200
    assert loaded.json()["roll_number"] == "CS-001"

    updated = {**PROFILE, "campus": "South Campus", "semester": 4}
    response = profile_client.patch("/api/profile", json=updated)
    assert response.status_code == 200
    assert response.json()["campus"] == "South Campus"
    assert response.json()["semester"] == 4


def test_duplicate_profile_is_rejected(profile_client: TestClient) -> None:
    assert profile_client.post("/api/profile", json=PROFILE).status_code == 201

    duplicate = profile_client.post("/api/profile", json=PROFILE)

    assert duplicate.status_code == 409


def test_invalid_profile_data_is_rejected(profile_client: TestClient) -> None:
    invalid_profile = {**PROFILE, "semester": 0, "university_email": "not-an-email"}

    response = profile_client.post("/api/profile", json=invalid_profile)

    assert response.status_code == 422
    assert len(response.json()["detail"]) >= 1


def test_profile_is_scoped_to_verified_uid(profile_client: TestClient) -> None:
    assert profile_client.post("/api/profile", json=PROFILE).status_code == 201

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="different-user",
        email="other@example.edu",
        email_verified=True,
    )

    response = profile_client.get("/api/profile")

    assert response.status_code == 404
    assert response.json()["detail"] == "Student profile not found."


def test_database_enables_foreign_keys(profile_client: TestClient) -> None:
    connection = db.get_connection()
    try:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        connection.close()
