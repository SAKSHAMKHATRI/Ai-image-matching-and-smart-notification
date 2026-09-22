import pytest
from fastapi.testclient import TestClient

from app.config import FirebaseConfigError
from app.main import app


@pytest.fixture
def unconfigured_client(monkeypatch):
    """Client whose Firebase Admin config lookup raises FirebaseConfigError."""

    def raise_unconfigured() -> dict[str, str]:
        raise FirebaseConfigError("Firebase Admin configuration is incomplete.")

    # Patch where firebase.py actually looks the function up, and drop any
    # cached Firebase app from earlier imports or tests.
    monkeypatch.setattr(
        "app.auth.firebase.get_firebase_options", raise_unconfigured
    )
    from app.auth import firebase as auth_firebase

    auth_firebase.get_firebase_app.cache_clear()
    yield TestClient(app)
    auth_firebase.get_firebase_app.cache_clear()


def test_unconfigured_firebase_admin_returns_503_not_401(unconfigured_client) -> None:
    """A server misconfiguration must surface as 503, never as a fake 401."""
    response = unconfigured_client.get(
        "/api/profile", headers={"Authorization": "Bearer some-token"}
    )

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_unconfigured_firebase_admin_does_not_break_health(unconfigured_client) -> None:
    response = unconfigured_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
