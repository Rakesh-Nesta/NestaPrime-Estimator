"""Amendment 6b (Section 9): "admin reviews all quotations and daily
activity" -- a Director-only, cross-project browse of every quotation,
filterable, with a CSV export (Director-approved 14 Sept 2026 addition
to the original browse-and-drill scope)."""

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
        name="Test Sales", email="sales-qa@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.SALES,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales-qa@test.local")


def _create_client_record(client, headers, name):
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


def _add_project_sport(client, headers, project_id, sport_key="badminton"):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports", json={"sport_id": sport_id, "building_status": "open_air"}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _verified_cost_sheet(client, headers, project_id, cost_total=850000):
    cost_sheet_id = client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_total}, headers=headers
    ).json()["id"]
    res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert res.status_code == 200, res.text
    return cost_sheet_id


def _sent_estimate(client, headers, project_id, project_sport_id, cost_for_option=850000):
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": cost_for_option}]},
        headers=headers,
    ).json()
    res = client.post(f"/estimates/{estimate['id']}/send", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _approve_option(client, headers, estimate_id, option_id):
    res = client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert res.status_code == 200, res.text


def _released_quotation(client, headers, project_id, estimate_id, option_id):
    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate_id, "included_option_ids": [option_id]},
        headers=headers,
    ).json()
    res = client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _quotation_for_new_project(client, headers, client_name):
    client_id = _create_client_record(client, headers, client_name)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)
    option_id = estimate["options"][0]["id"]
    _approve_option(client, headers, estimate["id"], option_id)
    quotation = _released_quotation(client, headers, project_id, estimate["id"], option_id)
    return project_id, quotation


# ---------------------------------------------------------------------------
# GET /quotations
# ---------------------------------------------------------------------------


def test_director_lists_all_quotations_across_projects(client, director_user):
    headers = _director_headers(client, director_user)
    project_a, quotation_a = _quotation_for_new_project(client, headers, "All-Quotations Client A")
    project_b, quotation_b = _quotation_for_new_project(client, headers, "All-Quotations Client B")

    res = client.get("/quotations", headers=headers)
    assert res.status_code == 200, res.text
    doc_nos = {row["document_no"] for row in res.json()}
    assert quotation_a["document_no"] in doc_nos
    assert quotation_b["document_no"] in doc_nos

    row_a = next(r for r in res.json() if r["document_no"] == quotation_a["document_no"])
    assert row_a["project_id"] == project_a
    assert row_a["client_name"] == "All-Quotations Client A"
    assert row_a["sports"] == ["Badminton"]
    assert row_a["status"] == "released"


def test_sales_cannot_list_all_quotations(client, db_session):
    headers = _sales_headers(client, db_session)
    res = client.get("/quotations", headers=headers)
    assert res.status_code == 403


def test_quotations_require_auth(client):
    assert client.get("/quotations").status_code == 401


def test_filter_by_project_id_returns_only_that_project(client, director_user):
    headers = _director_headers(client, director_user)
    project_a, quotation_a = _quotation_for_new_project(client, headers, "Filter Client A")
    _project_b, quotation_b = _quotation_for_new_project(client, headers, "Filter Client B")

    res = client.get("/quotations", params={"project_id": project_a}, headers=headers)
    assert res.status_code == 200, res.text
    doc_nos = {row["document_no"] for row in res.json()}
    assert quotation_a["document_no"] in doc_nos
    assert quotation_b["document_no"] not in doc_nos


def test_filter_by_status(client, director_user):
    headers = _director_headers(client, director_user)
    _project, quotation = _quotation_for_new_project(client, headers, "Status Filter Client")

    released = client.get("/quotations", params={"status": "released"}, headers=headers).json()
    assert quotation["document_no"] in {r["document_no"] for r in released}

    won = client.get("/quotations", params={"status": "won"}, headers=headers).json()
    assert quotation["document_no"] not in {r["document_no"] for r in won}


# ---------------------------------------------------------------------------
# GET /quotations/export
# ---------------------------------------------------------------------------


def test_export_csv_contains_the_filtered_quotation(client, director_user):
    headers = _director_headers(client, director_user)
    _project, quotation = _quotation_for_new_project(client, headers, "CSV Export Client")

    res = client.get("/quotations/export", headers=headers)
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/csv")
    body = res.text
    assert quotation["document_no"] in body
    assert "CSV Export Client" in body


def test_sales_cannot_export_all_quotations(client, db_session):
    headers = _sales_headers(client, db_session)
    res = client.get("/quotations/export", headers=headers)
    assert res.status_code == 403
