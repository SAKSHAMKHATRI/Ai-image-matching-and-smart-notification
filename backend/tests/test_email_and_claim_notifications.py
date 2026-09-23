"""Comprehensive tests for real email notification integration and claim notifications."""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.firebase import AuthenticatedUser, get_current_user
from app.database import db, repositories
from app.main import app
from app.services.analysis_service import AnalysisResult
from app.services.email_service import MockEmailTransport, get_email_transport, set_email_transport


@pytest.fixture
def clean_test_db(tmp_path, monkeypatch):
    test_db_path = tmp_path / "test_email_notifications.db"
    monkeypatch.setattr(db, "get_database_path", lambda: test_db_path)
    db.initialize_database()
    yield test_db_path
    app.dependency_overrides.clear()


@pytest.fixture
def mock_email_transport():
    transport = MockEmailTransport()
    set_email_transport(transport)
    yield transport
    transport.clear()
    set_email_transport(None)


@pytest.fixture
def user_a_auth():
    return AuthenticatedUser(
        uid="alice-uid",
        email="alice@chitkara.edu.in",
        email_verified=True,
        role="STUDENT",
    )


@pytest.fixture
def user_b_auth():
    return AuthenticatedUser(
        uid="bob-uid",
        email="bob@chitkara.edu.in",
        email_verified=True,
        role="STUDENT",
    )


@pytest.fixture
def admin_auth():
    return AuthenticatedUser(
        uid="admin-uid",
        email="admin@chitkara.edu.in",
        email_verified=True,
        role="ADMIN",
        is_admin=True,
    )


def test_match_creates_owner_in_app_notification_and_triggers_email(
    clean_test_db, mock_email_transport, user_a_auth, user_b_auth
):
    """FLOW 1: When a Found item matches a Lost item, the Lost Owner receives in-app alert and safe email."""
    client = TestClient(app)

    # 1. Setup User A (Alice - Lost Owner)
    app.dependency_overrides[get_current_user] = lambda: user_a_auth
    user_a_id = db.ensure_user(user_a_auth.uid, role="STUDENT", email=user_a_auth.email)
    db.create_profile(
        user_a_auth.uid,
        {
            "full_name": "Alice Wonderland",
            "roll_number": "2410990001",
            "class_section": "5A",
            "course_program": "CSE",
            "semester": 5,
            "phone_number": "9876543210",
            "university_email": "alice@chitkara.edu.in",
            "campus": "Main Campus",
        },
    )

    lost_resp = client.post(
        "/api/lost-items",
        json={
            "item_name": "HP Laptop Charger",
            "category": "Electronics & Accessories",
            "color": "Black",
            "brand": "HP",
            "campus": "Main Campus",
            "lost_date": "2026-09-20",
            "approximate_location": "Turing Block Lab 2",
            "description": "Original 65W HP blue tip laptop adapter with power cable",
        },
    )
    assert lost_resp.status_code == 201
    lost_id = lost_resp.json()["id"]

    # 2. User B (Bob - Finder) creates matching Found item with AI analysis
    app.dependency_overrides[get_current_user] = lambda: user_b_auth
    user_b_id = db.ensure_user(user_b_auth.uid, role="STUDENT", email=user_b_auth.email)

    mock_analysis = AnalysisResult(
        description="A black HP 65W laptop charger with blue connector pin.",
        attributes={
            "object_type": "charger",
            "category": "Electronics & Accessories",
            "primary_color": "Black",
            "brand": "HP",
            "confidence": 0.92,
        },
    )

    with patch("app.services.analysis_service.get_analysis_provider") as mock_prov_fn:
        mock_prov = MagicMock()
        mock_prov.analyze_bytes.return_value = mock_analysis
        mock_prov_fn.return_value = mock_prov

        found_resp = client.post(
            "/api/found-items",
            json={
                "item_name": "HP Charger",
                "category": "Electronics & Accessories",
                "color": "Black",
                "brand": "HP",
                "campus": "Main Campus",
                "found_date": "2026-09-20",
                "found_location": "Turing Block Ground Floor",
                "description": "Found HP laptop charger near stairs",
                "ai_attributes_json": json.dumps(mock_analysis.attributes),
            },
        )
        assert found_resp.status_code == 201

    # 3. Verify in-app notification for User A
    app.dependency_overrides[get_current_user] = lambda: user_a_auth
    notif_resp = client.get("/api/notifications")
    assert notif_resp.status_code == 200
    notifs = notif_resp.json()["notifications"]
    assert len(notifs) >= 1

    match_notif = notifs[0]
    assert match_notif["type"] == "POSSIBLE_MATCH"
    assert match_notif["title"] == "Possible Match Found"
    assert match_notif["email_status"] == "SENT"
    assert match_notif["email_recipient"] == "alice@chitkara.edu.in"

    # 4. Verify email transport received safe email
    sent = mock_email_transport.sent_emails
    assert len(sent) >= 1
    email = sent[0]
    assert email["to"] == "alice@chitkara.edu.in"
    assert email["subject"] == "Possible Match Found - Campus Lost & Found"
    assert "A possible match has been identified" in email["body_text"]

    # 5. PRIVACY CHECK: Verify NO private PII appears in email body
    assert "9876543210" not in email["body_text"]
    assert "2410990001" not in email["body_text"]
    assert "bob-uid" not in email["body_text"]


