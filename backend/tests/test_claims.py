"""Unit and integration tests for Phase 13 Claims & Verification workflow."""

import json

import pytest
from fastapi.testclient import TestClient

from app.auth.firebase import AuthenticatedUser, get_current_user
from app.database import db, repositories
from app.database.claim_schemas import ClaimDecision, ClaimStatus
from app.main import app
from app.services.claim_service import (
    DuplicateClaimError,
    InvalidClaimStateError,
    UnauthorizedClaimActionError,
    admin_override_claim,
    get_claim_detail,
    get_user_claims,
    process_claim_decision,
    request_claim,
)


@pytest.fixture
def claims_db(tmp_path, monkeypatch):
    """Provide a fresh database and test users for claims testing."""
    database_path = tmp_path / "claims_test.db"
    monkeypatch.setattr(db, "get_database_path", lambda: database_path)
    db.initialize_database()

    owner_uid = "owner-uid-1"
    finder_uid = "finder-uid-2"
    other_uid = "unrelated-uid-3"
    admin_uid = "admin-uid-4"

    owner_id = db.ensure_user(owner_uid)
    finder_id = db.ensure_user(finder_uid)
    other_id = db.ensure_user(other_uid)
    admin_id = db.ensure_user(admin_uid)

    # Create a lost item by owner
    lost_id = repositories.create_lost_item(
        owner_id,
        item_name="Blue HP Laptop",
        category="Laptops",
        campus="North Campus",
        lost_at="2026-09-18",
    )

    # Create a found item by finder
    found_id = repositories.create_found_item(
        finder_id,
        item_name="Blue HP Pavilion",
        category="Laptops",
        campus="North Campus",
        found_at="2026-09-19",
    )

    # Create match
    match_id = repositories.create_match(
        found_item_id=found_id,
        lost_item_id=lost_id,
        score=0.91,
        explanation_json=json.dumps({"reasons": ["Same category", "Same campus"]}),
        status="SUGGESTED",
    )

    return {
        "owner_id": owner_id,
        "owner_uid": owner_uid,
        "finder_id": finder_id,
        "finder_uid": finder_uid,
        "other_id": other_id,
        "other_uid": other_uid,
        "admin_id": admin_id,
        "admin_uid": admin_uid,
        "lost_id": lost_id,
        "found_id": found_id,
        "match_id": match_id,
    }


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------

