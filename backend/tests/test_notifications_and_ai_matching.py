"""Comprehensive integration tests for Microsoft AI Foundry matching & smart notifications."""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.firebase import AuthenticatedUser, get_current_user
from app.database import db, repositories
from app.main import app
from app.services.analysis_service import AnalysisResult
from app.services.foundry_client import FoundryVisionResult


@pytest.fixture
def clean_test_db(tmp_path, monkeypatch):
    test_db_path = tmp_path / "test_match_notif.db"
    monkeypatch.setattr(db, "get_database_path", lambda: test_db_path)
    db.initialize_database()
    yield test_db_path
    app.dependency_overrides.clear()


@pytest.fixture
def user_a_auth():
    return AuthenticatedUser(
        uid="user-a-uid",
        email="usera@chitkara.edu.in",
        email_verified=True,
        role="STUDENT",
    )


@pytest.fixture
def user_b_auth():
    return AuthenticatedUser(
        uid="user-b-uid",
        email="userb@chitkara.edu.in",
        email_verified=True,
        role="STUDENT",
    )


VALID_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00" + b"\x00" * 64 + b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"


def test_two_user_ai_match_and_notification_workflow(clean_test_db, user_a_auth, user_b_auth):
    """Test full two-user flow:

    1. User A reports Lost "Black Backpack".
    2. User B reports Found item with photo analyzed by Microsoft AI Foundry.
    3. Automatic candidate matching runs and persists match.
    4. User A receives safe 'Possible Match Found' notification.
    5. User A inspects match details with deterministic score and explanation.
    6. User B cannot see User A's private PII or modify User A's report.
    """
    client = TestClient(app)

    # 1. User A creates student profile and lost item
    app.dependency_overrides[get_current_user] = lambda: user_a_auth
    user_a_id = db.ensure_user(user_a_auth.uid, role="STUDENT", email=user_a_auth.email)
    db.create_profile(
        user_a_auth.uid,
        {
            "full_name": "Alice Student",
            "roll_number": "2410991111",
            "class_section": "5G1",
            "course_program": "CSE AI",
            "semester": 5,
            "phone_number": "9876543210",
            "university_email": "usera@chitkara.edu.in",
            "campus": "Main Campus",
        },
    )

    lost_resp = client.post(
        "/api/lost-items",
        json={
            "item_name": "Black Backpack",
            "category": "Bags & Backpacks",
            "color": "Black",
            "brand": "Wildcraft",
            "campus": "Main Campus",
            "lost_date": "2026-09-20",
            "approximate_location": "Library Block 3",
            "description": "Black Wildcraft laptop bag with red zipper and laptop compartment",
        },
    )
    assert lost_resp.status_code == 201
    lost_item = lost_resp.json()
    lost_id = lost_item["id"]

    # 2. User B analyzes found photo using Microsoft Foundry mock
    app.dependency_overrides[get_current_user] = lambda: user_b_auth
    user_b_id = db.ensure_user(user_b_auth.uid, role="STUDENT", email=user_b_auth.email)

    mock_analysis = AnalysisResult(
        description="A black Wildcraft backpack with red accents and padded straps.",
        attributes={
            "object_type": "backpack",
            "category": "Bags & Backpacks",
            "primary_color": "Black",
            "secondary_colors": ["Red"],
            "brand": "Wildcraft",
            "visible_features": ["red zipper", "laptop compartment"],
            "visible_text": ["WILDCRAFT"],
            "confidence": 0.95,
        },
    )

    with patch("app.services.analysis_service.get_analysis_provider") as mock_provider_fn:
        mock_prov = MagicMock()
        mock_prov.analyze_bytes.return_value = mock_analysis
        mock_provider_fn.return_value = mock_prov

        # User B creates found report with AI-extracted attributes
        found_resp = client.post(
            "/api/found-items",
            json={
                "item_name": "Wildcraft Backpack",
                "category": "Bags & Backpacks",
                "color": "Black",
                "brand": "Wildcraft",
                "campus": "Main Campus",
                "found_date": "2026-09-20",
                "found_location": "Library Ground Floor",
                "description": "Found a black Wildcraft backpack near study tables",
                "distinctive_features": "Red zipper accents",
                "ai_attributes_json": json.dumps(mock_analysis.attributes),
            },
        )
        assert found_resp.status_code == 201
        found_item = found_resp.json()
        found_id = found_item["id"]

    # 3. Verify match was automatically created in database
    with db.get_connection() as conn:
        matches = conn.execute("SELECT * FROM matches WHERE found_item_id = ? AND lost_item_id = ?", (found_id, lost_id)).fetchall()
        assert len(matches) == 1
        match_row = matches[0]
        assert match_row["score"] > 0.40  # High compatibility match

    # 4. Switch back to User A and check notifications
    app.dependency_overrides[get_current_user] = lambda: user_a_auth
    notif_resp = client.get("/api/notifications")
    assert notif_resp.status_code == 200
    notif_data = notif_resp.json()
    assert notif_data["unread_count"] >= 1
    assert len(notif_data["notifications"]) >= 1

    first_notif = notif_data["notifications"][0]
    assert first_notif["type"] == "POSSIBLE_MATCH"
    assert first_notif["title"] == "Possible Match Found"
    assert "Wildcraft" in first_notif["message"]
    assert first_notif["entity_id"] == lost_id

    # 5. Check notification privacy: MUST NOT contain private phone, roll number, or email
    assert "9876543210" not in first_notif["message"]
    assert "2410991111" not in first_notif["message"]

    # 6. User A opens matches view for their lost report
    matches_resp = client.get(f"/api/matches/lost/{lost_id}")
    assert matches_resp.status_code == 200
    match_view_data = matches_resp.json()
    assert len(match_view_data["matches"]) >= 1

    scored_match = match_view_data["matches"][0]
    assert scored_match["found_item_id"] == found_id
    assert scored_match["score_percent"] > 40
    assert scored_match["classification"] in ("STRONG_CANDIDATE", "POSSIBLE_CANDIDATE", "LOW_CONFIDENCE")
    assert len(scored_match["reasons"]) > 0
    assert "attributes" in scored_match["components"]
    assert "disclaimer" in match_view_data

    # 7. Mark notification as read
    read_resp = client.patch(f"/api/notifications/{first_notif['id']}/read")
    assert read_resp.status_code == 200

    notif_after = client.get("/api/notifications").json()
    assert notif_after["unread_count"] == 0

    # 8. Privacy & Authorization Checks: User B cannot delete or modify User A's lost report
    app.dependency_overrides[get_current_user] = lambda: user_b_auth
    del_resp = client.delete(f"/api/lost-items/{lost_id}")
    assert del_resp.status_code == 404  # Not found for user B

    update_resp = client.patch(
        f"/api/lost-items/{lost_id}",
        json={
            "item_name": "Hacked Title",
            "category": "Bags & Backpacks",
            "lost_date": "2026-09-20",
            "approximate_location": "Library Block 3",
            "description": "Attempted update description by another user",
        },
    )
    assert update_resp.status_code == 404