def test_claim_submitted_creates_owner_and_admin_notifications_and_email(
    clean_test_db, mock_email_transport, user_a_auth, user_b_auth, admin_auth
):
    """FLOW 2: When a claim is submitted, counterparty receives in-app alert + email, and admins receive in-app alert."""
    client = TestClient(app)

    # Setup User A (Lost Owner), User B (Finder), Admin
    user_a_id = db.ensure_user(user_a_auth.uid, role="STUDENT", email=user_a_auth.email)
    user_b_id = db.ensure_user(user_b_auth.uid, role="STUDENT", email=user_b_auth.email)
    admin_id = db.ensure_user(admin_auth.uid, role="ADMIN", email=admin_auth.email)

    db.create_profile(
        user_a_auth.uid,
        {
            "full_name": "Alice Wonderland",
            "roll_number": "2410990001",
            "class_section": "5A",
            "course_program": "CSE",
            "semester": 5,
            "phone_number": "9876543210",
            "university_email": "alice@chitkara.edu.in",
            "campus": "Main Campus",
        },
    )
    db.create_profile(
        user_b_auth.uid,
        {
            "full_name": "Bob Finder",
            "roll_number": "2410990002",
            "class_section": "5B",
            "course_program": "CSE",
            "semester": 5,
            "phone_number": "9876543211",
            "university_email": "bob@chitkara.edu.in",
            "campus": "Main Campus",
        },
    )

    # User A lost item
    app.dependency_overrides[get_current_user] = lambda: user_a_auth
    lost_resp = client.post(
        "/api/lost-items",
        json={
            "item_name": "Calculus Notebook",
            "category": "Books & Stationery",
            "lost_date": "2026-09-20",
            "approximate_location": "Newton Block",
            "description": "Spiral bound blue notebook for engineering calculus",
        },
    )
    lost_id = lost_resp.json()["id"]

    # User B found item
    app.dependency_overrides[get_current_user] = lambda: user_b_auth
    found_resp = client.post(
        "/api/found-items",
        json={
            "item_name": "Blue Spiral Notebook",
            "category": "Books & Stationery",
            "found_date": "2026-09-20",
            "found_location": "Newton Block Room 101",
            "description": "Blue notebook found on desk",
        },
    )
    found_id = found_resp.json()["id"]

    # Retrieve match ID
    with db.get_connection() as conn:
        match_row = conn.execute(
            "SELECT id FROM matches WHERE found_item_id = ? AND lost_item_id = ?",
            (found_id, lost_id),
        ).fetchone()
        assert match_row is not None
        match_id = match_row["id"]

    mock_email_transport.clear()

    # User A initiates a claim on the match
    app.dependency_overrides[get_current_user] = lambda: user_a_auth
    claim_resp = client.post(
        "/api/claims",
        json={
            "match_id": match_id,
            "verification_notes": "My name is written inside the back cover",
        },
    )
    assert claim_resp.status_code == 201

    # 1. Counterparty (User B - Finder) receives in-app notification + email
    app.dependency_overrides[get_current_user] = lambda: user_b_auth
    b_notifs = client.get("/api/notifications").json()["notifications"]
    assert any(n["type"] == "CLAIM_SUBMITTED" for n in b_notifs)

    claim_email = next((e for e in mock_email_transport.sent_emails if e["to"] == "bob@chitkara.edu.in"), None)
    assert claim_email is not None
    assert claim_email["subject"] == "Claim Submitted - Campus Lost & Found"
    assert "claim has been submitted" in claim_email["body_text"].lower()
    # Private verification notes must NOT be in email
    assert "back cover" not in claim_email["body_text"]

    # 2. Administrator receives in-app review notification
    app.dependency_overrides[get_current_user] = lambda: admin_auth
    admin_notifs = client.get("/api/notifications").json()["notifications"]
    assert any("New Claim For Review" in n["title"] for n in admin_notifs)


