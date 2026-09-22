import pytest
from fastapi.testclient import TestClient

from app.auth import firebase
from app import config
from app.database import db
from app.main import app


@pytest.fixture(autouse=True)
def isolated_auth_db(tmp_path, monkeypatch):
    """Ensure auth tests run against a dedicated temporary test database."""
    test_db = tmp_path / "auth_test.db"
    monkeypatch.setattr(db, "get_database_path", lambda: test_db)
    db.initialize_database()
    yield


client = TestClient(app)


def test_health_remains_public() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protected_endpoint_rejects_missing_token() -> None:
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required."


def test_protected_endpoint_rejects_invalid_token(monkeypatch) -> None:
    def reject_token(token: str):
        raise RuntimeError("invalid token")

    monkeypatch.setattr(firebase, "verify_firebase_token", reject_token)

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired authentication token."


def test_protected_endpoint_returns_verified_identity(monkeypatch) -> None:
    monkeypatch.setattr(
        firebase,
        "verify_firebase_token",
        lambda token: {
            "uid": "verified-user-123",
            "email": "student@example.edu",
            "email_verified": True,
            "roll_number": "client-data-must-not-be-returned",
        },
    )

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["uid"] == "verified-user-123"
    assert data["email"] == "student@example.edu"
    assert data["email_verified"] is True
    assert data["role"] == "STUDENT"
    assert data["is_admin"] is False
    assert "roll_number" not in data


def test_malformed_authorization_scheme_is_rejected() -> None:
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Basic not-a-bearer-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required."


def test_missing_firebase_configuration_returns_service_unavailable(monkeypatch) -> None:
    for variable in (
        "FIREBASE_SERVICE_ACCOUNT_PATH",
        "FIREBASE_SERVICE_ACCOUNT_JSON",
        "FIREBASE_PROJECT_ID",
        "FIREBASE_CLIENT_EMAIL",
        "FIREBASE_PRIVATE_KEY",
    ):
        monkeypatch.delenv(variable, raising=False)

    config.get_firebase_options.cache_clear()
    firebase.get_firebase_app.cache_clear()

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer token-without-config"},
    )

    # A server-side misconfiguration is 503, not a caller-side 401.
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Authentication service is not configured. Contact the administrator."
    )
