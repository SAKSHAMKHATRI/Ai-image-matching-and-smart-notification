"""Unit and integration tests for Phase 14 Item Return, Lifecycle Closure, and Handover Logging."""

import json

import pytest
from fastapi.testclient import TestClient

from app.auth.firebase import AuthenticatedUser, get_current_user
from app.database import db, repositories
from app.database.claim_schemas import ClaimDecision, ClaimStatus
from app.main import app
from app.services import candidate_service
from app.services.claim_service import (
    ClaimNotFoundError,
    InvalidClaimStateError,
    UnauthorizedClaimActionError,
    admin_override_claim,
    get_claim_detail,
    process_claim_decision,
    process_item_return,
    request_claim,
)


@pytest.fixture
def return_test_db(tmp_path, monkeypatch):
    """Provide a fresh database with lost, found, match, and approved claim records."""
    database_path = tmp_path / "return_closure_test.db"
    monkeypatch.setattr(db, "get_database_path", lambda: database_path)
    db.initialize_database()

    owner_uid = "owner-uid-101"
    finder_uid = "finder-uid-202"
    other_uid = "unrelated-uid-303"
    admin_uid = "admin-uid-404"

    owner_id = db.ensure_user(owner_uid)
    finder_id = db.ensure_user(finder_uid)
    other_id = db.ensure_user(other_uid)
    admin_id = db.ensure_user(admin_uid)

    # 1. Lost item created by owner
    lost_id = repositories.create_lost_item(
        owner_id,
        item_name="Sony WH-1000XM4 Headphones",
        category="Electronics",
        campus="South Campus",
        lost_at="2026-09-15",
        location="Library 2nd Floor",
    )

    # 2. Found item created by finder
    found_id = repositories.create_found_item(
        finder_id,
        item_name="Black Sony Headphones",
        category="Electronics",
        campus="South Campus",
        found_at="2026-09-16",
        location="Library 2nd Floor",
    )

    # 3. Match record
    match_id = repositories.create_match(
        found_item_id=found_id,
        lost_item_id=lost_id,
        score=0.94,
        explanation_json=json.dumps({"reasons": ["Category match", "Campus match", "Location match"]}),
        status="SUGGESTED",
    )

    # 4. Initiate claim
    claim_record = request_claim(
        claimant_user_id=owner_id,
        match_id=match_id,
        verification_notes="Has a small sticker on the right ear cup.",
    )
    claim_id = claim_record["id"]

    # 5. Approve claim
    approved_claim = process_claim_decision(
        claim_id=claim_id,
        user_id=finder_id,
        decision=ClaimDecision.APPROVE,
        notes="Sticker on right ear cup verified.",
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
        "claim_id": claim_id,
        "claim": approved_claim,
    }


