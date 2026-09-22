from hashlib import sha256

import pytest
from fastapi.testclient import TestClient

from app.api import lost_items
from app.auth.firebase import AuthenticatedUser, get_current_user
from app.database import db
from app.main import app
from app.services.storage_service import StoredImage


REPORT = {
    "item_name": "Blue backpack",
    "category": "Bags",
    "color": "Navy blue",
    "brand": "ExampleBrand",
    "lost_date": "2026-09-18",
    "approximate_location": "Library west entrance",
    "description": "A navy backpack with a silver zipper and two front pockets.",
    "distinctive_features": "Small astronomy patch.",
}


@pytest.fixture
def storage_client(tmp_path, monkeypatch):
    database_path = tmp_path / "storage.db"
    monkeypatch.setattr(db, "get_database_path", lambda: database_path)
    db.initialize_database()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="firebase-user-1",
        email="student@example.edu",
        email_verified=True,
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def create_report(client: TestClient) -> int:
    response = client.post("/api/lost-items", json=REPORT)
    assert response.status_code == 201
    return response.json()["id"]


def test_valid_image_is_stored_as_reference(storage_client, monkeypatch) -> None:
    item_id = create_report(storage_client)
    monkeypatch.setattr(
        lost_items,
        "store_image",
        lambda contents, content_type, firebase_uid, stored_item_id: StoredImage(
            path=f"lost-items/{sha256(firebase_uid.encode()).hexdigest()}/{stored_item_id}/safe-name.png",
            content_type=content_type,
            size=len(contents),
        ),
    )

    response = storage_client.post(
        f"/api/lost-items/{item_id}/image",
        files={"image": ("../../unsafe.png", b"\x89PNG\r\n\x1a\nimage", "image/png")},
    )

    assert response.status_code == 200
    owner_key = sha256(b"firebase-user-1").hexdigest()
    assert response.json()["image_reference"] == f"lost-items/{owner_key}/{item_id}/safe-name.png"
    assert "image" not in response.json()


def test_unsupported_mime_type_is_rejected(storage_client) -> None:
    item_id = create_report(storage_client)

    response = storage_client.post(
        f"/api/lost-items/{item_id}/image",
        files={"image": ("payload.txt", b"not-an-image", "text/plain")},
    )

    assert response.status_code == 415


def test_mismatched_image_signature_is_rejected(storage_client) -> None:
    item_id = create_report(storage_client)

    response = storage_client.post(
        f"/api/lost-items/{item_id}/image",
        files={"image": ("payload.png", b"not-a-png", "image/png")},
    )

    assert response.status_code == 415


def test_oversized_image_is_rejected(storage_client) -> None:
    item_id = create_report(storage_client)

    response = storage_client.post(
        f"/api/lost-items/{item_id}/image",
        files={
            "image": (
                "large.png",
                b"\x89PNG\r\n\x1a\n" + b"x" * (5 * 1024 * 1024),
                "image/png",
            )
        },
    )

    assert response.status_code == 413


def test_other_owner_cannot_upload_to_report(storage_client, monkeypatch) -> None:
    item_id = create_report(storage_client)
    monkeypatch.setattr(
        lost_items,
        "store_image",
        lambda *args: pytest.fail("storage must not be called for another owner"),
    )
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="different-user",
        email="other@example.edu",
        email_verified=True,
    )

    response = storage_client.post(
        f"/api/lost-items/{item_id}/image",
        files={"image": ("image.png", b"\x89PNG\r\n\x1a\nimage", "image/png")},
    )

    assert response.status_code == 404


def test_storage_bucket_name_fallback(monkeypatch) -> None:
    from app.config import get_storage_bucket_name
    monkeypatch.delenv("FIREBASE_STORAGE_BUCKET", raising=False)
    monkeypatch.setattr("app.config.get_firebase_options", lambda: {"projectId": "test-project-123"})
    assert get_storage_bucket_name() == "test-project-123.appspot.com"


def test_storage_failure_returns_503(storage_client, monkeypatch) -> None:
    item_id = create_report(storage_client)
    def raise_storage_error(*args, **kwargs):
        raise RuntimeError("Cloud Storage network timeout")

    monkeypatch.setattr(lost_items, "store_image", raise_storage_error)
    response = storage_client.post(
        f"/api/lost-items/{item_id}/image",
        files={"image": ("photo.jpg", b"\xff\xd8\xffimage-bytes", "image/jpeg")},
    )
    assert response.status_code == 503
    assert "Image storage is temporarily unavailable" in response.json()["detail"]
