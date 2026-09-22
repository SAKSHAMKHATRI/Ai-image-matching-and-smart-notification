"""Tests for Phase 11 — Match Scoring and Thresholds Service."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.database import db, repositories
from app.services.embedding_service import serialize_embedding
from app.services.scoring_service import (
    DEFAULT_POSSIBLE_THRESHOLD,
    DEFAULT_STRONG_THRESHOLD,
    DISCLAIMER_TEXT,
    MatchClassification,
    MatchScoreResult,
    ScoringThresholds,
    ScoringWeights,
    classify_score,
    compute_attribute_similarity,
    compute_date_compatibility,
    compute_image_image_similarity,
    compute_image_text_similarity,
    compute_location_compatibility,
    compute_match_score,
    score_candidates,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def scoring_db(tmp_path, monkeypatch):
    """Provide a fresh temporary database for scoring tests."""
    database_path = tmp_path / "scoring.db"
    monkeypatch.setattr(db, "get_database_path", lambda: database_path)
    db.initialize_database()
    user_id = db.ensure_user("scoring-test-uid")
    return {"user_id": user_id}


# Helper vectors for testing (3-dimensional normalized)
VEC_A = [1.0, 0.0, 0.0]
VEC_B = [1.0, 0.0, 0.0]        # Cosine sim with VEC_A = 1.0
VEC_ORTHO = [0.0, 1.0, 0.0]    # Cosine sim with VEC_A = 0.0
VEC_PARTIAL = [0.7071, 0.7071, 0.0]  # Cosine sim with VEC_A ~ 0.7071


# ---------------------------------------------------------------------------
# Thresholds and Classification Tests
# ---------------------------------------------------------------------------

class TestThresholdsAndClassification:
    def test_default_threshold_constants(self):
        assert DEFAULT_STRONG_THRESHOLD == 0.85
        assert DEFAULT_POSSIBLE_THRESHOLD == 0.70

    def test_classification_strong_candidate(self):
        cls, label = classify_score(0.85)
        assert cls == MatchClassification.STRONG_CANDIDATE
        assert label == "Strong candidate"

        cls, _ = classify_score(0.95)
        assert cls == MatchClassification.STRONG_CANDIDATE

    def test_classification_possible_candidate(self):
        cls, label = classify_score(0.70)
        assert cls == MatchClassification.POSSIBLE_CANDIDATE
        assert label == "Possible candidate"

        cls, _ = classify_score(0.8499)
        assert cls == MatchClassification.POSSIBLE_CANDIDATE

    def test_classification_low_confidence(self):
        cls, label = classify_score(0.6999)
        assert cls == MatchClassification.LOW_CONFIDENCE
        assert label == "Low confidence"

        cls, _ = classify_score(0.20)
        assert cls == MatchClassification.LOW_CONFIDENCE

    def test_custom_thresholds(self):
        custom = ScoringThresholds(strong_threshold=0.90, possible_threshold=0.60)
        cls, _ = classify_score(0.88, custom)
        assert cls == MatchClassification.POSSIBLE_CANDIDATE

        cls, _ = classify_score(0.91, custom)
        assert cls == MatchClassification.STRONG_CANDIDATE

        cls, _ = classify_score(0.55, custom)
        assert cls == MatchClassification.LOW_CONFIDENCE

    def test_invalid_thresholds_raise(self):
        with pytest.raises(ValueError):
            ScoringThresholds(strong_threshold=0.60, possible_threshold=0.80)

        with pytest.raises(ValueError):
            ScoringThresholds(strong_threshold=1.5, possible_threshold=0.70)


# ---------------------------------------------------------------------------
# Component Score Tests
# ---------------------------------------------------------------------------

class TestComponentScoring:
    def test_image_text_similarity(self):
        # Deserialized vectors
        sim = compute_image_text_similarity(VEC_A, VEC_B)
        assert sim == pytest.approx(1.0, abs=1e-3)

        # Serialized JSON blobs
        blob_a = serialize_embedding(VEC_A)
        blob_b = serialize_embedding(VEC_PARTIAL)
        sim_blob = compute_image_text_similarity(blob_a, blob_b)
        assert sim_blob == pytest.approx(0.7071, abs=1e-3)

        # Missing input
        assert compute_image_text_similarity(None, blob_a) == 0.0
        assert compute_image_text_similarity(blob_a, "") == 0.0

    def test_image_image_similarity(self):
        blob_a = serialize_embedding(VEC_A)
        blob_ortho = serialize_embedding(VEC_ORTHO)
        assert compute_image_image_similarity(blob_a, blob_a) == pytest.approx(1.0, abs=1e-3)
        assert compute_image_image_similarity(blob_a, blob_ortho) == pytest.approx(0.0, abs=1e-3)
        assert compute_image_image_similarity(None, blob_a) == 0.0

    def test_attribute_similarity_identical(self):
        found = {
            "category": "Electronics",
            "brand": "Apple",
            "color": "Midnight Blue",
            "distinctive_features": "Scratched Apple logo on back",
        }
        lost = {
            "category": "Electronics",
            "brand": "Apple",
            "color": "Blue",
            "distinctive_features": "Scratched logo on bottom",
        }
        score, reasons = compute_attribute_similarity(found, lost)
        assert score == pytest.approx(1.0, abs=1e-2)
        assert any("Same category" in r for r in reasons)
        assert any("Brand appears consistent" in r for r in reasons)
        assert any("Matching color" in r for r in reasons)

    def test_attribute_similarity_mismatched(self):
        found = {"category": "Electronics", "brand": "Apple", "color": "Blue"}
        lost = {"category": "Books", "brand": "Penguin", "color": "Yellow"}
        score, reasons = compute_attribute_similarity(found, lost)
        assert score == pytest.approx(0.0, abs=1e-2)
        assert len(reasons) == 0

    def test_attribute_similarity_partial(self):
        found = {"category": "Electronics", "brand": None, "color": "Black"}
        lost = {"category": "Electronics", "brand": "Sony", "color": "White"}
        score, reasons = compute_attribute_similarity(found, lost)
        assert 0.0 < score < 1.0

    def test_attribute_similarity_compound_category(self):
        found = {"category": "Bags & Wallets", "brand": "HRX", "color": "black"}
        lost = {"category": "Bags & Backpacks", "brand": None, "color": "black"}
        score, reasons = compute_attribute_similarity(found, lost)
        assert score > 0.8
        assert any("Same category" in r for r in reasons)
        assert any("Matching color" in r for r in reasons)

    def test_attribute_similarity_neutral_brand(self):
        found = {"category": "Electronics", "brand": "Apple", "color": "Black"}
        lost = {"category": "Electronics", "brand": "Other", "color": "Black"}
        score, reasons = compute_attribute_similarity(found, lost)
        assert score > 0.7

    def test_location_compatibility_same_campus_and_location(self):
        score, reasons = compute_location_compatibility(
            found_campus="North Campus",
            found_location="Main Library 2nd Floor",
            lost_campus="North Campus",
            lost_location="Library 2nd Floor",
        )
        assert score == pytest.approx(1.0, abs=1e-2)
        assert any("Compatible campus" in r for r in reasons)
        assert any("Compatible specific location" in r for r in reasons)

    def test_location_compatibility_conflicting_campus(self):
        score, reasons = compute_location_compatibility(
            found_campus="North Campus",
            found_location="Library",
            lost_campus="South Campus",
            lost_location="Library",
        )
        assert score == 0.0
        assert len(reasons) == 0

    def test_location_compatibility_unspecified(self):
        score, _ = compute_location_compatibility(None, None, None, None)
        assert score == 0.5

    def test_date_compatibility_close_dates(self):
        score, reasons = compute_date_compatibility("2026-09-20", "2026-09-18")
        assert score == pytest.approx(1.0, abs=1e-2)
        assert any("Found 2 day(s) after" in r for r in reasons)

    def test_date_compatibility_medium_distance(self):
        score, reasons = compute_date_compatibility("2026-09-25", "2026-09-18")
        assert score == pytest.approx(0.90, abs=1e-2)

    def test_date_compatibility_old_distance(self):
        score, _ = compute_date_compatibility("2026-12-01", "2026-08-01")
        assert score == pytest.approx(0.20, abs=1e-2)

    def test_date_compatibility_found_before_lost(self):
        score, reasons = compute_date_compatibility("2026-09-10", "2026-09-20")
        assert score == 0.0
        assert any("precedes" in r for r in reasons)


# ---------------------------------------------------------------------------
# Composite Match Scoring Tests
# ---------------------------------------------------------------------------

class TestComputeMatchScore:
    def test_score_with_lost_image_strong_match(self):
        vec_json = serialize_embedding(VEC_A)
        found_item = {
            "id": 1,
            "category": "Laptops",
            "brand": "Lenovo",
            "color": "Black",
            "campus": "Central",
            "location": "Library Study Room 3",
            "found_at": "2026-09-20",
            "image_embedding_blob": vec_json,
        }
        lost_item = {
            "id": 10,
            "category": "Laptops",
            "brand": "Lenovo",
            "color": "Black",
            "campus": "Central",
            "location": "Library Study Room",
            "lost_at": "2026-09-19",
            "description_embedding_blob": vec_json,
            "image_embedding_blob": vec_json,
        }

        result = compute_match_score(found_item, lost_item)
        assert isinstance(result, MatchScoreResult)
        assert result.has_lost_image is True
        assert result.score >= 0.85
        assert result.classification == MatchClassification.STRONG_CANDIDATE
        assert result.classification_label == "Strong candidate"
        assert result.disclaimer == DISCLAIMER_TEXT
        assert len(result.reasons) >= 3

        # Check components breakdown
        assert "image_text" in result.components
        assert "lost_image" in result.components
        assert "attributes" in result.components
        assert "location" in result.components
        assert "date" in result.components

        # Verify 5-component weights sum
        w = ScoringWeights()
        assert result.components["image_text"].weight == w.image_text_with_image
        assert result.components["lost_image"].weight == w.lost_image_with_image

    def test_score_without_lost_image(self):
        vec_json = serialize_embedding(VEC_A)
        found_item = {
            "id": 2,
            "category": "Water Bottles",
            "brand": "Hydro Flask",
            "color": "Green",
            "campus": "Central",
            "location": "Gym",
            "found_at": "2026-09-20",
            "image_embedding_blob": vec_json,
        }
        lost_item = {
            "id": 20,
            "category": "Water Bottles",
            "brand": "Hydro Flask",
            "color": "Green",
            "campus": "Central",
            "location": "Gym",
            "lost_at": "2026-09-19",
            "description_embedding_blob": vec_json,
            "image_embedding_blob": None,  # No lost image
        }

        result = compute_match_score(found_item, lost_item)
        assert result.has_lost_image is False
        assert result.score >= 0.85
        assert "lost_image" not in result.components
        assert "image_text" in result.components

        w = ScoringWeights()
        assert result.components["image_text"].weight == w.image_text_without_image
        assert result.components["attributes"].weight == w.attributes_without_image

    def test_deterministic_scoring(self):
        found_item = {
            "id": 1,
            "category": "Backpacks",
            "brand": "Jansport",
            "color": "Black",
            "found_at": "2026-09-20",
        }
        lost_item = {
            "id": 2,
            "category": "Backpacks",
            "brand": "Jansport",
            "color": "Black",
            "lost_at": "2026-09-19",
        }

        r1 = compute_match_score(found_item, lost_item)
        r2 = compute_match_score(found_item, lost_item)
        assert r1.score == r2.score
        assert r1.reasons == r2.reasons
        assert r1.to_explanation_json() == r2.to_explanation_json()

    def test_to_dict_and_to_explanation_json(self):
        found_item = {"id": 1, "category": "Keys"}
        lost_item = {"id": 2, "category": "Keys"}
        result = compute_match_score(found_item, lost_item)

        d = result.to_dict()
        assert d["found_item_id"] == 1
        assert d["lost_item_id"] == 2
        assert "score" in d
        assert "classification" in d
        assert "disclaimer" in d

        expl_json = result.to_explanation_json()
        parsed = json.loads(expl_json)
        assert "score" in parsed
        assert "classification" in parsed
        assert "reasons" in parsed
        assert "components" in parsed


# ---------------------------------------------------------------------------
# Batch Scoring & Repository Tests
# ---------------------------------------------------------------------------

class TestBatchScoringAndRepositories:
    def test_score_candidates_orders_descending(self):
        found = {
            "id": 1,
            "category": "Electronics",
            "brand": "Apple",
            "color": "Silver",
            "found_at": "2026-09-20",
        }
        candidates = [
            {"id": 101, "category": "Books", "brand": "Penguin"},  # Low
            {"id": 102, "category": "Electronics", "brand": "Apple", "color": "Silver", "lost_at": "2026-09-19"},  # High
            {"id": 103, "category": "Electronics", "brand": "Dell", "color": "Black"},  # Medium
        ]

        scored = score_candidates(found, candidates)
        assert len(scored) == 3
        assert scored[0].lost_item_id == 102
        assert scored[0].score >= scored[1].score >= scored[2].score

    def test_score_candidates_min_score_filter(self):
        vec_json = serialize_embedding(VEC_A)
        found = {
            "id": 1,
            "category": "Electronics",
            "brand": "Apple",
            "image_embedding_blob": vec_json,
        }
        candidates = [
            {"id": 101, "category": "Books"},
            {"id": 102, "category": "Electronics", "brand": "Apple", "description_embedding_blob": vec_json},
        ]
        scored = score_candidates(found, candidates, min_score=0.50)
        assert len(scored) == 1
        assert scored[0].lost_item_id == 102
        assert scored[0].score >= 0.50

    def test_repository_upsert_and_get_matches(self, scoring_db):
        uid = scoring_db["user_id"]
        # Create found and lost items in DB
        found_id = repositories.create_found_item(uid, category="Electronics")
        lost_id_1 = repositories.create_lost_item(uid, category="Electronics", item_name="Phone 1")
        lost_id_2 = repositories.create_lost_item(uid, category="Electronics", item_name="Phone 2")

        # Upsert first match
        match_id_1 = repositories.upsert_match(
            found_item_id=found_id,
            lost_item_id=lost_id_1,
            score=0.92,
            explanation_json=json.dumps({"reasons": ["Same category"]}),
            status="SUGGESTED",
        )
        assert match_id_1 > 0

        # Upsert second match
        match_id_2 = repositories.upsert_match(
            found_item_id=found_id,
            lost_item_id=lost_id_2,
            score=0.75,
            explanation_json=json.dumps({"reasons": ["Compatible date"]}),
            status="SUGGESTED",
        )
        assert match_id_2 > 0

        # Upsert existing match with updated score
        updated_id = repositories.upsert_match(
            found_item_id=found_id,
            lost_item_id=lost_id_1,
            score=0.95,
            explanation_json=json.dumps({"reasons": ["Same category", "Same brand"]}),
            status="SUGGESTED",
        )
        assert updated_id == match_id_1

        # Fetch matches for found item
        matches = repositories.get_matches_for_found_item(found_id)
        assert len(matches) == 2
        # Verify ordered by score DESC
        assert matches[0]["lost_item_id"] == lost_id_1
        assert matches[0]["score"] == 0.95
        assert matches[1]["lost_item_id"] == lost_id_2
        assert matches[1]["score"] == 0.75
