import pytest
from fastapi.testclient import TestClient

from app.auth.firebase import AuthenticatedUser, get_current_user
from app.database import db
from app.main import app


REPORT = {
    "item_name": "Blue backpack",
    "category": "Bags",
    "color": "Navy blue",
    "brand": "ExampleBrand",
    "lost_date": "2026-09-18",
    "approximate_location": "Library west entrance",
    "description": "A navy backpack with a silver zipper and two front pockets.",
    "distinctive_features": "Small astronomy patch on the front pocket.",
    "image_reference": "lost-items/user-1/backpack.jpg",
}


@pytest.fixture
def lost_item_client(tmp_path, monkeypatch):
    database_path = tmp_path / "lost-items.db"
    monkeypatch.setattr(db, "get_database_path", lambda: database_path)
    db.initialize_database()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="firebase-user-1",
        email="student@example.edu",
        email_verified=True,
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_lost_item_requires_authentication() -> None:
    response = TestClient(app).get("/api/lost-items")

    assert response.status_code == 401


def test_student_can_create_list_read_update_and_delete_report(
    lost_item_client: TestClient,
) -> None:
    created = lost_item_client.post("/api/lost-items", json=REPORT)
    assert created.status_code == 201
    assert created.json()["status"] == "ACTIVE"
    assert created.json()["image_reference"] == REPORT["image_reference"]
    item_id = created.json()["id"]

    listed = lost_item_client.get("/api/lost-items")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    loaded = lost_item_client.get(f"/api/lost-items/{item_id}")
    assert loaded.status_code == 200
    assert loaded.json()["item_name"] == "Blue backpack"

    updated = {**REPORT, "description": "Updated description with a red keychain."}
    changed = lost_item_client.patch(f"/api/lost-items/{item_id}", json=updated)
    assert changed.status_code == 200
    assert changed.json()["description"] == updated["description"]

    deleted = lost_item_client.delete(f"/api/lost-items/{item_id}")
    assert deleted.status_code == 204
    assert lost_item_client.get(f"/api/lost-items/{item_id}").status_code == 404


def test_invalid_report_data_is_rejected(lost_item_client: TestClient) -> None:
    invalid_report = {**REPORT, "item_name": "x", "lost_date": "not-a-date"}

    response = lost_item_client.post("/api/lost-items", json=invalid_report)

    assert response.status_code == 422


def test_report_is_scoped_to_verified_owner(lost_item_client: TestClient) -> None:
    created = lost_item_client.post("/api/lost-items", json=REPORT)
    item_id = created.json()["id"]

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="different-user",
        email="other@example.edu",
        email_verified=True,
    )

    assert lost_item_client.get("/api/lost-items").json() == []
    assert lost_item_client.get(f"/api/lost-items/{item_id}").status_code == 404
    assert lost_item_client.patch(f"/api/lost-items/{item_id}", json=REPORT).status_code == 404
    assert lost_item_client.delete(f"/api/lost-items/{item_id}").status_code == 404