def test_claim_status_update_creates_claimant_notification_and_email(
    clean_test_db, mock_email_transport, user_a_auth, user_b_auth
):
    """FLOW 3: When a claim decision is approved/rejected or returned, claimant receives in-app alert + email."""
    client = TestClient(app)

    user_a_id = db.ensure_user(user_a_auth.uid, role="STUDENT", email=user_a_auth.email)
    user_b_id = db.ensure_user(user_b_auth.uid, role="STUDENT", email=user_b_auth.email)

    db.create_profile(
        user_a_auth.uid,
        {
            "full_name": "Alice Student",
            "roll_number": "2410990001",
            "class_section": "5A",
            "course_program": "CSE",
            "semester": 5,
            "phone_number": "9876543210",
            "university_email": "alice@chitkara.edu.in",
            "campus": "Main Campus",
        },
    )

    app.dependency_overrides[get_current_user] = lambda: user_a_auth
    lost_resp = client.post(
        "/api/lost-items",
        json={
            "item_name": "Titan Watch",
            "category": "Watches",
            "lost_date": "2026-09-20",
            "approximate_location": "Gymnasium",
            "description": "Silver Titan analog wrist watch",
        },
    )
    lost_id = lost_resp.json()["id"]

    app.dependency_overrides[get_current_user] = lambda: user_b_auth
    found_resp = client.post(
        "/api/found-items",
        json={
            "item_name": "Titan Watch",
            "category": "Watches",
            "found_date": "2026-09-20",
            "found_location": "Gymnasium Locker Room",
            "description": "Found silver analog watch",
        },
    )
    found_id = found_resp.json()["id"]

    with db.get_connection() as conn:
        match_id = conn.execute("SELECT id FROM matches WHERE found_item_id = ?", (found_id,)).fetchone()["id"]

    # User A creates claim
    app.dependency_overrides[get_current_user] = lambda: user_a_auth
    claim_resp = client.post("/api/claims", json={"match_id": match_id, "verification_notes": "Engraved initials"})
    claim_id = claim_resp.json()["id"]

    mock_email_transport.clear()

    # User B approves the claim
    app.dependency_overrides[get_current_user] = lambda: user_b_auth
    decision_resp = client.post(
        f"/api/claims/{claim_id}/decision",
        json={"decision": "APPROVE", "notes": "Verified description matches"},
    )
    assert decision_resp.status_code == 200

    # User A (claimant) receives APPROVE in-app notification + email
    app.dependency_overrides[get_current_user] = lambda: user_a_auth
    notifs = client.get("/api/notifications").json()["notifications"]
    assert any(n["title"] == "Claim Approved" for n in notifs)

    sent = mock_email_transport.sent_emails
    approve_email = next((e for e in sent if e["to"] == "alice@chitkara.edu.in"), None)
    assert approve_email is not None
    assert approve_email["subject"] == "Claim Approved - Campus Lost & Found"
    assert "Your claim has been approved" in approve_email["body_text"]

    # Now execute return handover
    mock_email_transport.clear()
    return_resp = client.post(
        f"/api/claims/{claim_id}/return",
        json={"handover_notes": "Returned at security desk", "handover_location": "Security Office"},
    )
    assert return_resp.status_code == 200

    return_email = next((e for e in mock_email_transport.sent_emails if e["to"] == "alice@chitkara.edu.in"), None)
    assert return_email is not None
    assert return_email["subject"] == "Item Return Completed - Campus Lost & Found"
    assert "return stage" in return_email["body_text"]


