from app.core.security import hash_password
from app.models.user import User, UserRole


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


def _turn_on_rate_blind_mode(client, headers):
    res = client.post("/settings", json={"key": "rate_blind_mode", "value": "true"}, headers=headers)
    assert res.status_code == 201, res.text


def _create_client_record(client, headers, name="Rate Blind Client"):
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


def _empty_draft_cost_sheet(client, headers, project_id):
    res = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


LINE_FIELDS = {
    "work_package": "civil", "category": "MS structure", "item_name": "Steel Rs/kg", "unit": "kg", "quantity": 100,
}


# ---------------------------------------------------------------------------
# Default off -- unchanged behaviour
# ---------------------------------------------------------------------------


def test_sales_still_gets_403_when_rate_blind_mode_is_off(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _empty_draft_cost_sheet(client, headers, project_id)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/lines", json={**LINE_FIELDS}, headers=sales_headers
    )
    assert res.status_code == 403

    res = client.get(f"/cost-sheets/{cost_sheet_id}/lines", headers=sales_headers)
    assert res.status_code == 403


def test_pm_still_requires_a_rate_regardless_of_mode(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _empty_draft_cost_sheet(client, headers, project_id)

    res = client.post(f"/cost-sheets/{cost_sheet_id}/lines", json={**LINE_FIELDS}, headers=headers)
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# On -- Sales proposes quantities, PM prices them
# ---------------------------------------------------------------------------


def test_sales_can_propose_a_line_without_a_rate_when_mode_is_on(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    _turn_on_rate_blind_mode(client, headers)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _empty_draft_cost_sheet(client, headers, project_id)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(f"/cost-sheets/{cost_sheet_id}/lines", json={**LINE_FIELDS}, headers=sales_headers)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["rate"] is None
    assert body["amount"] is None
    assert body["pending"] is True


def test_sales_submitted_rate_is_always_discarded(client, director_user, db_session):
    """K.3: 'removed at the API by role, not hidden in the browser.'"""
    headers = _director_headers(client, director_user)
    _turn_on_rate_blind_mode(client, headers)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _empty_draft_cost_sheet(client, headers, project_id)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/lines", json={**LINE_FIELDS, "rate": 999}, headers=sales_headers
    )
    assert res.status_code == 201, res.text
    assert res.json()["rate"] is None

    # Confirm the stored row is really None, not merely stripped in the response.
    pm_view = client.get(f"/cost-sheets/{cost_sheet_id}/lines", headers=headers).json()
    assert pm_view[0]["rate"] is None


def test_sales_sees_rate_and_amount_stripped_even_after_pm_prices_it(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    _turn_on_rate_blind_mode(client, headers)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _empty_draft_cost_sheet(client, headers, project_id)

    sales_headers = _sales_headers(client, db_session)
    line = client.post(f"/cost-sheets/{cost_sheet_id}/lines", json={**LINE_FIELDS}, headers=sales_headers).json()

    client.patch(f"/cost-sheets/{cost_sheet_id}/lines/{line['id']}", json={"rate": 65}, headers=headers)

    sales_view = client.get(f"/cost-sheets/{cost_sheet_id}/lines", headers=sales_headers).json()
    assert sales_view[0]["rate"] is None
    assert sales_view[0]["amount"] is None
    assert sales_view[0]["pending"] is False  # PM has priced it -- Sales just can't see the number

    pm_view = client.get(f"/cost-sheets/{cost_sheet_id}/lines", headers=headers).json()
    assert pm_view[0]["rate"] == 65.0
    assert pm_view[0]["amount"] == 6500.0


def test_pm_can_price_a_pending_line_via_patch(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    _turn_on_rate_blind_mode(client, headers)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _empty_draft_cost_sheet(client, headers, project_id)
    sales_headers = _sales_headers(client, db_session)
    line = client.post(f"/cost-sheets/{cost_sheet_id}/lines", json={**LINE_FIELDS}, headers=sales_headers).json()
    assert line["pending"] is True

    res = client.patch(f"/cost-sheets/{cost_sheet_id}/lines/{line['id']}", json={"rate": 70}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["rate"] == 70.0
    assert res.json()["pending"] is False


def test_sales_cannot_patch_a_line(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    _turn_on_rate_blind_mode(client, headers)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _empty_draft_cost_sheet(client, headers, project_id)
    sales_headers = _sales_headers(client, db_session)
    line = client.post(f"/cost-sheets/{cost_sheet_id}/lines", json={**LINE_FIELDS}, headers=sales_headers).json()

    res = client.patch(f"/cost-sheets/{cost_sheet_id}/lines/{line['id']}", json={"rate": 999}, headers=sales_headers)
    assert res.status_code == 403


def test_recompute_blocked_while_a_line_is_pending(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    _turn_on_rate_blind_mode(client, headers)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _empty_draft_cost_sheet(client, headers, project_id)
    sales_headers = _sales_headers(client, db_session)
    client.post(f"/cost-sheets/{cost_sheet_id}/lines", json={**LINE_FIELDS}, headers=sales_headers)

    res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    assert res.status_code == 400
    assert "awaiting a PM-entered rate" in res.json()["detail"]


def test_verify_blocked_while_a_line_is_pending(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    _turn_on_rate_blind_mode(client, headers)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    # cost_total set directly at creation, so the *only* thing standing
    # between this sheet and Verified is the pending line added next.
    cost_sheet_id = client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": 100000}, headers=headers
    ).json()["id"]
    sales_headers = _sales_headers(client, db_session)
    line = client.post(f"/cost-sheets/{cost_sheet_id}/lines", json={**LINE_FIELDS}, headers=sales_headers).json()

    res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert res.status_code == 400
    assert "awaiting a PM-entered rate" in res.json()["detail"]

    client.patch(f"/cost-sheets/{cost_sheet_id}/lines/{line['id']}", json={"rate": 65}, headers=headers)
    res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "verified"


def test_full_recompute_and_verify_cycle_after_pricing_all_pending_lines(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    _turn_on_rate_blind_mode(client, headers)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _empty_draft_cost_sheet(client, headers, project_id)
    sales_headers = _sales_headers(client, db_session)
    line = client.post(f"/cost-sheets/{cost_sheet_id}/lines", json={**LINE_FIELDS}, headers=sales_headers).json()

    client.patch(f"/cost-sheets/{cost_sheet_id}/lines/{line['id']}", json={"rate": 65}, headers=headers)
    res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["cost_total"] > 0

    res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "verified"


# ---------------------------------------------------------------------------
# Attachments: Sales can attach vendor-quote images to the Cost Sheet
# ---------------------------------------------------------------------------


def test_sales_cannot_attach_to_cost_sheet_when_mode_is_off(client, director_user, db_session):
    import io

    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _empty_draft_cost_sheet(client, headers, project_id)
    sales_headers = _sales_headers(client, db_session)

    res = client.post(
        "/attachments",
        data={"doc_type": "cost_sheet", "doc_id": cost_sheet_id, "tag": "vendor_quote"},
        files={"file": ("quote.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_sales_can_attach_vendor_quote_when_mode_is_on(client, director_user, db_session):
    import io

    headers = _director_headers(client, director_user)
    _turn_on_rate_blind_mode(client, headers)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _empty_draft_cost_sheet(client, headers, project_id)
    sales_headers = _sales_headers(client, db_session)

    res = client.post(
        "/attachments",
        data={"doc_type": "cost_sheet", "doc_id": cost_sheet_id, "tag": "vendor_quote"},
        files={"file": ("quote.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
        headers=sales_headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["tag"] == "vendor_quote"


# ---------------------------------------------------------------------------
# PM/Director untouched by the toggle
# ---------------------------------------------------------------------------


def test_pm_workflow_unaffected_by_rate_blind_mode(client, director_user):
    """A PM-priced line, created the normal way, still works exactly as
    before regardless of the toggle."""
    headers = _director_headers(client, director_user)
    _turn_on_rate_blind_mode(client, headers)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _empty_draft_cost_sheet(client, headers, project_id)

    res = client.post(f"/cost-sheets/{cost_sheet_id}/lines", json={**LINE_FIELDS, "rate": 60}, headers=headers)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["rate"] == 60.0
    assert body["amount"] == 6000.0
    assert body["pending"] is False

    res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    assert res.status_code == 200, res.text
