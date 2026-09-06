from datetime import date, timedelta

from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _pm_headers(client, db_session):
    user = User(name="Test PM", email="pm@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.PM)
    db_session.add(user)
    db_session.commit()
    return _login(client, "pm@test.local")


def _sales_headers(client, db_session):
    user = User(
        name="Test Sales", email="sales@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.SALES
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales@test.local")


def test_director_can_create_a_setting_pm_cannot(client, director_user, db_session):
    """Q.2 rule 6: Master Settings screen is Director-only, PM read-only."""
    director_headers = _director_headers(client, director_user)
    pm_headers = _pm_headers(client, db_session)

    pm_attempt = client.post(
        "/settings", json={"key": "gst_rate_percent", "value": "20.0"}, headers=pm_headers
    )
    assert pm_attempt.status_code == 403

    director_res = client.post(
        "/settings", json={"key": "gst_rate_percent", "value": "20.0", "reason": "test"}, headers=director_headers
    )
    assert director_res.status_code == 201, director_res.text
    assert director_res.json()["value"] == "20.0"


def test_pm_can_read_settings(client, db_session):
    pm_headers = _pm_headers(client, db_session)
    res = client.get("/settings", headers=pm_headers)
    assert res.status_code == 200


def test_sales_cannot_read_settings(client, db_session):
    sales_headers = _sales_headers(client, db_session)
    res = client.get("/settings", headers=sales_headers)
    assert res.status_code == 403


def test_editing_a_setting_creates_a_new_version_not_a_mutation(client, director_user):
    """Q.2 rule 1: 'editing' inserts a new row; history stays queryable."""
    headers = _director_headers(client, director_user)
    client.post("/settings", json={"key": "test_key", "value": "10", "reason": "v1"}, headers=headers)
    client.post("/settings", json={"key": "test_key", "value": "20", "reason": "v2"}, headers=headers)

    history = client.get("/settings/test_key/history", headers=headers).json()
    assert len(history) == 2
    assert {h["value"] for h in history} == {"10", "20"}

    current = next(s for s in client.get("/settings", headers=headers).json() if s["key"] == "test_key")
    assert current["value"] == "20"  # most recent by effective_from/created_at wins


def test_future_effective_date_does_not_become_current_yet(client, director_user):
    """Q.2 rule 1: a setting has an effective-from date; it isn't 'current'
    until that date arrives."""
    headers = _director_headers(client, director_user)
    client.post(
        "/settings", json={"key": "future_key", "value": "1", "reason": "baseline"}, headers=headers
    )
    future_date = (date.today() + timedelta(days=30)).isoformat()
    client.post(
        "/settings",
        json={"key": "future_key", "value": "2", "effective_from": future_date, "reason": "future change"},
        headers=headers,
    )

    current = next(s for s in client.get("/settings", headers=headers).json() if s["key"] == "future_key")
    assert current["value"] == "1"  # the future version hasn't taken effect yet


def test_bulk_update_applies_percent_change_to_matching_keys(client, director_user):
    """Q.2 rule 5: 'Director can apply a % change to a whole category ...
    with one action and an effective date.'"""
    headers = _director_headers(client, director_user)
    client.post("/settings", json={"key": "steel_ms_pipe", "value": "68"}, headers=headers)
    client.post("/settings", json={"key": "steel_ms_sheet", "value": "50"}, headers=headers)
    client.post("/settings", json={"key": "turf_rate", "value": "500"}, headers=headers)  # not matched

    res = client.post(
        "/settings/bulk-update",
        json={"key_prefix": "steel_", "percent_change": 6.0, "reason": "market movement"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    updated = {s["key"]: s["value"] for s in res.json()}
    assert updated["steel_ms_pipe"] == "72.08"
    assert updated["steel_ms_sheet"] == "53.0"

    turf_current = next(s for s in client.get("/settings", headers=headers).json() if s["key"] == "turf_rate")
    assert turf_current["value"] == "500"  # untouched, different prefix


def test_gst_master_setting_change_actually_changes_computed_pricing(client, director_user):
    """The core proof of Q's principle: 'no rate ... is hard-coded' --
    changing gst_rate_percent in Master Settings changes what /pricing/
    quote actually computes, not just what's displayed somewhere."""
    headers = _director_headers(client, director_user)

    baseline = client.post(
        "/pricing/quote", json={"cost_incl_contingency": 850000, "client_type": "government"}, headers=headers
    ).json()
    assert baseline["gst_rate_percent"] == 18.0
    assert round(baseline["quotation_total"], 2) == 1180000.00

    client.post(
        "/settings",
        json={"key": "gst_rate_percent", "value": "12.0", "reason": "director decision"},
        headers=headers,
    )

    updated = client.post(
        "/pricing/quote", json={"cost_incl_contingency": 850000, "client_type": "government"}, headers=headers
    ).json()
    assert updated["gst_rate_percent"] == 12.0
    assert round(updated["selling_after_discount"], 2) == 1000000.00  # margin math unaffected by GST
    assert round(updated["quotation_total"], 2) == 1120000.00  # 1,000,000 * 1.12


def test_override_is_logged_with_master_and_override_values(client, director_user):
    """Part O OVERRIDES / Q.2 rule 2."""
    headers = _director_headers(client, director_user)
    fake_cost_sheet_id = "00000000-0000-0000-0000-0000000000aa"

    res = client.post(
        "/overrides",
        json={
            "document_type": "cost_sheet",
            "document_id": fake_cost_sheet_id,
            "setting_key": "site_establishment_percent",
            "master_value": "6.0",
            "override_value": "8.0",
            "reason": "remote site, +2% for extra mobilisation",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["master_value"] == "6.0"
    assert body["override_value"] == "8.0"

    list_res = client.get(
        "/overrides",
        params={"document_type": "cost_sheet", "document_id": fake_cost_sheet_id},
        headers=headers,
    )
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1


def test_override_requires_a_reason(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/overrides",
        json={
            "document_type": "estimate",
            "document_id": "00000000-0000-0000-0000-0000000000bb",
            "setting_key": "validity_days",
            "master_value": "15",
            "override_value": "30",
            "reason": "",
        },
        headers=headers,
    )
    assert res.status_code == 422


def test_sales_cannot_create_overrides(client, db_session):
    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        "/overrides",
        json={
            "document_type": "quotation",
            "document_id": "00000000-0000-0000-0000-0000000000cc",
            "setting_key": "discount_limit",
            "master_value": "10",
            "override_value": "15",
            "reason": "client requested",
        },
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_settings_require_auth(client):
    assert client.get("/settings").status_code == 401
    assert client.post("/overrides", json={}).status_code == 401