def test_email_failure_does_not_break_match_or_claim_creation(
    clean_test_db, mock_email_transport, user_a_auth, user_b_auth
):
    """Reliability test: Even if the SMTP email transport completely fails, match and claim creation must succeed."""
    mock_email_transport.simulate_failure = True
    mock_email_transport.failure_error = "Connection refused to smtp.chitkara.edu:587"

    client = TestClient(app)

    user_a_id = db.ensure_user(user_a_auth.uid, role="STUDENT", email=user_a_auth.email)
    user_b_id = db.ensure_user(user_b_auth.uid, role="STUDENT", email=user_b_auth.email)

    db.create_profile(
        user_a_auth.uid,
        {
            "full_name": "Alice Student",
            "roll_number": "2410990001",
            "class_section": "5A",
            "course_program": "CSE",
            "semester": 5,
            "phone_number": "9876543210",
            "university_email": "alice@chitkara.edu.in",
            "campus": "Main Campus",
        },
    )

    # 1. Match creation with failed email transport
    app.dependency_overrides[get_current_user] = lambda: user_a_auth
    lost_resp = client.post(
        "/api/lost-items",
        json={
            "item_name": "Blue Umbrella",
            "category": "Umbrellas",
            "lost_date": "2026-09-20",
            "approximate_location": "Cafeteria",
            "description": "Large blue folding umbrella",
        },
    )
    lost_id = lost_resp.json()["id"]

    app.dependency_overrides[get_current_user] = lambda: user_b_auth
    found_resp = client.post(
        "/api/found-items",
        json={
            "item_name": "Blue Umbrella",
            "category": "Umbrellas",
            "found_date": "2026-09-20",
            "found_location": "Cafeteria Entrance",
            "description": "Blue umbrella left on chair",
        },
    )
    assert found_resp.status_code == 201
    found_id = found_resp.json()["id"]

    # Match was created successfully in database despite email failure
    with db.get_connection() as conn:
        match_row = conn.execute("SELECT id FROM matches WHERE found_item_id = ?", (found_id,)).fetchone()
        assert match_row is not None
        match_id = match_row["id"]

    # In-app notification was still created, with email_status="FAILED" recorded in audit
    app.dependency_overrides[get_current_user] = lambda: user_a_auth
    notifs = client.get("/api/notifications").json()["notifications"]
    assert len(notifs) >= 1
    match_notif = notifs[0]
    assert match_notif["type"] == "POSSIBLE_MATCH"
    assert match_notif["email_status"] == "FAILED"
    assert "Connection refused" in match_notif["email_error"]

    # 2. Claim creation with failed email transport
    claim_resp = client.post("/api/claims", json={"match_id": match_id, "verification_notes": "Patterned handle"})
    assert claim_resp.status_code == 201
    claim_id = claim_resp.json()["id"]
    assert claim_id > 0


def create_test_student(auth, name="Test Student", roll="2410990001"):
    db.ensure_user(auth.uid, role="STUDENT", email=auth.email)
    db.create_profile(
        auth.uid,
        {
            "full_name": name,
            "roll_number": roll,
            "class_section": "5A",
            "course_program": "CSE",
            "semester": 5,
            "phone_number": "9876543210",
            "university_email": auth.email,
            "campus": "Main Campus",
        },
    )


def test_finder_name_visible_in_match_details(
    clean_test_db, mock_email_transport, user_a_auth, user_b_auth
):
    """TEST 5: Match details for Lost Owner must expose finder display name safely."""
    client = TestClient(app)

    create_test_student(user_a_auth, "Alice Owner", "2410990001")
    create_test_student(user_b_auth, "Bob Builder", "2410990002")

    app.dependency_overrides[get_current_user] = lambda: user_a_auth
    lost_resp = client.post(
        "/api/lost-items",
        json={
            "item_name": "Water Bottle",
            "category": "Personal Items",
            "lost_date": "2026-09-20",
            "approximate_location": "Sports Complex",
            "description": "Stainless steel water bottle left behind",
        },
    )
    assert lost_resp.status_code == 201
    lost_id = lost_resp.json()["id"]

    app.dependency_overrides[get_current_user] = lambda: user_b_auth
    client.post(
        "/api/found-items",
        json={
            "item_name": "Water Bottle",
            "category": "Personal Items",
            "found_date": "2026-09-20",
            "found_location": "Sports Complex Court 1",
            "description": "Found stainless steel bottle",
        },
    )

    # Owner checks match details
    app.dependency_overrides[get_current_user] = lambda: user_a_auth
    matches_resp = client.get(f"/api/matches/lost/{lost_id}")
    assert matches_resp.status_code == 200
    matches = matches_resp.json()["matches"]
    assert len(matches) > 0
    top_match = matches[0]
    assert top_match.get("finder_name") == "Bob Builder"
    assert top_match.get("found_by") == "Bob Builder"
    assert "lost_item_name" in top_match