class TestReturnClosureService:
    def test_process_return_by_lost_owner_success(self, return_test_db):
        claim_id = return_test_db["claim_id"]
        owner_id = return_test_db["owner_id"]
        lost_id = return_test_db["lost_id"]
        found_id = return_test_db["found_id"]
        match_id = return_test_db["match_id"]

        result = process_item_return(
            claim_id=claim_id,
            user_id=owner_id,
            handover_notes="Received headphones from finder at South Campus Security Desk.",
            handover_location="South Campus Security Desk",
        )

        assert result["status"] == "RETURNED"
        assert result["can_return"] is False

        # Verify database records updated transactionally
        lost_item = repositories.get_lost_item(lost_id)
        assert lost_item["status"] == "RETURNED"

        found_item = repositories.get_found_item(found_id)
        assert found_item["status"] == "RETURNED"

        match_record = repositories.get_match(match_id)
        assert match_record["status"] == "CLAIMED"

        # Verify structured audit events
        claim_audits = repositories.get_audit_events_for_entity("claims", claim_id)
        assert any(a["action"] == "ITEM_RETURNED" for a in claim_audits)

        lost_audits = repositories.get_audit_events_for_entity("lost_items", lost_id)
        assert any(a["action"] == "STATUS_CHANGED_RETURNED" for a in lost_audits)

        found_audits = repositories.get_audit_events_for_entity("found_items", found_id)
        assert any(a["action"] == "STATUS_CHANGED_RETURNED" for a in found_audits)

    def test_process_return_by_finder_success(self, return_test_db):
        claim_id = return_test_db["claim_id"]
        finder_id = return_test_db["finder_id"]

        result = process_item_return(
            claim_id=claim_id,
            user_id=finder_id,
            handover_notes="Handed over directly to student after verifying student ID.",
        )

        assert result["status"] == "RETURNED"

    def test_process_return_by_admin_success(self, return_test_db):
        claim_id = return_test_db["claim_id"]
        admin_id = return_test_db["admin_id"]

        result = process_item_return(
            claim_id=claim_id,
            user_id=admin_id,
            handover_notes="Administrative handover completed.",
            is_admin=True,
        )

        assert result["status"] == "RETURNED"

    def test_unauthorized_user_cannot_process_return(self, return_test_db):
        claim_id = return_test_db["claim_id"]
        other_id = return_test_db["other_id"]

        with pytest.raises(UnauthorizedClaimActionError, match="Only the item owner, finder, or administrator"):
            process_item_return(
                claim_id=claim_id,
                user_id=other_id,
                handover_notes="Malicious return attempt",
            )

    def test_cannot_return_unapproved_claim(self, return_test_db):
        owner_id = return_test_db["owner_id"]
        finder_id = return_test_db["finder_id"]

        # Create fresh lost + found + match in CLAIM_REQUESTED state
        lost_id = repositories.create_lost_item(owner_id, item_name="Watch")
        found_id = repositories.create_found_item(finder_id, item_name="Watch")
        match_id = repositories.create_match(found_item_id=found_id, lost_item_id=lost_id, score=0.88)
        claim = request_claim(claimant_user_id=owner_id, match_id=match_id)

        with pytest.raises(InvalidClaimStateError, match="The claim must be APPROVED first"):
            process_item_return(claim_id=claim["id"], user_id=owner_id)

    def test_cannot_return_rejected_claim(self, return_test_db):
        owner_id = return_test_db["owner_id"]
        finder_id = return_test_db["finder_id"]

        lost_id = repositories.create_lost_item(owner_id, item_name="Keys")
        found_id = repositories.create_found_item(finder_id, item_name="Keys")
        match_id = repositories.create_match(found_item_id=found_id, lost_item_id=lost_id, score=0.85)
        claim = request_claim(claimant_user_id=owner_id, match_id=match_id)
        process_claim_decision(claim_id=claim["id"], user_id=finder_id, decision=ClaimDecision.REJECT)

        with pytest.raises(InvalidClaimStateError, match="Cannot process return for a rejected claim"):
            process_item_return(claim_id=claim["id"], user_id=owner_id)

    def test_cannot_return_already_returned_claim(self, return_test_db):
        claim_id = return_test_db["claim_id"]
        owner_id = return_test_db["owner_id"]

        process_item_return(claim_id=claim_id, user_id=owner_id)

        with pytest.raises(InvalidClaimStateError, match="has already been marked as RETURNED"):
            process_item_return(claim_id=claim_id, user_id=owner_id)

    def test_closed_returned_claim_cannot_be_reopened_by_students(self, return_test_db):
        claim_id = return_test_db["claim_id"]
        owner_id = return_test_db["owner_id"]
        finder_id = return_test_db["finder_id"]

        process_item_return(claim_id=claim_id, user_id=owner_id)

        with pytest.raises(InvalidClaimStateError, match="terminal state"):
            process_claim_decision(claim_id=claim_id, user_id=finder_id, decision=ClaimDecision.APPROVE)

        with pytest.raises(InvalidClaimStateError, match="terminal state"):
            process_claim_decision(claim_id=claim_id, user_id=finder_id, decision=ClaimDecision.REJECT)

    def test_admin_can_intervene_and_reopen_closed_claim(self, return_test_db):
        claim_id = return_test_db["claim_id"]
        owner_id = return_test_db["owner_id"]
        admin_id = return_test_db["admin_id"]
        lost_id = return_test_db["lost_id"]
        found_id = return_test_db["found_id"]

        process_item_return(claim_id=claim_id, user_id=owner_id)

        # Admin overrides back to ADMIN_REVIEW
        reopened = admin_override_claim(
            claim_id=claim_id,
            admin_user_id=admin_id,
            new_status=ClaimStatus.ADMIN_REVIEW,
            admin_notes="Dispute raised regarding wrong item handover.",
        )

        assert reopened["status"] == "ADMIN_REVIEW"
        lost_item = repositories.get_lost_item(lost_id)
        assert lost_item["status"] == "ACTIVE"
        found_item = repositories.get_found_item(found_id)
        assert found_item["status"] == "REPORTED"

    def test_returned_lost_item_excluded_from_candidate_search(self, return_test_db):
        claim_id = return_test_db["claim_id"]
        owner_id = return_test_db["owner_id"]
        lost_id = return_test_db["lost_id"]
        found_id = return_test_db["found_id"]

        # Before return, candidate search finds it
        candidates_before = candidate_service.retrieve_candidates(
            found_item_id=found_id,
            filters=candidate_service.CandidateFilter(category="Electronics"),
        )
        assert any(c["id"] == lost_id for c in candidates_before["candidates"])

        # Process return
        process_item_return(claim_id=claim_id, user_id=owner_id)

        # After return, candidate search no longer returns it
        candidates_after = candidate_service.retrieve_candidates(
            found_item_id=found_id,
            filters=candidate_service.CandidateFilter(category="Electronics"),
        )
        assert not any(c["id"] == lost_id for c in candidates_after["candidates"])



class TestReturnClosureApi:
    def test_api_return_flow_and_history(self, return_test_db):
        claim_id = return_test_db["claim_id"]
        owner_uid = return_test_db["owner_uid"]

        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            uid=owner_uid,
            email="owner@university.edu",
        )
        client = TestClient(app)

        try:
            # 1. Process return via API
            response = client.post(
                f"/api/claims/{claim_id}/return",
                json={
                    "handover_notes": "Student ID verified. Handed over at student desk.",
                    "handover_location": "Student Desk 3",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == claim_id
            assert data["status"] == "RETURNED"
            assert data["can_return"] is False

            # 2. Query history / audit trail
            history_response = client.get(f"/api/claims/{claim_id}/history")
            assert history_response.status_code == 200
            history_events = history_response.json()
            assert len(history_events) >= 3  # CLAIM_REQUESTED, CLAIM_APPROVED, ITEM_RETURNED
            actions = [e["action"] for e in history_events]
            assert "ITEM_RETURNED" in actions

            # 3. Verify audit alias endpoint
            audit_alias_response = client.get(f"/api/claims/{claim_id}/audit")
            assert audit_alias_response.status_code == 200
            assert len(audit_alias_response.json()) == len(history_events)

        finally:
            app.dependency_overrides.clear()

    def test_api_unauthorized_return_forbidden(self, return_test_db):
        claim_id = return_test_db["claim_id"]
        other_uid = return_test_db["other_uid"]

        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            uid=other_uid,
            email="other@university.edu",
        )
        client = TestClient(app)

        try:
            response = client.post(
                f"/api/claims/{claim_id}/return",
                json={"handover_notes": "Unauthorized attempt"},
            )
            assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()
