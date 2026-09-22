"""Unit and integration tests for Phase 15 Admin Dashboard and Moderation."""

import json

import pytest
from fastapi.testclient import TestClient

from app.auth.firebase import AuthenticatedUser, get_current_user
from app.database import db, repositories
from app.main import app
from app.services.admin_service import (
    get_admin_overview_stats,
    get_all_claims_admin,
    get_all_found_items_admin,
    get_all_lost_items_admin,
    get_all_users_admin,
    get_user_detail_admin,
    moderate_found_item_status,
    moderate_lost_item_status,
    moderate_user_status,
)
from app.services.claim_service import (
    ClaimDecision,
    process_claim_decision,
    request_claim,
)


@pytest.fixture
def admin_test_db(tmp_path, monkeypatch):
    """Provide a fresh database with admin, students, reports, matches, and claims."""
    database_path = tmp_path / "admin_test.db"
    monkeypatch.setattr(db, "get_database_path", lambda: database_path)
    db.initialize_database()

    admin_uid = "admin-uid-999"
    student1_uid = "student1-uid-111"
    student2_uid = "student2-uid-222"

    admin_id = db.ensure_user(admin_uid, role="ADMIN")
    student1_id = db.ensure_user(student1_uid, role="STUDENT")
    student2_id = db.ensure_user(student2_uid, role="STUDENT")

    # Profiles
    db.create_profile(
        admin_uid,
        {
            "full_name": "Admin Officer",
            "roll_number": "ADM-001",
            "class_section": "STAFF",
            "course_program": "Administration",
            "semester": 1,
            "phone_number": "+15550000000",
            "university_email": "admin@university.edu",
            "campus": "Main Campus",
        },
    )
    db.create_profile(
        student1_uid,
        {
            "full_name": "Alice Student",
            "roll_number": "CS-2026-001",
            "class_section": "A1",
            "course_program": "Computer Science",
            "semester": 4,
            "phone_number": "+15551111111",
            "university_email": "alice@university.edu",
            "campus": "North Campus",
        },
    )
    db.create_profile(
        student2_uid,
        {
            "full_name": "Bob Student",
            "roll_number": "EE-2026-002",
            "class_section": "B2",
            "course_program": "Electrical Engineering",
            "semester": 4,
            "phone_number": "+15552222222",
            "university_email": "bob@university.edu",
            "campus": "North Campus",
        },
    )

    # Reports
    lost_id = repositories.create_lost_item(
        student1_id,
        item_name="Spam Report Item",
        category="Electronics",
        campus="North Campus",
        lost_at="2026-09-10",
        description="Suspicious spam report",
    )
    found_id = repositories.create_found_item(
        student2_id,
        item_name="Found iPhone 13",
        category="Electronics",
        campus="North Campus",
        found_at="2026-09-11",
    )

    # Match & Claim escalated to ADMIN_REVIEW
    match_id = repositories.create_match(
        found_item_id=found_id,
        lost_item_id=lost_id,
        score=0.89,
        explanation_json=json.dumps({"reasons": ["Same category", "Same campus"]}),
    )
    claim = request_claim(claimant_user_id=student1_id, match_id=match_id)
    claim_id = claim["id"]
    process_claim_decision(claim_id=claim_id, user_id=student1_id, decision=ClaimDecision.ESCALATE, notes="Dispute on ownership")

    return {
        "admin_id": admin_id,
        "admin_uid": admin_uid,
        "student1_id": student1_id,
        "student1_uid": student1_uid,
        "student2_id": student2_id,
        "student2_uid": student2_uid,
        "lost_id": lost_id,
        "found_id": found_id,
        "match_id": match_id,
        "claim_id": claim_id,
    }