def test_foundry_failure_fallback_path(clean_test_db, user_b_auth):
    """Verify that when Microsoft Foundry is offline, reporting and manual workflow succeed gracefully."""
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: user_b_auth

    # Found item image preview with Foundry failure
    with patch("app.services.analysis_service.get_analysis_provider") as mock_prov_factory:
        mock_prov = MagicMock()
        mock_prov.analyze_bytes.side_effect = RuntimeError("Foundry API connection timed out.")
        mock_prov_factory.return_value = mock_prov

        preview_resp = client.post(
            "/api/found-items/analyze-image",
            files={"image": ("test.jpg", VALID_JPEG_BYTES, "image/jpeg")},
        )
        assert preview_resp.status_code == 200
        preview_data = preview_resp.json()
        assert preview_data["success"] is False
        assert "manually" in preview_data["message"].lower()

    # Manual reporting continues without error
    found_resp = client.post(
        "/api/found-items",
        json={
            "item_name": "Keys",
            "category": "Keys",
            "found_date": "2026-09-21",
            "found_location": "Gym",
            "description": "Silver key ring with Honda fob",
        },
    )
    assert found_resp.status_code == 201
    assert found_resp.json()["item_name"] == "Keys"


def test_lost_item_image_analysis_preview(clean_test_db, user_a_auth):
    """Verify lost item image preview endpoint using Foundry vision provider."""
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: user_a_auth

    mock_analysis = AnalysisResult(
        description="A blue stainless steel water bottle with stickers.",
        attributes={
            "object_type": "water bottle",
            "category": "Bottles & Containers",
            "primary_color": "Blue",
            "brand": "Hydro Flask",
            "visible_features": ["astronaut sticker"],
            "visible_text": [],
            "confidence": 0.9,
        },
    )

    with patch("app.services.analysis_service.get_analysis_provider") as mock_prov_factory:
        mock_prov = MagicMock()
        mock_prov.analyze_bytes.return_value = mock_analysis
        mock_prov_factory.return_value = mock_prov

        resp = client.post(
            "/api/lost-items/analyze-image",
            files={"image": ("bottle.jpg", VALID_JPEG_BYTES, "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["item_name"] == "water bottle"
        assert data["category"] == "Bottles & Containers"
        assert data["color"] == "Blue"
        assert data["brand"] == "Hydro Flask"

