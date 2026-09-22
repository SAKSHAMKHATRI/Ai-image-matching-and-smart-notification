"""Tests for Phase 10 — Candidate Retrieval Service."""

from datetime import datetime, timedelta, timezone

import pytest

from app.database import db, repositories
from app.services.candidate_service import (
    CandidateFilter,
    auto_filter_from_found_item,
    retrieve_candidates,
)


@pytest.fixture
def candidate_db(tmp_path, monkeypatch):
    """Provide a fresh temporary database for candidate retrieval tests."""
    database_path = tmp_path / "candidate.db"
    monkeypatch.setattr(db, "get_database_path", lambda: database_path)
    db.initialize_database()
    # Create a test user
    user_id = db.ensure_user("candidate-test-uid")
    return {"user_id": user_id}


def _create_lost_item(
    user_id: int,
    item_name: str = "Test Item",
    status: str = "ACTIVE",
    category: str | None = None,
    color: str | None = None,
    campus: str | None = None,
    location: str | None = None,
    brand: str | None = None,
    lost_at: str | None = None,
    description: str | None = None,
) -> int:
    """Insert a lost item into the database."""
    lost_at = lost_at or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fields = {
        "item_name": item_name,
        "category": category,
        "color": color,
        "campus": campus,
        "location": location,
        "brand": brand,
        "lost_at": lost_at,
        "description": description,
    }
    item_id = repositories.create_lost_item(user_id, **fields)
    if status != "ACTIVE":
        repositories.change_status("lost_items", item_id, status)
    return item_id


