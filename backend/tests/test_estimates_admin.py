"""Amendment 12 (Section 11): the Dashboard's "Pending Estimates" tile
had no screen behind it -- only the count. GET /estimates fixes that:
a cross-project, searchable, status-filterable list."""

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
        name="Test Sales", email="sales-estlist@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.SALES,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales-estlist@test.local")


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


def _draft_estimate(client, headers, project_id, project_sport_id, cost_for_option=850000):
    res = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": cost_for_option}]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def _estimate_for_new_project(client, headers, client_name, send=False):
    client_id = _create_client_record(client, headers, client_name)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate = _draft_estimate(client, headers, project_id, project_sport_id)
    if send:
        res = client.post(f"/estimates/{estimate['id']}/send", headers=headers)
        assert res.status_code == 200, res.text
        estimate = res.json()
    return project_id, estimate


def test_list_estimates_requires_auth(client):
    assert client.get("/estimates").status_code == 401


def test_sales_can_list_estimates(client, db_session):
    headers = _sales_headers(client, db_session)
    res = client.get("/estimates", headers=headers)
    assert res.status_code == 200, res.text


def test_lists_estimates_across_projects_with_project_client_enrichment(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, estimate = _estimate_for_new_project(client, headers, "Estimates Admin Client")

    res = client.get("/estimates", headers=headers)
    assert res.status_code == 200, res.text
    row = next(r for r in res.json() if r["id"] == estimate["id"])
    assert row["project_id"] == project_id
    assert row["client_name"] == "Estimates Admin Client"
    assert row["status"] == "draft"


def test_filter_by_status(client, director_user):
    headers = _director_headers(client, director_user)
    _project_a, draft_estimate = _estimate_for_new_project(client, headers, "Draft Status Client", send=False)
    _project_b, sent_estimate = _estimate_for_new_project(client, headers, "Sent Status Client", send=True)

    draft_rows = client.get("/estimates", params={"status": "draft"}, headers=headers).json()
    assert any(r["id"] == draft_estimate["id"] for r in draft_rows)
    assert not any(r["id"] == sent_estimate["id"] for r in draft_rows)

    sent_rows = client.get("/estimates", params={"status": "sent"}, headers=headers).json()
    assert any(r["id"] == sent_estimate["id"] for r in sent_rows)
    assert not any(r["id"] == draft_estimate["id"] for r in sent_rows)


def test_search_matches_client_name(client, director_user):
    headers = _director_headers(client, director_user)
    _project_id, estimate = _estimate_for_new_project(client, headers, "Searchable Estimate School")

    res = client.get("/estimates", params={"search": "Searchable Estimate"}, headers=headers)
    assert any(r["id"] == estimate["id"] for r in res.json())