class TestAdminService:
    def test_get_admin_overview_stats(self, admin_test_db):
        stats = get_admin_overview_stats()
        assert stats["total_users"] == 3
        assert stats["active_users"] == 3
        assert stats["suspended_users"] == 0
        assert stats["total_lost_items"] == 1
        assert stats["total_found_items"] == 1
        assert stats["total_claims"] == 1
        assert stats["disputed_claims"] == 1  # in ADMIN_REVIEW

    def test_list_and_detail_users(self, admin_test_db):
        users = get_all_users_admin()
        assert len(users) == 3
        alice = next(u for u in users if u["full_name"] == "Alice Student")
        assert alice["lost_count"] == 1
        assert alice["claim_count"] == 1

        detail = get_user_detail_admin(admin_test_db["student1_id"])
        assert detail["full_name"] == "Alice Student"
        assert len(detail["lost_items"]) == 1
        assert len(detail["claims"]) == 1

    def test_moderate_user_suspension(self, admin_test_db):
        student1_id = admin_test_db["student1_id"]
        admin_id = admin_test_db["admin_id"]

        updated = moderate_user_status(
            user_id=student1_id,
            admin_user_id=admin_id,
            new_status="SUSPENDED",
            reason="Posting spam lost reports",
        )
        assert updated["status"] == "SUSPENDED"

        # Check audit event
        audits = repositories.get_audit_events_for_entity("users", student1_id)
        assert any(a["action"] == "USER_STATUS_MODERATED" for a in audits)

    def test_moderate_lost_and_found_items(self, admin_test_db):
        lost_id = admin_test_db["lost_id"]
        found_id = admin_test_db["found_id"]
        admin_id = admin_test_db["admin_id"]

        mod_lost = moderate_lost_item_status(
            item_id=lost_id,
            admin_user_id=admin_id,
            new_status="CLOSED",
            reason="Confirmed fraudulent spam report",
        )
        assert mod_lost["status"] == "CLOSED"

        mod_found = moderate_found_item_status(
            item_id=found_id,
            admin_user_id=admin_id,
            new_status="CLOSED",
            reason="Duplicate report closed by admin",
        )
        assert mod_found["status"] == "CLOSED"

    def test_list_disputed_claims(self, admin_test_db):
        claims = get_all_claims_admin(status="ADMIN_REVIEW")
        assert len(claims) == 1
        assert claims[0]["id"] == admin_test_db["claim_id"]
        assert claims[0]["status"] == "ADMIN_REVIEW"


class TestAdminApi:
    def test_student_forbidden_from_admin_endpoints(self, admin_test_db):
        student_uid = admin_test_db["student1_uid"]
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            uid=student_uid,
            email="alice@university.edu",
        )
        client = TestClient(app)

        try:
            res_overview = client.get("/api/admin/overview")
            assert res_overview.status_code == 403
            assert "Administrator access required" in res_overview.json()["detail"]

            res_users = client.get("/api/admin/users")
            assert res_users.status_code == 403

            res_claims = client.get("/api/admin/claims")
            assert res_claims.status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_admin_can_access_overview_and_moderate(self, admin_test_db):
        admin_uid = admin_test_db["admin_uid"]
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            uid=admin_uid,
            email="admin@university.edu",
        )
        client = TestClient(app)

        try:
            # 1. Overview
            res_overview = client.get("/api/admin/overview")
            assert res_overview.status_code == 200
            data = res_overview.json()
            assert data["total_users"] == 3

            # 2. List & Detail users
            res_users = client.get("/api/admin/users")
            assert res_users.status_code == 200
            assert len(res_users.json()) == 3

            # 3. Suspend user
            student_id = admin_test_db["student1_id"]
            res_suspend = client.patch(
                f"/api/admin/users/{student_id}/status",
                json={"status": "SUSPENDED", "reason": "Abusive behavior"},
            )
            assert res_suspend.status_code == 200
            assert res_suspend.json()["status"] == "SUSPENDED"

            # 4. Moderate report
            lost_id = admin_test_db["lost_id"]
            res_mod_lost = client.patch(
                f"/api/admin/lost-items/{lost_id}/status",
                json={"status": "CLOSED", "reason": "Spam"},
            )
            assert res_mod_lost.status_code == 200
            assert res_mod_lost.json()["status"] == "CLOSED"

            # 5. List disputes & override claim
            res_disputes = client.get("/api/admin/disputes")
            assert res_disputes.status_code == 200
            assert len(res_disputes.json()) == 1

            claim_id = admin_test_db["claim_id"]
            res_override = client.post(
                f"/api/admin/claims/{claim_id}/override",
                json={"new_status": "APPROVED", "admin_notes": "Admin resolved dispute in claimant favor."},
            )
            assert res_override.status_code == 200
            assert res_override.json()["status"] == "APPROVED"

            # 6. Audit logs
            res_audit = client.get("/api/admin/audit-logs")
            assert res_audit.status_code == 200
            assert len(res_audit.json()) > 0
        finally:
            app.dependency_overrides.clear()