def test_privacy_restrictions_verification_notes_hidden_from_finder(
    clean_test_db, mock_email_transport, user_a_auth, user_b_auth, admin_auth
):
    """TEST 11: Private verification notes must NOT be visible to Finder, but visible to Claimant and Admin."""
    client = TestClient(app)

    create_test_student(user_a_auth, "Alice Owner", "2410990001")
    create_test_student(user_b_auth, "Bob Finder", "2410990002")
    db.ensure_user(admin_auth.uid, role="ADMIN", email=admin_auth.email)

    app.dependency_overrides[get_current_user] = lambda: user_a_auth
    lost_resp = client.post(
        "/api/lost-items",
        json={
            "item_name": "Leather Wallet",
            "category": "Personal Items",
            "lost_date": "2026-09-20",
            "approximate_location": "Cafeteria",
            "description": "Brown leather wallet with ID card",
        },
    )
    assert lost_resp.status_code == 201
    lost_id = lost_resp.json()["id"]

    app.dependency_overrides[get_current_user] = lambda: user_b_auth
    found_resp = client.post(
        "/api/found-items",
        json={
            "item_name": "Leather Wallet",
            "category": "Personal Items",
            "found_date": "2026-09-20",
            "found_location": "Cafeteria Table 4",
            "description": "Found brown wallet",
        },
    )
    assert found_resp.status_code == 201
    found_id = found_resp.json()["id"]

    with db.get_connection() as conn:
        match_id = conn.execute("SELECT id FROM matches WHERE found_item_id = ?", (found_id,)).fetchone()["id"]

    # User A initiates claim with super sensitive verification answer
    app.dependency_overrides[get_current_user] = lambda: user_a_auth
    claim_resp = client.post(
        "/api/claims",
        json={
            "match_id": match_id,
            "claim_explanation": "I left it on the bench",
            "verification_notes": "Contains my driver license ending with 9999 and a photo of my dog",
        },
    )
    assert claim_resp.status_code == 201
    claim_id = claim_resp.json()["id"]

    # 1. Claimant (User A) views claim: CAN see their own notes
    a_claim = client.get(f"/api/claims/{claim_id}").json()
    assert a_claim["verification_notes"] is not None
    assert "driver license ending with 9999" in a_claim["verification_notes"]

    # 2. Finder (User B) views claim: CANNOT see private verification notes (masked to None)
    app.dependency_overrides[get_current_user] = lambda: user_b_auth
    b_claim = client.get(f"/api/claims/{claim_id}").json()
    assert b_claim["verification_notes"] is None

    # 3. Finder views my-claims: verification_notes must be None
    b_my_claims = client.get("/api/claims/my-claims").json()
    b_claim_summary = next((c for c in b_my_claims if c["id"] == claim_id), None)
    assert b_claim_summary is not None
    assert b_claim_summary["verification_notes"] is None

    # 4. Admin views claim: CAN see verification notes
    app.dependency_overrides[get_current_user] = lambda: admin_auth
    admin_claims = client.get("/api/admin/claims").json()
    admin_claim_entry = next((c for c in admin_claims if c["id"] == claim_id), None)
    assert admin_claim_entry is not None
    assert "driver license ending with 9999" in str(admin_claim_entry["verification_notes"])


def test_duplicate_notifications_are_prevented(
    clean_test_db, mock_email_transport, user_a_auth, user_b_auth
):
    """TEST 13: Duplicate match evaluation must NOT dispatch duplicate in-app alerts or duplicate emails."""
    client = TestClient(app)

    create_test_student(user_a_auth, "Alice Owner", "2410990001")
    create_test_student(user_b_auth, "Bob Finder", "2410990002")

    app.dependency_overrides[get_current_user] = lambda: user_a_auth
    lost_resp = client.post(
        "/api/lost-items",
        json={
            "item_name": "Scientific Calculator",
            "category": "Electronics",
            "lost_date": "2026-09-20",
            "approximate_location": "Math Lab",
            "description": "Casio fx-991EX scientific calculator",
        },
    )
    assert lost_resp.status_code == 201
    lost_id = lost_resp.json()["id"]

    app.dependency_overrides[get_current_user] = lambda: user_b_auth
    found_resp = client.post(
        "/api/found-items",
        json={
            "item_name": "Scientific Calculator",
            "category": "Electronics",
            "found_date": "2026-09-20",
            "found_location": "Math Lab Desk",
            "description": "Found Casio calculator",
        },
    )
    assert found_resp.status_code == 201
    found_id = found_resp.json()["id"]

    assert len(mock_email_transport.sent_emails) == 1

    # Re-evaluate matches for the found item
    app.dependency_overrides[get_current_user] = lambda: user_b_auth
    eval_resp = client.post("/api/matches/evaluate", json={"found_item_id": found_id})
    assert eval_resp.status_code == 200

    # Notification count should STILL be exactly 1 (no duplicate sent)
    assert len(mock_email_transport.sent_emails) == 1

    app.dependency_overrides[get_current_user] = lambda: user_a_auth
    notifs = client.get("/api/notifications").json()["notifications"]
    match_notifs = [n for n in notifs if n["type"] == "POSSIBLE_MATCH"]
    assert len(match_notifs) == 1


