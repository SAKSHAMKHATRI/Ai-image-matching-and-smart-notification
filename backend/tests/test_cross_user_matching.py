import pytest
from fastapi.testclient import TestClient

from app.auth.firebase import AuthenticatedUser, get_current_user
from app.database import db, repositories
from app.main import app


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = tmp_path / "cross_user_test.db"
    monkeypatch.setattr(db, "get_database_path", lambda: db_path)
    db.initialize_database()
    return db_path


def set_auth_user(uid: str, email: str):
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid=uid,
        email=email,
        email_verified=True,
    )


def test_cross_user_matching_flow(test_db):
    """Verify that User A's lost item matches User B's found item across user accounts,

    while keeping reports isolated and safe.
    """
    user_a_uid = "user-a-student"
    user_b_uid = "user-b-student"

    user_a_email = "student_a@university.edu"
    user_b_email = "student_b@university.edu"

    user_a_id = db.ensure_user(user_a_uid)
    user_b_id = db.ensure_user(user_b_uid)

    client = TestClient(app)

    # 1. User A creates a lost item report
    set_auth_user(user_a_uid, user_a_email)
    lost_resp = client.post(
        "/api/lost-items",
        json={
            "item_name": "Black Dell XPS 15 Laptop",
            "category": "Electronics",
            "color": "Black",
            "brand": "Dell",
            "approximate_location": "North Campus Computer Science Lab 301",
            "lost_date": "2026-09-20",
            "description": "Dell laptop with high performance stickers on lid.",
            "distinctive_features": "Red power LED sticker.",
            "image_reference": None,
        },
    )
    assert lost_resp.status_code == 201
    lost_id = lost_resp.json()["id"]

    # 2. User B creates a found item report for the same item
    set_auth_user(user_b_uid, user_b_email)
    found_resp = client.post(
        "/api/found-items",
        json={
            "found_date": "2026-09-20",
            "found_location": "Science Hall Floor 3",
            "campus": "North Campus",
            "item_name": "Dell XPS Laptop",
            "category": "Electronics",
            "color": "Black",
            "brand": "Dell",
            "description": "Black laptop left on lab desk with stickers.",
        },
    )
    assert found_resp.status_code == 201
    found_id = found_resp.json()["id"]

    # 3. User B's candidate search retrieves User A's lost item
    set_auth_user(user_b_uid, user_b_email)
    candidate_resp = client.post(
        "/api/matches/search",
        json={"found_item_id": found_id},
    )
    assert candidate_resp.status_code == 200
    candidate_data = candidate_resp.json()
    assert candidate_data["total_candidates"] >= 1
    retrieved_candidate = candidate_data["candidates"][0]
    assert retrieved_candidate["id"] == lost_id
    assert retrieved_candidate["item_name"] == "Black Dell XPS 15 Laptop"
    # Verify no private owner PII in candidate retrieval
    assert "email" not in retrieved_candidate
    assert "phone_number" not in retrieved_candidate
    assert "roll_number" not in retrieved_candidate
    assert "user_id" not in retrieved_candidate

    # 4. User B evaluates matches (Found-side View Matches functionality)
    set_auth_user(user_b_uid, user_b_email)
    eval_resp = client.post(
        "/api/matches/evaluate",
        json={"found_item_id": found_id},
    )
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert eval_data["total_matches"] >= 1
    match_item = eval_data["matches"][0]
    assert match_item["lost_item_id"] == lost_id
    assert match_item["score"] > 0.50
    assert "email" not in match_item
    assert "user_id" not in match_item

    # 5. User A can check matches for their lost item (Lost-owner flow)
    set_auth_user(user_a_uid, user_a_email)
    lost_matches_resp = client.get(f"/api/matches/lost/{lost_id}")
    assert lost_matches_resp.status_code == 200
    lost_matches_data = lost_matches_resp.json()
    assert lost_matches_data["total_matches"] >= 1
    assert lost_matches_data["matches"][0]["found_item_id"] == found_id

    # 6. User B cannot edit or delete User A's lost item
    set_auth_user(user_b_uid, user_b_email)
    patch_resp = client.patch(
        f"/api/lost-items/{lost_id}",
        json={
            "item_name": "Hacked Name",
            "category": "Electronics",
            "color": "Black",
            "brand": "Dell",
            "approximate_location": "North Campus Computer Science Lab 301",
            "lost_date": "2026-09-20",
            "description": "Dell laptop with high performance stickers on lid.",
            "distinctive_features": "Red power LED sticker.",
            "image_reference": None,
        },
    )
    assert patch_resp.status_code == 404

    delete_resp = client.delete(f"/api/lost-items/{lost_id}")
    assert delete_resp.status_code == 404

    # 7. User A cannot edit or delete User B's found item
    set_auth_user(user_a_uid, user_a_email)
    patch_found_resp = client.patch(
        f"/api/found-items/{found_id}",
        json={
            "item_name": "Hacked Found Name",
            "category": "Electronics",
            "found_location": "Science Hall Floor 3",
            "campus": "North Campus",
            "found_date": "2026-09-20",
        },
    )
    assert patch_found_resp.status_code == 404

    delete_found_resp = client.delete(f"/api/found-items/{found_id}")
    assert delete_found_resp.status_code == 404

    # 8. User A's "Your reports" does not include User B's found item
    set_auth_user(user_a_uid, user_a_email)
    user_a_found = client.get("/api/found-items").json()
    assert len(user_a_found) == 0

    # User B's "Your reports" does not include User A's lost item
    set_auth_user(user_b_uid, user_b_email)
    user_b_lost = client.get("/api/lost-items").json()
    assert len(user_b_lost) == 0

    # 9. Public Browse/Search allows discovery with privacy-safe fields
    # User B searches lost items
    set_auth_user(user_b_uid, user_b_email)
    browse_lost_resp = client.get("/api/search/lost-items", params={"query": "Dell XPS"})
    assert browse_lost_resp.status_code == 200
    browse_lost_data = browse_lost_resp.json()
    assert browse_lost_data["total"] == 1
    public_lost = browse_lost_data["items"][0]
    assert public_lost["id"] == lost_id
    assert public_lost["item_name"] == "Black Dell XPS 15 Laptop"
    assert "user_id" not in public_lost
    assert "email" not in public_lost
    assert "roll_number" not in public_lost
    assert "phone_number" not in public_lost

    # User A searches found items
    set_auth_user(user_a_uid, user_a_email)
    browse_found_resp = client.get("/api/search/found-items", params={"query": "Dell"})
    assert browse_found_resp.status_code == 200
    browse_found_data = browse_found_resp.json()
    assert browse_found_data["total"] == 1
    public_found = browse_found_data["items"][0]
    assert public_found["id"] == found_id
    assert "user_id" not in public_found
    assert "reporter_id" not in public_found
    assert "email" not in public_found

    app.dependency_overrides.clear()


