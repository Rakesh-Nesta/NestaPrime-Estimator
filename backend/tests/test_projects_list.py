"""Amendment 12 (Section 11): the Dashboard's "Open Projects" /
"Quotation-winning projects" tiles had no screen behind them -- only a
5-row "Recent projects" list. GET /projects fixes that: searchable,
filterable by open/won/lost, matching dashboard.py's own status
vocabulary exactly."""

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
        name="Test Sales", email="sales-projlist@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.SALES,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales-projlist@test.local")


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


def test_list_projects_requires_auth(client):
    assert client.get("/projects").status_code == 401


def test_sales_can_list_projects(client, db_session):
    """Broader visibility than Quotations Admin -- a project list carries
    no cost/margin, matching dashboard.py's own broad role gate."""
    headers = _sales_headers(client, db_session)
    res = client.get("/projects", headers=headers)
    assert res.status_code == 200, res.text


def test_open_project_has_no_won_or_lost_quotation(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "Open Project Client")
    project_id = _create_project(client, headers, client_id)

    res = client.get("/projects", params={"status": "open"}, headers=headers)
    assert res.status_code == 200, res.text
    row = next(r for r in res.json() if r["id"] == project_id)
    assert row["status"] == "open"


def test_won_project_appears_under_won_filter(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, quotation = _quotation_for_new_project(client, headers, "Won Filter Client")
    client.post(f"/quotations/{quotation['id']}/send", headers=headers)
    res = client.post(
        f"/quotations/{quotation['id']}/mark-won",
        json={"waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert res.status_code == 200, res.text

    won = client.get("/projects", params={"status": "won"}, headers=headers).json()
    assert any(r["id"] == project_id for r in won)

    open_rows = client.get("/projects", params={"status": "open"}, headers=headers).json()
    assert not any(r["id"] == project_id for r in open_rows)


def test_search_matches_client_name(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "Riverside Searchable School")
    project_id = _create_project(client, headers, client_id)

    res = client.get("/projects", params={"search": "Riverside Searchable"}, headers=headers)
    assert res.status_code == 200, res.text
    assert any(r["id"] == project_id for r in res.json())

    miss = client.get("/projects", params={"search": "Nonexistent Client Name"}, headers=headers)
    assert not any(r["id"] == project_id for r in miss.json())


def test_search_matches_project_no(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "Project No Search Client")
    project_id = _create_project(client, headers, client_id)
    project_no = client.get(f"/projects/{project_id}", headers=headers).json()["project_no"]

    res = client.get("/projects", params={"search": project_no}, headers=headers)
    assert any(r["id"] == project_id for r in res.json())
