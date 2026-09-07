from app.core.security import hash_password
from app.models.user import User, UserRole

RATE_ITEM_FIELDS = {
    "category": "MS structure",
    "item_name": "Steel Rs/kg",
    "unit": "kg",
    "hsn_sac": "7306",
    "rate": 68.0,
}


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _sales_headers(client, db_session):
    user = User(
        name="Test Sales", email="sales@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.SALES
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales@test.local")


def _create_client_record(client, headers, name="Rate History Client"):
    res = client.post("/clients", json={"name": name, "type": "school"}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_project(client, headers, client_id):
    fields = {
        "client_id": client_id, "city": "Mumbai", "site_condition": "level", "soil_type": "normal",
        "building_status": "open_air", "site_access": "good", "power_available": "yes",
        "water_available": True, "package": "standard",
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _draft_cost_sheet(client, headers, client_id=None):
    if client_id is None:
        client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    res = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _add_manual_line(client, headers, cost_sheet_id, rate_item_id, rate):
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={
            "rate_item_id": rate_item_id, "work_package": "civil", "category": "MS structure",
            "item_name": "Steel Rs/kg", "unit": "kg", "quantity": 100, "rate": rate,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def _create_rate_item(client, headers, **overrides):
    payload = {**RATE_ITEM_FIELDS, **overrides}
    res = client.post("/rate-items", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


# ---------------------------------------------------------------------------
# RATE_HISTORY
# ---------------------------------------------------------------------------


def test_creating_a_rate_item_writes_an_opening_history_row(client, director_user):
    headers = _director_headers(client, director_user)
    item_id = _create_rate_item(client, headers)

    history = client.get(f"/rate-items/{item_id}/history", headers=headers).json()
    assert len(history) == 1
    assert history[0]["rate"] == 68.0
    assert history[0]["effective_to"] is None
    assert history[0]["reason"] == "Initial rate"


def test_update_rate_closes_previous_row_and_opens_a_new_one(client, director_user):
    headers = _director_headers(client, director_user)
    item_id = _create_rate_item(client, headers)

    res = client.post(f"/rate-items/{item_id}/rate", json={"rate": 75.0, "reason": "Vendor re-quote"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["rate_item"]["rate"] == 75.0

    history = client.get(f"/rate-items/{item_id}/history", headers=headers).json()
    assert len(history) == 2
    newest, oldest = history[0], history[1]
    assert newest["rate"] == 75.0
    assert newest["effective_to"] is None
    assert newest["reason"] == "Vendor re-quote"
    assert oldest["rate"] == 68.0
    assert oldest["effective_to"] is not None


def test_update_rate_rejects_same_value(client, director_user):
    headers = _director_headers(client, director_user)
    item_id = _create_rate_item(client, headers)

    res = client.post(f"/rate-items/{item_id}/rate", json={"rate": 68.0, "reason": "No change"}, headers=headers)
    assert res.status_code == 422


def test_update_rate_requires_a_reason(client, director_user):
    headers = _director_headers(client, director_user)
    item_id = _create_rate_item(client, headers)

    res = client.post(f"/rate-items/{item_id}/rate", json={"rate": 75.0, "reason": ""}, headers=headers)
    assert res.status_code == 422


def test_update_rate_records_vendor_and_project_context(client, director_user):
    headers = _director_headers(client, director_user)
    item_id = _create_rate_item(client, headers)
    vendor_id = client.post("/vendors", json={"name": "Steel Traders Co"}, headers=headers).json()["id"]
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)

    res = client.post(
        f"/rate-items/{item_id}/rate",
        json={"rate": 80.0, "reason": "Fresh quote", "vendor_id": vendor_id, "project_id": project_id},
        headers=headers,
    )
    assert res.status_code == 200, res.text

    history = client.get(f"/rate-items/{item_id}/history", headers=headers).json()
    assert history[0]["vendor_id"] == vendor_id
    assert history[0]["project_id"] == project_id


def test_update_rate_rejects_unknown_vendor(client, director_user):
    headers = _director_headers(client, director_user)
    item_id = _create_rate_item(client, headers)
    res = client.post(
        f"/rate-items/{item_id}/rate",
        json={"rate": 75.0, "reason": "x", "vendor_id": "00000000-0000-0000-0000-000000000000"},
        headers=headers,
    )
    assert res.status_code == 404


def test_confirming_a_rate_does_not_write_a_history_row(client, director_user):
    """J.1 confirm promotes Manual -> AI; the rate value is unchanged, so
    RATE_HISTORY (which tracks value changes) gets no new row."""
    headers = _director_headers(client, director_user)
    item_id = _create_rate_item(client, headers)
    client.post(f"/rate-items/{item_id}/confirm", headers=headers)

    history = client.get(f"/rate-items/{item_id}/history", headers=headers).json()
    assert len(history) == 1


def test_sales_cannot_read_rate_history(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    item_id = _create_rate_item(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.get(f"/rate-items/{item_id}/history", headers=sales_headers)
    assert res.status_code == 403


def test_history_for_unknown_rate_item_404s(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.get("/rate-items/00000000-0000-0000-0000-000000000000/history", headers=headers)
    assert res.status_code == 404


def test_update_metadata_cannot_change_rate(client, director_user):
    """RateItemUpdate has no `rate` field -- confirms the endpoint split
    that keeps every rate value change funnelled through RATE_HISTORY."""
    headers = _director_headers(client, director_user)
    item_id = _create_rate_item(client, headers)

    res = client.patch(f"/rate-items/{item_id}", json={"rate": 999.0, "category": "Renamed"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["rate"] == 68.0  # unchanged -- unknown field silently ignored
    assert res.json()["category"] == "Renamed"


# ---------------------------------------------------------------------------
# Commodity alert (Part I / Q.1)
# ---------------------------------------------------------------------------


def test_unwatched_item_never_triggers_an_alert(client, director_user):
    headers = _director_headers(client, director_user)
    item_id = _create_rate_item(client, headers)  # is_commodity_watched defaults False

    res = client.post(f"/rate-items/{item_id}/rate", json={"rate": 200.0, "reason": "Big jump"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["commodity_alert"] is None


def test_watched_item_move_under_threshold_does_not_trigger(client, director_user):
    headers = _director_headers(client, director_user)
    item_id = _create_rate_item(client, headers, is_commodity_watched=True)

    # 68 -> 70 is ~2.9%, under the 10% default threshold.
    res = client.post(f"/rate-items/{item_id}/rate", json={"rate": 70.0, "reason": "Minor bump"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["commodity_alert"] is None


def test_watched_item_move_over_threshold_triggers_and_lists_open_cost_sheets(client, director_user):
    headers = _director_headers(client, director_user)
    item_id = _create_rate_item(client, headers, is_commodity_watched=True)

    draft_cs_id = _draft_cost_sheet(client, headers)
    _add_manual_line(client, headers, draft_cs_id, item_id, 68.0)

    # 68 -> 80 is ~17.6%, over the 10% default threshold.
    res = client.post(f"/rate-items/{item_id}/rate", json={"rate": 80.0, "reason": "Steel price spike"}, headers=headers)
    assert res.status_code == 200, res.text
    alert = res.json()["commodity_alert"]
    assert alert is not None
    assert alert["triggered"] is True
    assert alert["previous_rate"] == 68.0
    assert alert["new_rate"] == 80.0
    assert round(alert["percent_move"], 1) == round((80 - 68) / 68 * 100, 1)
    assert alert["threshold_percent"] == 10.0
    assert len(alert["draft_cost_sheets"]) == 1
    assert alert["draft_cost_sheets"][0]["cost_sheet_id"] == draft_cs_id
    assert alert["verified_cost_sheets"] == []


def test_verified_cost_sheets_are_flagged_but_not_eligible_for_sync(client, director_user):
    headers = _director_headers(client, director_user)
    item_id = _create_rate_item(client, headers, is_commodity_watched=True)

    verified_cs_id = _draft_cost_sheet(client, headers)
    _add_manual_line(client, headers, verified_cs_id, item_id, 68.0)
    client.post(f"/cost-sheets/{verified_cs_id}/recompute", headers=headers)
    client.post(f"/cost-sheets/{verified_cs_id}/verify", headers=headers)

    res = client.post(f"/rate-items/{item_id}/rate", json={"rate": 80.0, "reason": "Steel price spike"}, headers=headers)
    alert = res.json()["commodity_alert"]
    assert alert["draft_cost_sheets"] == []
    assert len(alert["verified_cost_sheets"]) == 1
    assert alert["verified_cost_sheets"][0]["cost_sheet_id"] == verified_cs_id
    assert alert["verified_cost_sheets"][0]["status"] == "verified"


def test_superseded_cost_sheets_are_never_flagged(client, director_user):
    headers = _director_headers(client, director_user)
    item_id = _create_rate_item(client, headers, is_commodity_watched=True)

    client_id = _create_client_record(client, headers)
    cost_sheet_id = _draft_cost_sheet(client, headers, client_id)
    _add_manual_line(client, headers, cost_sheet_id, item_id, 68.0)
    client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    # Supersede by revising the cost sheet.
    client.post(f"/cost-sheets/{cost_sheet_id}/revise", json={"cost_total": 100000}, headers=headers)

    res = client.post(f"/rate-items/{item_id}/rate", json={"rate": 80.0, "reason": "Steel price spike"}, headers=headers)
    alert = res.json()["commodity_alert"]
    assert alert["draft_cost_sheets"] == []
    assert alert["verified_cost_sheets"] == []


def test_commodity_alert_threshold_is_configurable(client, director_user):
    headers = _director_headers(client, director_user)
    client.post(
        "/settings", json={"key": "commodity_alert_threshold_percent", "value": "5.0"}, headers=headers
    )
    item_id = _create_rate_item(client, headers, is_commodity_watched=True)

    # 68 -> 72 is ~5.9%, over a 5% threshold but under the 10% default.
    res = client.post(f"/rate-items/{item_id}/rate", json={"rate": 72.0, "reason": "Small bump"}, headers=headers)
    alert = res.json()["commodity_alert"]
    assert alert is not None
    assert alert["threshold_percent"] == 5.0


def test_metadata_update_can_toggle_watch_flag(client, director_user):
    headers = _director_headers(client, director_user)
    item_id = _create_rate_item(client, headers)

    res = client.patch(f"/rate-items/{item_id}", json={"is_commodity_watched": True}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["is_commodity_watched"] is True

    listed = client.get("/rate-items", params={"watched_only": True}, headers=headers).json()
    assert any(i["id"] == item_id for i in listed)


# ---------------------------------------------------------------------------
# Bulk sync (Q.2 rule 5 precedent applied to Cost Sheet lines)
# ---------------------------------------------------------------------------


def test_sync_draft_lines_updates_only_draft_cost_sheets(client, director_user):
    headers = _director_headers(client, director_user)
    item_id = _create_rate_item(client, headers, is_commodity_watched=True)

    draft_cs_id = _draft_cost_sheet(client, headers)
    _add_manual_line(client, headers, draft_cs_id, item_id, 68.0)

    verified_cs_id = _draft_cost_sheet(client, headers)
    _add_manual_line(client, headers, verified_cs_id, item_id, 68.0)
    client.post(f"/cost-sheets/{verified_cs_id}/recompute", headers=headers)
    client.post(f"/cost-sheets/{verified_cs_id}/verify", headers=headers)

    client.post(f"/rate-items/{item_id}/rate", json={"rate": 80.0, "reason": "Spike"}, headers=headers)

    res = client.post(f"/rate-items/{item_id}/sync-draft-lines", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["updated_line_count"] == 1
    assert body["updated_cost_sheet_ids"] == [draft_cs_id]

    draft_lines = client.get(f"/cost-sheets/{draft_cs_id}/lines", headers=headers).json()
    assert draft_lines[0]["rate"] == 80.0

    verified_lines = client.get(f"/cost-sheets/{verified_cs_id}/lines", headers=headers).json()
    assert verified_lines[0]["rate"] == 68.0  # frozen, M.2 rule 5


def test_sales_cannot_sync_draft_lines(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    item_id = _create_rate_item(client, director_headers, is_commodity_watched=True)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(f"/rate-items/{item_id}/sync-draft-lines", headers=sales_headers)
    assert res.status_code == 403
