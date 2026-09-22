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
    from app.services.analysis_service import UnavailableImageAnalysisProvider
    monkeypatch.setattr(found_items, "get_analysis_provider", lambda: UnavailableImageAnalysisProvider())

    found_item_client.post(
        f"/api/found-items/{item_id}/image",
        files={"image": ("found.png", b"\x89PNG\r\n\x1a\nimage", "image/png")},
    )

    response = found_item_client.post(f"/api/found-items/{item_id}/analyze")

    assert response.status_code == 200
    assert response.json()["accepted"] is False
    assert response.json()["found_item"]["analysis_status"] == "UNAVAILABLE"
    assert "not configured" in response.json()["message"]


def test_successful_image_analysis_triggers_foundry_and_populates_fields(found_item_client, monkeypatch) -> None:
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

    from app.services.analysis_service import AnalysisResult

    class FakeProvider:
        def analyze(self, request):
            return AnalysisResult(
                description="Navy blue canvas backpack with leather straps.",
                attributes={
                    "object_type": "backpack",
                    "category": "Bags & Wallets",
                    "primary_color": "navy blue",
                    "brand": "Herschel",
                    "visible_features": ["leather straps", "front zipper pocket"],
                    "confidence": 0.95,
                },
            )

    monkeypatch.setattr(found_items, "get_analysis_provider", lambda: FakeProvider())

    response = found_item_client.post(f"/api/found-items/{item_id}/analyze")

    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] is True
    assert data["found_item"]["analysis_status"] == "ANALYZED"
    assert data["found_item"]["description"] == "Navy blue canvas backpack with leather straps."
    assert data["found_item"]["item_name"] == "backpack"
    assert data["found_item"]["category"] == "Bags & Wallets"
    assert data["found_item"]["color"] == "navy blue"
    assert data["found_item"]["brand"] == "Herschel"
    assert data["found_item"]["distinctive_features"] == "leather straps, front zipper pocket"
    assert data["attributes"]["confidence"] == 0.95


def test_ai_timeout_or_failure_falls_back_safely(found_item_client, monkeypatch) -> None:
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

    from app.services.analysis_service import AnalysisFailed

    class FailingProvider:
        def analyze(self, request):
            raise AnalysisFailed("Foundry request timed out.")

    monkeypatch.setattr(found_items, "get_analysis_provider", lambda: FailingProvider())

    response = found_item_client.post(f"/api/found-items/{item_id}/analyze")

    assert response.status_code == 200
    assert response.json()["accepted"] is False
    assert response.json()["found_item"]["analysis_status"] == "FAILED"
    assert "could not be completed" in response.json()["message"]


def test_analyze_image_preview_endpoint_success(found_item_client, monkeypatch) -> None:
    from app.services.analysis_service import AnalysisResult

    class FakeProvider:
        def analyze_bytes(self, image_bytes, content_type="image/jpeg"):
            return AnalysisResult(
                description="Stainless steel water bottle.",
                attributes={
                    "object_type": "water bottle",
                    "category": "Personal Items",
                    "primary_color": "silver",
                    "brand": "Yeti",
                    "visible_features": ["campus sticker"],
                },
            )

    monkeypatch.setattr(found_items, "get_analysis_provider", lambda: FakeProvider())

    response = found_item_client.post(
        "/api/found-items/analyze-image",
        files={"image": ("bottle.png", b"\x89PNG\r\n\x1a\nimage", "image/png")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["description"] == "Stainless steel water bottle."
    assert data["item_name"] == "water bottle"
    assert data["brand"] == "Yeti"
    assert data["distinctive_features"] == "campus sticker"


def test_analyze_image_preview_endpoint_unavailable_fallback(found_item_client, monkeypatch) -> None:
    from app.services.analysis_service import UnavailableImageAnalysisProvider
    monkeypatch.setattr(found_items, "get_analysis_provider", lambda: UnavailableImageAnalysisProvider())

    response = found_item_client.post(
        "/api/found-items/analyze-image",
        files={"image": ("bottle.png", b"\x89PNG\r\n\x1a\nimage", "image/png")},
    )

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert "unavailable" in response.json()["message"]


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


def test_update_own_found_item(found_item_client: TestClient) -> None:
    item_id = create_found_item(found_item_client)

    update_payload = {
        "item_name": "Updated Backpack",
        "category": "Bags & Backpacks",
        "color": "Navy Blue",
        "brand": "Herschel",
        "found_location": "Student Center 2nd Floor",
        "campus": "North Campus",
        "description": "Updated detailed description of the found backpack.",
    }

    response = found_item_client.patch(f"/api/found-items/{item_id}", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["item_name"] == "Updated Backpack"
    assert data["category"] == "Bags & Backpacks"
    assert data["color"] == "Navy Blue"
    assert data["brand"] == "Herschel"
    assert data["found_location"] == "Student Center 2nd Floor"
    assert data["campus"] == "North Campus"
    assert data["description"] == "Updated detailed description of the found backpack."


def test_update_found_item_rejects_other_user(found_item_client: TestClient) -> None:
    item_id = create_found_item(found_item_client)

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="different-user-999",
        email="other@example.edu",
        email_verified=True,
    )

    response = found_item_client.patch(
        f"/api/found-items/{item_id}",
        json={"item_name": "Hacked Title"},
    )
    assert response.status_code == 404


def test_delete_own_found_item(found_item_client: TestClient) -> None:
    item_id = create_found_item(found_item_client)

    delete_res = found_item_client.delete(f"/api/found-items/{item_id}")
    assert delete_res.status_code == 204

    get_res = found_item_client.get(f"/api/found-items/{item_id}")
    assert get_res.status_code == 404


def test_delete_found_item_rejects_other_user(found_item_client: TestClient) -> None:
    item_id = create_found_item(found_item_client)

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="different-user-999",
        email="other@example.edu",
        email_verified=True,
    )

    delete_res = found_item_client.delete(f"/api/found-items/{item_id}")
    assert delete_res.status_code == 404

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="firebase-user-1",
        email="student@example.edu",
        email_verified=True,
    )
    get_res = found_item_client.get(f"/api/found-items/{item_id}")
    assert get_res.status_code == 200
