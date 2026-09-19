import hashlib

import pytest
from fastapi.testclient import TestClient

from app.api import found_items
from app.auth.firebase import AuthenticatedUser, get_current_user
from app.database import db
from app.main import app
from app.services.storage_service import StoredImage


FOUND_ITEM = {
    "found_date": "2026-09-19",
    "found_location": "Library west entrance",
    "campus": "North Campus",
}


@pytest.fixture
def found_item_client(tmp_path, monkeypatch):
    database_path = tmp_path / "found-items.db"
    monkeypatch.setattr(db, "get_database_path", lambda: database_path)
    db.initialize_database()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="firebase-user-1",
        email="student@example.edu",
        email_verified=True,
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def create_found_item(client: TestClient) -> int:
    response = client.post("/api/found-items", json=FOUND_ITEM)
    assert response.status_code == 201
    return response.json()["id"]


def test_finder_can_create_and_list_found_item(found_item_client: TestClient) -> None:
    item_id = create_found_item(found_item_client)

    listed = found_item_client.get("/api/found-items")

    assert listed.status_code == 200
    assert listed.json()[0]["id"] == item_id
    assert listed.json()[0]["status"] == "REPORTED"
    assert listed.json()[0]["analysis_status"] == "NOT_REQUESTED"


def test_found_item_image_uses_secure_found_collection(found_item_client, monkeypatch) -> None:
    item_id = create_found_item(found_item_client)
    owner_key = hashlib.sha256(b"firebase-user-1").hexdigest()
    monkeypatch.setattr(
        found_items,
        "store_image",
        lambda contents, content_type, firebase_uid, stored_item_id, collection: StoredImage(
            path=f"{collection}/{owner_key}/{stored_item_id}/image.png",
            content_type=content_type,
            size=len(contents),
        ),
    )

    response = found_item_client.post(
        f"/api/found-items/{item_id}/image",
        files={"image": ("found.png", b"\x89PNG\r\n\x1a\nimage", "image/png")},
    )

    assert response.status_code == 200
    assert response.json()["image_reference"] == f"found-items/{owner_key}/{item_id}/image.png"


def test_analysis_trigger_has_safe_ai_unavailable_fallback(found_item_client, monkeypatch) -> None:
    item_id = create_found_item(found_item_client)
    monkeypatch.setattr(
        found_items,
        "store_image",
        lambda contents, content_type, firebase_uid, stored_item_id, collection: StoredImage(
            path=f"{collection}/owner/{stored_item_id}/image.png",
            content_type=content_type,
            size=len(contents),
        ),
    )
    found_item_client.post(
        f"/api/found-items/{item_id}/image",
        files={"image": ("found.png", b"\x89PNG\r\n\x1a\nimage", "image/png")},
    )

    response = found_item_client.post(f"/api/found-items/{item_id}/analyze")

    assert response.status_code == 200
    assert response.json()["accepted"] is False
    assert response.json()["found_item"]["analysis_status"] == "UNAVAILABLE"
    assert "not configured" in response.json()["message"]


def test_analysis_requires_an_image(found_item_client: TestClient) -> None:
    item_id = create_found_item(found_item_client)

    response = found_item_client.post(f"/api/found-items/{item_id}/analyze")

    assert response.status_code == 400


def test_found_item_rejects_other_owner(found_item_client: TestClient) -> None:
    item_id = create_found_item(found_item_client)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="different-user",
        email="other@example.edu",
        email_verified=True,
    )

    response = found_item_client.get(f"/api/found-items/{item_id}")

    assert response.status_code == 404