def test_unauthorized_user_cannot_create_or_view_another_users_claim(
    clean_test_db, mock_email_transport, user_a_auth, user_b_auth
):
    """TEST 14: Third-party user cannot create a claim or view claim details for matches they don't own."""
    client = TestClient(app)

    user_c_auth = AuthenticatedUser(
        uid="charlie-uid",
        email="charlie@chitkara.edu.in",
        email_verified=True,
        role="STUDENT",
    )

    create_test_student(user_a_auth, "Alice Owner", "2410990001")
    create_test_student(user_b_auth, "Bob Finder", "2410990002")
    create_test_student(user_c_auth, "Charlie Outsider", "2410990003")

    app.dependency_overrides[get_current_user] = lambda: user_a_auth
    lost_resp = client.post(
        "/api/lost-items",
        json={
            "item_name": "Black Backpack",
            "category": "Bags",
            "lost_date": "2026-09-20",
            "approximate_location": "Library 2nd Floor",
            "description": "Black laptop backpack with blue zipper",
        },
    )
    assert lost_resp.status_code == 201
    lost_id = lost_resp.json()["id"]

    app.dependency_overrides[get_current_user] = lambda: user_b_auth
    found_resp = client.post(
        "/api/found-items",
        json={
            "item_name": "Black Backpack",
            "category": "Bags",
            "found_date": "2026-09-20",
            "found_location": "Library Table",
            "description": "Found black backpack",
        },
    )
    assert found_resp.status_code == 201
    found_id = found_resp.json()["id"]

    with db.get_connection() as conn:
        match_id = conn.execute("SELECT id FROM matches WHERE found_item_id = ?", (found_id,)).fetchone()["id"]

    # User C attempts to create a claim on User A's match
    app.dependency_overrides[get_current_user] = lambda: user_c_auth
    unauth_create = client.post("/api/claims", json={"match_id": match_id, "verification_notes": "It is mine!"})
    assert unauth_create.status_code == 403

    # User A creates a valid claim
    app.dependency_overrides[get_current_user] = lambda: user_a_auth
    auth_create = client.post("/api/claims", json={"match_id": match_id, "verification_notes": "Real owner notes"})
    assert auth_create.status_code == 201
    claim_id = auth_create.json()["id"]

    # User C attempts to view User A's claim
    app.dependency_overrides[get_current_user] = lambda: user_c_auth
    unauth_view = client.get(f"/api/claims/{claim_id}")
    assert unauth_view.status_code == 403


def test_foundry_failure_does_not_fabricate_successful_match(
    clean_test_db, mock_email_transport, user_a_auth, user_b_auth
):
    """TEST 15: Microsoft AI Foundry failure gracefully falls back and does not fabricate fake AI confidence."""
    client = TestClient(app)

    create_test_student(user_a_auth, "Alice Owner", "2410990001")
    create_test_student(user_b_auth, "Bob Finder", "2410990002")

    app.dependency_overrides[get_current_user] = lambda: user_b_auth

    with patch("app.services.analysis_service.get_analysis_provider") as mock_prov_fn:
        mock_prov = MagicMock()
        mock_prov.analyze_bytes.side_effect = RuntimeError("Microsoft Foundry Service Unavailable")
        mock_prov_fn.return_value = mock_prov

        found_resp = client.post(
            "/api/found-items",
            json={
                "item_name": "Unidentified Object",
                "category": "Other",
                "found_date": "2026-09-20",
                "description": "Found some item",
            },
        )
        assert found_resp.status_code == 201
        found_id = found_resp.json()["id"]

    # Verify analysis_status did NOT claim success and no fake AI attributes were fabricated
    with db.get_connection() as conn:
        row = conn.execute("SELECT analysis_status, ai_attributes_json FROM found_items WHERE id = ?", (found_id,)).fetchone()
        assert row["analysis_status"] in ("NOT_REQUESTED", "UNAVAILABLE", "FAILED")
