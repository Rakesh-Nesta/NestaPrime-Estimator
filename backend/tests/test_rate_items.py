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


# ---------------------------------------------------------------------------
# J.1 "Bulk actions (all AI / all Manual / category)"
# ---------------------------------------------------------------------------


def _sales_headers(client, db_session):
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    user = User(
        name="Test Sales", email="sales-bulk@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.SALES,
    )
    db_session.add(user)
    db_session.commit()
    res = client.post("/auth/login", data={"username": "sales-bulk@test.local", "password": "TestPass!1"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_bulk_mark_all_manual_items_promotes_them_to_ai(client, director_user):
    headers = _login(client, director_user)
    id_a = client.post("/rate-items", json={**RATE_ITEM_FIELDS, "item_name": "A"}, headers=headers).json()["id"]
    id_b = client.post("/rate-items", json={**RATE_ITEM_FIELDS, "item_name": "B"}, headers=headers).json()["id"]

    res = client.post("/rate-items/bulk-mark", json={"source": "ai"}, headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["updated_count"] == 2
    assert set(body["updated_item_ids"]) == {id_a, id_b}

    item_a = client.get("/rate-items", headers=headers).json()
    a = next(i for i in item_a if i["id"] == id_a)
    assert a["source"] == "ai"
    assert a["verified"] is True
    assert a["confirmed_date"] is not None


def test_bulk_mark_all_ai_items_reverts_them_to_manual(client, director_user):
    """The reverse of the confirm flow: un-confirming a batch back to
    Manual clears verified and confirmed_date, same shape as a freshly
    created item."""
    headers = _login(client, director_user)
    item_id = client.post("/rate-items", json=RATE_ITEM_FIELDS, headers=headers).json()["id"]
    client.post(f"/rate-items/{item_id}/confirm", headers=headers)

    res = client.post("/rate-items/bulk-mark", json={"source": "manual"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["updated_count"] == 1

    item = next(i for i in client.get("/rate-items", headers=headers).json() if i["id"] == item_id)
    assert item["source"] == "manual"
    assert item["verified"] is False
    assert item["confirmed_date"] is None


def test_bulk_mark_with_category_only_touches_that_category(client, director_user):
    headers = _login(client, director_user)
    steel_id = client.post(
        "/rate-items", json={**RATE_ITEM_FIELDS, "category": "MS structure", "item_name": "Steel"}, headers=headers
    ).json()["id"]
    turf_id = client.post(
        "/rate-items", json={**RATE_ITEM_FIELDS, "category": "Turf", "item_name": "Turf roll"}, headers=headers
    ).json()["id"]

    res = client.post("/rate-items/bulk-mark", json={"source": "ai", "category": "MS structure"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["updated_count"] == 1
    assert res.json()["updated_item_ids"] == [steel_id]

    turf = next(i for i in client.get("/rate-items", headers=headers).json() if i["id"] == turf_id)
    assert turf["source"] == "manual"


def test_bulk_mark_skips_items_already_at_the_target_source(client, director_user):
    headers = _login(client, director_user)
    already_ai_id = client.post("/rate-items", json=RATE_ITEM_FIELDS, headers=headers).json()["id"]
    client.post(f"/rate-items/{already_ai_id}/confirm", headers=headers)
    still_manual_id = client.post(
        "/rate-items", json={**RATE_ITEM_FIELDS, "item_name": "Other"}, headers=headers
    ).json()["id"]

    res = client.post("/rate-items/bulk-mark", json={"source": "ai"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["updated_count"] == 1
    assert res.json()["updated_item_ids"] == [still_manual_id]


def test_sales_cannot_bulk_mark_rate_items(client, director_user, db_session):
    _login(client, director_user)
    headers = _sales_headers(client, db_session)
    res = client.post("/rate-items/bulk-mark", json={"source": "ai"}, headers=headers)
    assert res.status_code == 403


def test_bulk_rate_update_applies_percent_change_across_the_category(client, director_user):
    headers = _login(client, director_user)
    id_a = client.post(
        "/rate-items", json={**RATE_ITEM_FIELDS, "category": "Steel", "item_name": "A", "rate": 100.0}, headers=headers
    ).json()["id"]
    id_b = client.post(
        "/rate-items", json={**RATE_ITEM_FIELDS, "category": "Steel", "item_name": "B", "rate": 50.0}, headers=headers
    ).json()["id"]
    other_category_id = client.post(
        "/rate-items", json={**RATE_ITEM_FIELDS, "category": "Turf", "item_name": "C", "rate": 200.0}, headers=headers
    ).json()["id"]

    res = client.post(
        "/rate-items/bulk-rate-update",
        json={"category": "Steel", "percent_change": 6.0, "reason": "Steel price rise"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["updated_count"] == 2
    rates_by_id = {i["rate_item"]["id"]: i["rate_item"]["rate"] for i in body["items"]}
    assert rates_by_id[id_a] == 106.0
    assert rates_by_id[id_b] == 53.0

    other = next(i for i in client.get("/rate-items", headers=headers).json() if i["id"] == other_category_id)
    assert other["rate"] == 200.0  # untouched -- different category

    history_a = client.get(f"/rate-items/{id_a}/history", headers=headers).json()
    assert len(history_a) == 2
    assert history_a[0]["rate"] == 106.0
    assert history_a[0]["reason"] == "Steel price rise"
    assert history_a[1]["effective_to"] is not None


def test_bulk_rate_update_skips_zero_rate_items(client, director_user):
    headers = _login(client, director_user)
    zero_id = client.post(
        "/rate-items", json={**RATE_ITEM_FIELDS, "category": "Freebie", "rate": 0.0}, headers=headers
    ).json()["id"]

    res = client.post(
        "/rate-items/bulk-rate-update",
        json={"category": "Freebie", "percent_change": 10.0, "reason": "x"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["updated_count"] == 0

    history = client.get(f"/rate-items/{zero_id}/history", headers=headers).json()
    assert len(history) == 1  # only the opening row -- no bulk row added


def test_bulk_rate_update_unknown_category_404s(client, director_user):
    headers = _login(client, director_user)
    res = client.post(
        "/rate-items/bulk-rate-update",
        json={"category": "Does not exist", "percent_change": 5.0, "reason": "x"},
        headers=headers,
    )
    assert res.status_code == 404


def test_bulk_rate_update_triggers_commodity_alert_for_watched_items(client, director_user):
    headers = _login(client, director_user)
    client.post(
        "/rate-items",
        json={**RATE_ITEM_FIELDS, "category": "Steel", "rate": 68.0, "is_commodity_watched": True},
        headers=headers,
    )

    # 68 -> ~80 is a ~17.6% move, over the 10% default threshold.
    res = client.post(
        "/rate-items/bulk-rate-update",
        json={"category": "Steel", "percent_change": 17.6, "reason": "Steel price spike"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    alert = res.json()["items"][0]["commodity_alert"]
    assert alert is not None
    assert alert["triggered"] is True


def test_sales_cannot_bulk_update_rates(client, director_user, db_session):
    _login(client, director_user)
    headers = _sales_headers(client, db_session)
    res = client.post(
        "/rate-items/bulk-rate-update",
        json={"category": "Steel", "percent_change": 5.0, "reason": "x"},
        headers=headers,
    )
    assert res.status_code == 403