def _create_found_item(
    user_id: int,
    campus: str | None = None,
    category: str | None = None,
    brand: str | None = None,
    location: str | None = None,
) -> int:
    """Insert a found item into the database."""
    fields = {}
    if campus is not None:
        fields["campus"] = campus
    if category is not None:
        fields["category"] = category
    if brand is not None:
        fields["brand"] = brand
    if location is not None:
        fields["location"] = location
    fields["found_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return repositories.create_found_item(user_id, **fields)


class TestQueryActiveLostItems:
    """Unit tests for repositories.query_active_lost_items."""

    def test_returns_only_active_items(self, candidate_db):
        uid = candidate_db["user_id"]
        _create_lost_item(uid, "Active Item 1", status="ACTIVE")
        _create_lost_item(uid, "Active Item 2", status="ACTIVE")
        _create_lost_item(uid, "Draft Item", status="DRAFT")
        _create_lost_item(uid, "Matched Item", status="MATCHED")
        _create_lost_item(uid, "Returned Item", status="RETURNED")
        _create_lost_item(uid, "Closed Item", status="CLOSED")

        results = repositories.query_active_lost_items()
        names = {r["item_name"] for r in results}
        assert names == {"Active Item 1", "Active Item 2"}

    def test_category_filter(self, candidate_db):
        uid = candidate_db["user_id"]
        _create_lost_item(uid, "Phone", category="Electronics")
        _create_lost_item(uid, "Book", category="Books")
        _create_lost_item(uid, "Charger", category="Electronics")

        results = repositories.query_active_lost_items(category="Electronics")
        names = {r["item_name"] for r in results}
        assert names == {"Phone", "Charger"}

    def test_campus_filter(self, candidate_db):
        uid = candidate_db["user_id"]
        _create_lost_item(uid, "Item A", campus="Main Campus")
        _create_lost_item(uid, "Item B", campus="North Campus")

        results = repositories.query_active_lost_items(campus="Main Campus")
        assert len(results) == 1
        assert results[0]["item_name"] == "Item A"

    def test_location_like_filter(self, candidate_db):
        uid = candidate_db["user_id"]
        _create_lost_item(uid, "Item A", location="Library Building Floor 2")
        _create_lost_item(uid, "Item B", location="Cafeteria")
        _create_lost_item(uid, "Item C", location="Main Library Entrance")

        results = repositories.query_active_lost_items(location_like="Library")
        names = {r["item_name"] for r in results}
        assert names == {"Item A", "Item C"}

    def test_brand_filter(self, candidate_db):
        uid = candidate_db["user_id"]
        _create_lost_item(uid, "Phone 1", brand="Samsung")
        _create_lost_item(uid, "Phone 2", brand="Apple")

        results = repositories.query_active_lost_items(brand="Samsung")
        assert len(results) == 1
        assert results[0]["item_name"] == "Phone 1"

    def test_date_window_filter(self, candidate_db):
        uid = candidate_db["user_id"]
        recent = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        old = (datetime.now(timezone.utc) - timedelta(days=200)).strftime("%Y-%m-%d")
        _create_lost_item(uid, "Recent Item", lost_at=recent)
        _create_lost_item(uid, "Old Item", lost_at=old)

        date_from = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
        results = repositories.query_active_lost_items(date_from=date_from)
        names = {r["item_name"] for r in results}
        assert "Recent Item" in names
        assert "Old Item" not in names

    def test_combined_filters(self, candidate_db):
        uid = candidate_db["user_id"]
        _create_lost_item(uid, "Match", category="Electronics", campus="Main", brand="Samsung")
        _create_lost_item(uid, "Wrong Cat", category="Books", campus="Main", brand="Samsung")
        _create_lost_item(uid, "Wrong Campus", category="Electronics", campus="North", brand="Samsung")

        results = repositories.query_active_lost_items(
            category="Electronics", campus="Main", brand="Samsung"
        )
        assert len(results) == 1
        assert results[0]["item_name"] == "Match"

    def test_limit_cap(self, candidate_db):
        uid = candidate_db["user_id"]
        for i in range(10):
            _create_lost_item(uid, f"Item {i}")

        results = repositories.query_active_lost_items(limit=3)
        assert len(results) == 3

    def test_empty_results(self, candidate_db):
        results = repositories.query_active_lost_items(category="Nonexistent")
        assert results == []

    def test_excludes_embedding_blobs(self, candidate_db):
        uid = candidate_db["user_id"]
        _create_lost_item(uid, "Test Item")

        results = repositories.query_active_lost_items()
        assert len(results) == 1
        assert "description_embedding_blob" not in results[0]
        assert "image_embedding_blob" not in results[0]
        assert "user_id" not in results[0]


class TestCandidateService:
    """Integration tests for candidate_service.retrieve_candidates."""

    def test_retrieve_returns_candidates(self, candidate_db):
        uid = candidate_db["user_id"]
        found_id = _create_found_item(uid, category="Electronics", campus="Main")
        _create_lost_item(uid, "Phone", category="Electronics", campus="Main")
        _create_lost_item(uid, "Book", category="Books", campus="Main")

        result = retrieve_candidates(found_id, CandidateFilter())
        assert result["found_item_id"] == found_id
        assert result["total_candidates"] == 1
        assert result["candidates"][0]["item_name"] == "Phone"

    def test_explicit_filters_override_auto(self, candidate_db):
        uid = candidate_db["user_id"]
        found_id = _create_found_item(uid, category="Electronics")
        _create_lost_item(uid, "Book", category="Books")

        result = retrieve_candidates(found_id, CandidateFilter(category="Books"))
        assert result["total_candidates"] == 1
        assert result["candidates"][0]["item_name"] == "Book"

    def test_invalid_found_item_raises(self, candidate_db):
        with pytest.raises(ValueError, match="does not exist"):
            retrieve_candidates(99999, CandidateFilter())

    def test_privacy_safe_output(self, candidate_db):
        uid = candidate_db["user_id"]
        found_id = _create_found_item(uid)
        _create_lost_item(uid, "Phone", description="My phone")

        result = retrieve_candidates(found_id, CandidateFilter())
        for candidate in result["candidates"]:
            assert "user_id" not in candidate
            assert "description_embedding_blob" not in candidate
            assert "image_embedding_blob" not in candidate
            assert "id" in candidate
            assert "item_name" in candidate
            assert "created_at" in candidate

    def test_filters_applied_recorded(self, candidate_db):
        uid = candidate_db["user_id"]
        found_id = _create_found_item(uid, category="Books", campus="Main")
        _create_lost_item(uid, "Book", category="Books", campus="Main")

        result = retrieve_candidates(found_id, CandidateFilter())
        applied = result["filters_applied"]
        assert applied["status"] == "ACTIVE"
        assert applied["category"] == "Books"
        assert applied["campus"] == "Main"
        assert "date_from" in applied

    def test_date_window_respected(self, candidate_db):
        uid = candidate_db["user_id"]
        found_id = _create_found_item(uid)
        recent = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        old = (datetime.now(timezone.utc) - timedelta(days=200)).strftime("%Y-%m-%d")
        _create_lost_item(uid, "Recent", lost_at=recent)
        _create_lost_item(uid, "Old", lost_at=old)

        result = retrieve_candidates(found_id, CandidateFilter(date_window_days=90))
        names = {c["item_name"] for c in result["candidates"]}
        assert "Recent" in names
        assert "Old" not in names

    def test_max_results_limit(self, candidate_db):
        uid = candidate_db["user_id"]
        found_id = _create_found_item(uid)
        for i in range(10):
            _create_lost_item(uid, f"Item {i}")

        result = retrieve_candidates(found_id, CandidateFilter(max_results=3))
        assert result["total_candidates"] == 3


class TestAutoFilterFromFoundItem:
    """Tests for auto_filter_from_found_item."""

    def test_derives_category_campus_brand(self):
        found_item = {
            "category": "Electronics",
            "campus": "Main Campus",
            "brand": "Samsung",
        }
        f = auto_filter_from_found_item(found_item)
        assert f.category == "Electronics"
        assert f.campus == "Main Campus"
        assert f.brand == "Samsung"

    def test_none_for_missing_fields(self):
        found_item = {"category": None, "campus": "", "brand": None}
        f = auto_filter_from_found_item(found_item)
        assert f.category is None
        assert f.campus is None
        assert f.brand is None

    def test_empty_dict(self):
        f = auto_filter_from_found_item({})
        assert f.category is None
        assert f.campus is None
        assert f.brand is None


@pytest.fixture
def client(tmp_path, monkeypatch):
    database_path = tmp_path / "api_test.db"
    monkeypatch.setattr(db, "get_database_path", lambda: database_path)
    db.initialize_database()

    from app.auth.firebase import AuthenticatedUser, get_current_user
    from app.main import app
    from fastapi.testclient import TestClient

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="api-test-uid",
        email="finder@example.edu",
        email_verified=True,
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestMatchesAPI:
    """API endpoint tests for /api/matches/search."""

    def test_search_requires_authentication(self):
        from app.main import app
        from fastapi.testclient import TestClient

        resp = TestClient(app).post("/api/matches/search", json={"found_item_id": 1})
        assert resp.status_code == 401

    def test_search_not_found_item(self, client):
        resp = client.post("/api/matches/search", json={"found_item_id": 9999})
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_search_success_with_candidates(self, client):
        user_id = db.ensure_user("api-test-uid")
        found_id = _create_found_item(user_id, category="Electronics", campus="North")
        _create_lost_item(user_id, item_name="Lost Phone", category="Electronics", campus="North")
        _create_lost_item(user_id, item_name="Lost Keys", category="Keys", campus="North")

        resp = client.post("/api/matches/search", json={"found_item_id": found_id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["found_item_id"] == found_id
        assert data["total_candidates"] == 1
        assert data["candidates"][0]["item_name"] == "Lost Phone"
        assert "confidence_score" not in data["candidates"][0]
        assert "is_match" not in data["candidates"][0]

    def test_evaluate_matches_endpoint(self, client):
        user_id = db.ensure_user("api-test-uid")
        found_id = _create_found_item(user_id, category="Laptops", campus="Central")
        _create_lost_item(user_id, item_name="Lost Thinkpad", category="Laptops", campus="Central")

        resp = client.post("/api/matches/evaluate", json={"found_item_id": found_id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["found_item_id"] == found_id
        assert data["total_matches"] == 1
        match = data["matches"][0]
        assert match["item_name"] == "Lost Thinkpad"
        assert "score" in match
        assert "score_percent" in match
        assert "classification" in match
        assert "reasons" in match
        assert "disclaimer" in data
        assert "owner_email" not in match
        assert "roll_number" not in match

    def test_get_found_item_matches_endpoint(self, client):
        user_id = db.ensure_user("api-test-uid")
        found_id = _create_found_item(user_id, category="Bags", campus="Central")
        _create_lost_item(user_id, item_name="Lost Bag", category="Bags", campus="Central")

        resp = client.get(f"/api/matches/found/{found_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["found_item_id"] == found_id
        assert data["total_matches"] == 1
        assert data["matches"][0]["item_name"] == "Lost Bag"


class TestMatchingRegressionIssue:
    """Regression tests for lost and found item matching issues."""

    def test_same_bag_candidate_retrieval_and_matching(self, client):
        """A lost bag with missing optional campus/brand must match a found bag with campus/brand."""
        user_id = db.ensure_user("api-test-uid")
        lost_id = _create_lost_item(
            user_id,
            item_name="Black Backpack",
            category="Bags",
            campus=None,  # Lost form didn't capture campus
            brand=None,   # Lost form didn't specify brand
            lost_at="2026-09-20",
            description="Lost my favorite black school bag",
        )
        found_id = _create_found_item(
            user_id,
            category="Bag",
            campus="North Campus",
            brand="Nike",
            location="Library 2nd Floor",
        )

        # 1. Test candidate retrieval via service
        cand_res = retrieve_candidates(found_id, CandidateFilter())
        assert cand_res["total_candidates"] >= 1
        candidate_ids = [c["id"] for c in cand_res["candidates"]]
        assert lost_id in candidate_ids

        # 2. Test candidate search API endpoint
        resp = client.post("/api/matches/search", json={"found_item_id": found_id})
        assert resp.status_code == 200
        data = resp.json()
        assert any(c["id"] == lost_id for c in data["candidates"])

        # 3. Test match evaluation endpoint
        eval_resp = client.post("/api/matches/evaluate", json={"found_item_id": found_id})
        assert eval_resp.status_code == 200
        eval_data = eval_resp.json()
        assert eval_data["total_matches"] >= 1
        assert any(m["id"] == lost_id for m in eval_data["matches"])

    def test_suspicious_future_found_date_handled(self, client):
        """When found date is in the future compared to lost date or current date, candidate is not excluded."""
        user_id = db.ensure_user("api-test-uid")
        lost_id = _create_lost_item(
            user_id,
            item_name="Blue Wallet",
            category="Wallet",
            campus=None,
            brand=None,
            lost_at="2026-09-20",
        )
        # Found item with a future date
        found_id = repositories.create_found_item(
            user_id,
            category="Wallets",
            campus="South Campus",
            found_at="2026-09-30",
        )

        cand_res = retrieve_candidates(found_id, CandidateFilter())
        candidate_ids = [c["id"] for c in cand_res["candidates"]]
        assert lost_id in candidate_ids

        eval_resp = client.post("/api/matches/evaluate", json={"found_item_id": found_id})
        assert eval_resp.status_code == 200
        eval_data = eval_resp.json()
        assert any(m["id"] == lost_id for m in eval_data["matches"])

    def test_case_insensitive_and_plural_category_matching(self, candidate_db):
        """Category matching handles case-insensitivity and plural/singular forms."""
        uid = candidate_db["user_id"]
        _create_lost_item(uid, "Backpack Item", category="backpacks")
        _create_lost_item(uid, "Headphones Item", category="ELECTRONICS")

        # Test query with singular and different case
        res1 = repositories.query_active_lost_items(category="Backpack")
        assert any(r["item_name"] == "Backpack Item" for r in res1)

        res2 = repositories.query_active_lost_items(category="electronics")
        assert any(r["item_name"] == "Headphones Item" for r in res2)

    def test_compound_category_and_brand_matching_regression(self, client):
        """Regression test: Found item with category 'Bags & Wallets' and brand 'HRX'

        correctly matches a lost item with category 'Bags & Backpacks' and brand None,
        returning it in evaluate matches even with low-confidence score.
        """
        user_id = db.ensure_user("api-test-uid")
        lost_id = _create_lost_item(
            user_id,
            item_name="bag",
            category="Bags & Backpacks",
            color="Black",
            brand=None,
            lost_at="2026-09-15",
            location="Main Library",
        )

        found_id = repositories.create_found_item(
            user_id,
            item_name="bag",
            category="Bags & Wallets",
            color="black",
            brand="HRX",
            found_at="2026-09-16",
        )

        # 1. Candidate retrieval
        cand_res = retrieve_candidates(found_id, CandidateFilter())
        assert cand_res["total_candidates"] >= 1
        assert any(c["id"] == lost_id for c in cand_res["candidates"])

        # 2. Evaluation endpoint returns candidate
        eval_resp = client.post("/api/matches/evaluate", json={"found_item_id": found_id})
        assert eval_resp.status_code == 200
        eval_data = eval_resp.json()
        assert eval_data["total_matches"] >= 1
        matched_item = next(m for m in eval_data["matches"] if m["id"] == lost_id)
        assert matched_item["classification"] == "LOW_CONFIDENCE"
        assert matched_item["score"] > 0.0
        assert any("category" in r.lower() for r in matched_item["reasons"])
        assert any("color" in r.lower() for r in matched_item["reasons"])