def test_automatic_matching_and_lost_owner_retrieval(test_db):
    """Test the automatic matching and lost-owner retrieval workflow:

    - User A creates Lost item.
    - User B creates matching Found item.
    - Matching is automatically evaluated upon creation.
    - User A can retrieve the resulting match from the Lost-owner flow.
    - User A sees deterministic score, explanation factors, and safe item info.
    - User B cannot see User A's private information.
    - Existing Found-side matching remains functional.
    """
    user_a_uid = "owner-student-a"
    user_b_uid = "finder-student-b"
    user_a_email = "owner_a@university.edu"
    user_b_email = "finder_b@university.edu"

    client = TestClient(app)

    # 1. User A creates Lost item report
    set_auth_user(user_a_uid, user_a_email)
    lost_resp = client.post(
        "/api/lost-items",
        json={
            "item_name": "Blue Jansport Backpack",
            "category": "Bags & Backpacks",
            "color": "Navy Blue",
            "brand": "Jansport",
            "campus": "North Campus",
            "approximate_location": "Main Library",
            "lost_date": "2026-09-22",
            "description": "Blue backpack with books and keys.",
            "distinctive_features": "Silver keychain",
        },
    )
    assert lost_resp.status_code == 201
    lost_id = lost_resp.json()["id"]

    # 2. User B creates Found item report (Finder does not need to open View Matches)
    set_auth_user(user_b_uid, user_b_email)
    found_resp = client.post(
        "/api/found-items",
        json={
            "item_name": "Jansport Backpack",
            "category": "Bags & Backpacks",
            "color": "Navy Blue",
            "brand": "Jansport",
            "campus": "North Campus",
            "found_location": "Main Library 1st Floor",
            "found_date": "2026-09-22",
            "description": "Navy backpack found near study tables with keys.",
            "distinctive_features": "Silver keychain",
        },
    )
    assert found_resp.status_code == 201
    found_id = found_resp.json()["id"]

    # 3. User A (Lost Owner) retrieves matches automatically
    set_auth_user(user_a_uid, user_a_email)
    owner_matches_resp = client.get(f"/api/matches/lost/{lost_id}")
    assert owner_matches_resp.status_code == 200
    owner_matches = owner_matches_resp.json()

    assert owner_matches["total_matches"] >= 1
    match = owner_matches["matches"][0]
    assert match["found_item_id"] == found_id
    assert match["lost_item_id"] == lost_id

    # 4. Verify score, classification, explanation factors & safe public item info
    assert match["score"] > 0.50
    assert "score_percent" in match
    assert "classification" in match
    assert "classification_label" in match
    assert isinstance(match["reasons"], list)
    assert len(match["reasons"]) > 0
    assert "components" in match
    assert "attributes" in match["components"]
    assert match["item_name"] == "Jansport Backpack"
    assert match["category"] == "Bags & Backpacks"
    assert match["color"] == "Navy Blue"
    assert match["campus"] == "North Campus"

    # Privacy verification: no user_id, phone, email, or roll_number
    assert "email" not in match
    assert "phone" not in match
    assert "phone_number" not in match
    assert "roll_number" not in match
    assert "user_id" not in match

    # 5. User B (Finder) cannot see User A's private data via found-side matching
    set_auth_user(user_b_uid, user_b_email)
    finder_matches_resp = client.get(f"/api/matches/found/{found_id}")
    assert finder_matches_resp.status_code == 200
    finder_matches = finder_matches_resp.json()
    assert finder_matches["total_matches"] >= 1
    finder_match = finder_matches["matches"][0]
    assert finder_match["lost_item_id"] == lost_id
    assert "email" not in finder_match
    assert "phone_number" not in finder_match
    assert "roll_number" not in finder_match
    assert "user_id" not in finder_match

    # 6. Verify disclaimer is present
    assert "disclaimer" in owner_matches
    assert "disclaimer" in finder_matches

    app.dependency_overrides.clear()