class TestClaimService:
    def test_request_claim_success(self, claims_db):
        owner_id = claims_db["owner_id"]
        match_id = claims_db["match_id"]

        claim = request_claim(
            claimant_user_id=owner_id,
            match_id=match_id,
            verification_notes="Has a scratch under the keyboard and serial ends in 449.",
        )

        assert claim["id"] > 0
        assert claim["match_id"] == match_id
        assert claim["claimant_user_id"] == owner_id
        assert claim["status"] == ClaimStatus.CLAIM_REQUESTED.value
        assert "serial ends in 449" in claim["verification_notes"]

        # Match status transitioned to CLAIMED
        match_record = repositories.get_match(match_id)
        assert match_record["status"] == "CLAIMED"

        # Audit event recorded
        events = repositories.get_audit_events_for_entity("claims", claim["id"])
        assert len(events) >= 1
        assert events[0]["action"] == "CLAIM_REQUESTED"
        assert events[0]["actor_user_id"] == owner_id

    def test_duplicate_claim_prevention(self, claims_db):
        owner_id = claims_db["owner_id"]
        match_id = claims_db["match_id"]

        # First claim succeeds
        request_claim(claimant_user_id=owner_id, match_id=match_id)

        # Duplicate active claim fails
        with pytest.raises(DuplicateClaimError, match="already exists"):
            request_claim(claimant_user_id=owner_id, match_id=match_id)

    def test_unrelated_user_cannot_claim(self, claims_db):
        other_id = claims_db["other_id"]
        match_id = claims_db["match_id"]

        with pytest.raises(UnauthorizedClaimActionError, match="Only the item owner or finder"):
            request_claim(claimant_user_id=other_id, match_id=match_id)

    def test_owner_approves_claim(self, claims_db):
        owner_id = claims_db["owner_id"]
        finder_id = claims_db["finder_id"]
        match_id = claims_db["match_id"]

        # Finder initiates claim
        claim = request_claim(claimant_user_id=finder_id, match_id=match_id)
        claim_id = claim["id"]

        # Owner approves claim
        updated = process_claim_decision(
            claim_id=claim_id,
            user_id=owner_id,
            decision=ClaimDecision.APPROVE,
            notes="Details match my laptop exactly.",
        )

        assert updated["status"] == ClaimStatus.APPROVED.value
        match_rec = repositories.get_match(match_id)
        assert match_rec["status"] == "CLAIMED"

        # Check audit event
        events = repositories.get_audit_events_for_entity("claims", claim_id)
        assert any(e["action"] == "CLAIM_APPROVED" for e in events)

    def test_owner_rejects_claim(self, claims_db):
        owner_id = claims_db["owner_id"]
        finder_id = claims_db["finder_id"]
        match_id = claims_db["match_id"]

        claim = request_claim(claimant_user_id=finder_id, match_id=match_id)
        claim_id = claim["id"]

        # Owner rejects claim
        updated = process_claim_decision(
            claim_id=claim_id,
            user_id=owner_id,
            decision=ClaimDecision.REJECT,
            notes="Serial number does not match.",
        )

        assert updated["status"] == ClaimStatus.REJECTED.value
        match_rec = repositories.get_match(match_id)
        assert match_rec["status"] == "REJECTED"

        events = repositories.get_audit_events_for_entity("claims", claim_id)
        assert any(e["action"] == "CLAIM_REJECTED" for e in events)

    def test_escalate_to_admin_review(self, claims_db):
        owner_id = claims_db["owner_id"]
        match_id = claims_db["match_id"]

        claim = request_claim(claimant_user_id=owner_id, match_id=match_id)
        claim_id = claim["id"]

        # Escalate
        updated = process_claim_decision(
            claim_id=claim_id,
            user_id=owner_id,
            decision=ClaimDecision.ESCALATE,
            notes="Disputed serial number, requesting admin mediation.",
        )

        assert updated["status"] == ClaimStatus.ADMIN_REVIEW.value
        events = repositories.get_audit_events_for_entity("claims", claim_id)
        assert any(e["action"] == "CLAIM_ESCALATED_ADMIN_REVIEW" for e in events)

    def test_admin_override(self, claims_db):
        owner_id = claims_db["owner_id"]
        admin_id = claims_db["admin_id"]
        match_id = claims_db["match_id"]

        claim = request_claim(claimant_user_id=owner_id, match_id=match_id)
        claim_id = claim["id"]

        # Admin overrides to APPROVED
        updated = admin_override_claim(
            claim_id=claim_id,
            admin_user_id=admin_id,
            new_status=ClaimStatus.APPROVED,
            admin_notes="Student provided physical receipt matching serial number.",
        )

        assert updated["status"] == ClaimStatus.APPROVED.value
        events = repositories.get_audit_events_for_entity("claims", claim_id)
        assert any(e["action"] == "ADMIN_INTERVENTION" for e in events)

    def test_terminal_state_rejects_further_decisions(self, claims_db):
        owner_id = claims_db["owner_id"]
        match_id = claims_db["match_id"]

        claim = request_claim(claimant_user_id=owner_id, match_id=match_id)
        claim_id = claim["id"]

        # Approve
        process_claim_decision(claim_id=claim_id, user_id=owner_id, decision=ClaimDecision.APPROVE)

        # Attempting to reject already approved claim raises error
        with pytest.raises(InvalidClaimStateError, match="terminal state"):
            process_claim_decision(claim_id=claim_id, user_id=owner_id, decision=ClaimDecision.REJECT)

    def test_get_user_claims_list(self, claims_db):
        owner_id = claims_db["owner_id"]
        finder_id = claims_db["finder_id"]
        other_id = claims_db["other_id"]
        match_id = claims_db["match_id"]

        request_claim(claimant_user_id=owner_id, match_id=match_id)

        owner_claims = get_user_claims(owner_id)
        assert len(owner_claims) == 1
        assert owner_claims[0]["match_id"] == match_id

        finder_claims = get_user_claims(finder_id)
        assert len(finder_claims) == 1

        other_claims = get_user_claims(other_id)
        assert len(other_claims) == 0


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestClaimsAPI:
    def test_create_claim_via_api(self, claims_db):
        owner_uid = claims_db["owner_uid"]
        match_id = claims_db["match_id"]

        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            uid=owner_uid,
            email="owner@university.edu",
            email_verified=True,
        )

        client = TestClient(app)
        resp = client.post(
            "/api/claims",
            json={"match_id": match_id, "verification_notes": "Special sticker on lid."},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["match_id"] == match_id
        assert data["status"] == "CLAIM_REQUESTED"
        claim_id = data["id"]

        # Fetch detail
        detail_resp = client.get(f"/api/claims/{claim_id}")
        assert detail_resp.status_code == 200
        detail_data = detail_resp.json()
        assert detail_data["id"] == claim_id
        assert detail_data["lost_item"]["item_name"] == "Blue HP Laptop"
        assert detail_data["found_item"]["item_name"] == "Blue HP Pavilion"
        assert len(detail_data["audit_history"]) >= 1

        # List claims
        list_resp = client.get("/api/claims/my-claims")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

        # Approve decision
        dec_resp = client.post(
            f"/api/claims/{claim_id}/decision",
            json={"decision": "APPROVE", "notes": "Verified in person."},
        )
        assert dec_resp.status_code == 200
        assert dec_resp.json()["status"] == "APPROVED"

        app.dependency_overrides.clear()

    def test_duplicate_claim_returns_409(self, claims_db):
        owner_uid = claims_db["owner_uid"]
        match_id = claims_db["match_id"]

        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            uid=owner_uid,
            email="owner@university.edu",
            email_verified=True,
        )
        client = TestClient(app)

        # First claim succeeds
        resp1 = client.post("/api/claims", json={"match_id": match_id})
        assert resp1.status_code == 201

        # Duplicate claim returns 409 Conflict
        resp2 = client.post("/api/claims", json={"match_id": match_id})
        assert resp2.status_code == 409
        assert "already exists" in resp2.json()["detail"].lower()

        app.dependency_overrides.clear()

    def test_unauthorized_user_forbidden(self, claims_db):
        other_uid = claims_db["other_uid"]
        owner_uid = claims_db["owner_uid"]
        match_id = claims_db["match_id"]

        # Owner creates claim
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            uid=owner_uid,
            email="owner@university.edu",
            email_verified=True,
        )
        client = TestClient(app)
        c_resp = client.post("/api/claims", json={"match_id": match_id})
        claim_id = c_resp.json()["id"]

        # Unrelated user tries to view claim
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            uid=other_uid,
            email="intruder@university.edu",
            email_verified=True,
        )
        get_resp = client.get(f"/api/claims/{claim_id}")
        assert get_resp.status_code == 403

        # Unrelated user tries to approve claim
        dec_resp = client.post(
            f"/api/claims/{claim_id}/decision",
            json={"decision": "APPROVE"},
        )
        assert dec_resp.status_code == 403

        app.dependency_overrides.clear()
