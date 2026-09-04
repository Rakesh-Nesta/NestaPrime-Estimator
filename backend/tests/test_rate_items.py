from datetime import UTC, datetime, timedelta

from app.models.rate_item import RateItem, RateSource


def _login(client, director_user):
    res = client.post(
        "/auth/login",
        data={"username": "director@test.local", "password": "TestPass!1"},
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


RATE_ITEM_FIELDS = {
    "category": "MS structure",
    "item_name": "SHS 3x3 x 2.5mm",
    "unit": "kg",
    "hsn_sac": "7306",
    "rate": 68.0,
}


def test_labour_categories_lists_all_nine_with_defaults(client, director_user):
    headers = _login(client, director_user)
    res = client.get("/labour-categories", headers=headers)
    assert res.status_code == 200
    categories = res.json()
    assert len(categories) == 9
    blended = next(c for c in categories if c["key"] == "blended_fallback")
    assert blended["default_percent"] == 22.0


def test_new_rate_item_starts_manual_and_unverified(client, director_user):
    """J.1: 'Manual entry -> saved as Unverified (grey). Unverified rates
    never become defaults.'"""
    headers = _login(client, director_user)
    res = client.post("/rate-items", json=RATE_ITEM_FIELDS, headers=headers)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["source"] == "manual"
    assert body["verified"] is False
    assert body["confirmed_date"] is None
    assert body["is_stale"] is False


def test_confirming_a_rate_item_promotes_it_to_ai(client, director_user):
    """J.1: 'PM or Director confirms -> becomes AI rate.'"""
    headers = _login(client, director_user)
    create_res = client.post("/rate-items", json=RATE_ITEM_FIELDS, headers=headers)
    item_id = create_res.json()["id"]

    confirm_res = client.post(f"/rate-items/{item_id}/confirm", headers=headers)
    assert confirm_res.status_code == 200, confirm_res.text
    body = confirm_res.json()
    assert body["source"] == "ai"
    assert body["verified"] is True
    assert body["confirmed_date"] is not None


def test_confirming_an_already_confirmed_rate_item_is_rejected(client, director_user):
    headers = _login(client, director_user)
    create_res = client.post("/rate-items", json=RATE_ITEM_FIELDS, headers=headers)
    item_id = create_res.json()["id"]
    client.post(f"/rate-items/{item_id}/confirm", headers=headers)

    res = client.post(f"/rate-items/{item_id}/confirm", headers=headers)
    assert res.status_code == 400


def test_ai_rate_older_than_ninety_days_is_flagged_stale(client, director_user, db_session):
    """J.1: 'Stale flag after 90 days.'"""
    headers = _login(client, director_user)
    create_res = client.post("/rate-items", json=RATE_ITEM_FIELDS, headers=headers)
    item_id = create_res.json()["id"]
    client.post(f"/rate-items/{item_id}/confirm", headers=headers)

    # Back-date confirmed_date past the 90-day window -- only reachable by
    # touching the DB directly, since the API always confirms as "today".
    row = db_session.query(RateItem).filter(RateItem.id == item_id).first()
    row.confirmed_date = (datetime.now(UTC) - timedelta(days=91)).date()
    db_session.commit()

    res = client.get("/rate-items", headers=headers)
    stale_item = next(i for i in res.json() if i["id"] == item_id)
    assert stale_item["is_stale"] is True


def test_manual_rate_within_ninety_days_is_not_stale(client, director_user, db_session):
    headers = _login(client, director_user)
    create_res = client.post("/rate-items", json=RATE_ITEM_FIELDS, headers=headers)
    item_id = create_res.json()["id"]

    res = client.get("/rate-items", headers=headers)
    item = next(i for i in res.json() if i["id"] == item_id)
    assert item["is_stale"] is False


def test_rate_item_carries_labour_category(client, director_user):
    headers = _login(client, director_user)
    categories = client.get("/labour-categories", headers=headers).json()
    turf_category = next(c for c in categories if c["key"] == "turf_laying")

    res = client.post(
        "/rate-items",
        json={**RATE_ITEM_FIELDS, "labour_category_id": turf_category["id"]},
        headers=headers,
    )
    assert res.json()["labour_category_id"] == turf_category["id"]


def test_rate_item_with_unknown_labour_category_is_rejected(client, director_user):
    headers = _login(client, director_user)
    res = client.post(
        "/rate-items",
        json={**RATE_ITEM_FIELDS, "labour_category_id": "00000000-0000-0000-0000-000000000000"},
        headers=headers,
    )
    assert res.status_code == 404


def test_rate_items_require_auth(client):
    res = client.get("/rate-items")
    assert res.status_code == 401


def test_sales_role_cannot_read_rate_items(client, db_session):
    """Rates are cost-side, internal-only data -- Sales never sees them."""
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    sales_user = User(
        name="Test Sales",
        email="sales@test.local",
        hashed_password=hash_password("TestPass!1"),
        role=UserRole.SALES,
    )
    db_session.add(sales_user)
    db_session.commit()

    login_res = client.post(
        "/auth/login", data={"username": "sales@test.local", "password": "TestPass!1"}
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    res = client.get("/rate-items", headers=headers)
    assert res.status_code == 403
