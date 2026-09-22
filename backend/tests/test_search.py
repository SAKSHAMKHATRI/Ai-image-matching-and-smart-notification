import pytest
from fastapi.testclient import TestClient

from app.auth.firebase import AuthenticatedUser, get_current_user
from app.database import db, repositories
from app.main import app


@pytest.fixture
def search_client(tmp_path, monkeypatch):
    database_path = tmp_path / "search-test.db"
    monkeypatch.setattr(db, "get_database_path", lambda: database_path)
    db.initialize_database()

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="student-searcher-1",
        email="searcher@example.edu",
        email_verified=True,
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_search_endpoints_require_authentication() -> None:
    client = TestClient(app)
    assert client.get("/api/search/found-items").status_code == 401
    assert client.get("/api/search/lost-items").status_code == 401
    assert client.get("/api/search/status").status_code == 401


def test_search_system_status(search_client: TestClient) -> None:
    response = search_client.get("/api/search/status")
    assert response.status_code == 200
    data = response.json()
    assert "ai_available" in data
    assert "manual_search_available" in data
    assert data["manual_search_available"] is True


def test_search_public_found_items(search_client: TestClient) -> None:
    user_id = db.ensure_user("reporter-1")
    
    # Active/analyzed found item
    f1_id = repositories.create_found_item(
        user_id=user_id,
        found_at="2026-09-15",
        location="Student Union Floor 2",
        campus="Main Campus",
        image_reference="found/bottle1.jpg",
        item_name="Hydro Flask Water Bottle",
        category="Bottles & Containers",
        color="Ocean Blue",
        brand="Hydro Flask",
        description="Blue insulated stainless steel water bottle with white lid.",
        distinctive_features="Small mountain sticker on bottom edge.",
        status="ANALYZED",
    )

    # Another found item - Electronics
    f2_id = repositories.create_found_item(
        user_id=user_id,
        found_at="2026-09-18",
        location="Library Study Room 4",
        campus="North Campus",
        image_reference="found/calculator.jpg",
        item_name="TI-84 Plus CE Calculator",
        category="Electronics",
        color="Black",
        brand="Texas Instruments",
        description="Graphing calculator in dark slide cover.",
        distinctive_features="Yellow battery door tape.",
        status="ANALYZED",
    )

    # Inactive / Returned item - Should not appear in public browse
    f3_id = repositories.create_found_item(
        user_id=user_id,
        found_at="2026-09-10",
        location="Gym Locker Room",
        campus="Main Campus",
        image_reference="found/keys.jpg",
        item_name="Dorm keys with lanyard",
        category="Keys & Eyewear",
        color="Silver",
        brand=None,
        description="Set of three brass keys.",
        distinctive_features="Blue university lanyard.",
        status="RETURNED",
    )

    # 1. Search all found items
    res_all = search_client.get("/api/search/found-items")
    assert res_all.status_code == 200
    data_all = res_all.json()
    assert data_all["total"] == 2
    assert len(data_all["items"]) == 2

    # Verify no private owner/reporter fields leaked
    first_item = data_all["items"][0]
    assert "roll_number" not in first_item
    assert "email" not in first_item
    assert "phone_number" not in first_item
    assert "reporter_id" not in first_item

    # 2. Keyword query search
    res_kw = search_client.get("/api/search/found-items", params={"query": "Hydro Flask"})
    assert res_kw.status_code == 200
    data_kw = res_kw.json()
    assert data_kw["total"] == 1
    assert data_kw["items"][0]["item_name"] == "Hydro Flask Water Bottle"
    assert data_kw["filters_applied"]["query"] == "Hydro Flask"

    # 3. Filter by category and campus
    res_filt = search_client.get(
        "/api/search/found-items",
        params={"category": "Electronics", "campus": "North Campus"},
    )
    assert res_filt.status_code == 200
    data_filt = res_filt.json()
    assert data_filt["total"] == 1
    assert data_filt["items"][0]["item_name"] == "TI-84 Plus CE Calculator"

    # 4. Date filtering
    res_date = search_client.get(
        "/api/search/found-items",
        params={"from_date": "2026-09-17", "to_date": "2026-09-20"},
    )
    assert res_date.status_code == 200
    assert res_date.json()["total"] == 1
    assert res_date.json()["items"][0]["id"] == f2_id


def test_search_public_lost_items(search_client: TestClient) -> None:
    user_id = db.ensure_user("owner-1")
    
    l1_id = repositories.create_lost_item(
        user_id=user_id,
        item_name="Sony WH-1000XM4 Headphones",
        category="Electronics",
        color="Black",
        brand="Sony",
        lost_at="2026-09-19",
        location="Engineering Building 3rd Floor",
        campus="South Campus",
        description="Over-ear noise cancelling headphones in black protective case.",
        distinctive_features="Scratch on the right ear cup.",
        image_reference="lost/sony.jpg",
        status="ACTIVE",
    )
    l2_id = repositories.create_lost_item(
        user_id=user_id,
        item_name="Chemistry Textbook 10th Ed",
        category="Books & Stationery",
        color="Green",
        brand=None,
        lost_at="2026-09-14",
        location="Science Lab 102",
        campus="Main Campus",
        description="Hardcover chemistry textbook with highlighted chapters 3 and 4.",
        distinctive_features="Name sticker inside front cover.",
        image_reference=None,
        status="ACTIVE",
    )
    # Inactive / Closed lost item
    l3_id = repositories.create_lost_item(
        user_id=user_id,
        item_name="Umbrella",
        category="Personal Items",
        color="Red",
        brand=None,
        lost_at="2026-09-01",
        location="Dining Hall",
        campus="Main Campus",
        description="Red compact umbrella.",
        distinctive_features=None,
        image_reference=None,
        status="RETURNED",
    )

    # 1. Search all active lost items
    res = search_client.get("/api/search/lost-items")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2

    # Verify no private owner information
    item = data["items"][0]
    assert "owner_id" not in item
    assert "email" not in item
    assert "roll_number" not in item

    # 2. Keyword query
    res_kw = search_client.get("/api/search/lost-items", params={"query": "Sony noise cancelling"})
    assert res_kw.status_code == 200
    assert res_kw.json()["total"] == 1
    assert res_kw.json()["items"][0]["id"] == l1_id

    # 3. Filter by color and category
    res_cat = search_client.get("/api/search/lost-items", params={"color": "Green", "category": "Books & Stationery"})
    assert res_cat.status_code == 200
    assert res_cat.json()["total"] == 1
    assert res_cat.json()["items"][0]["id"] == l2_id
