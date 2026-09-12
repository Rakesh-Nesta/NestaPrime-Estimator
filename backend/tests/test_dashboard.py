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


def _create_client_record(client, headers, client_type="school", name="Test School"):
    res = client.post("/clients", json={"name": name, "type": client_type}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_project(client, headers, client_id, city="Mumbai"):
    fields = {
        "client_id": client_id,
        "city": city,
        "site_condition": "level",
        "soil_type": "normal",
        "building_status": "open_air",
        "site_access": "good",
        "power_available": "yes",
        "water_available": True,
        "package": "standard",
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _add_project_sport(client, headers, project_id, sport_key="badminton"):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": sport_id, "building_status": "open_air"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _released_quotation(client, headers, cost_for_option=850000, client_type="school"):
    """CS -> EST -> approved option -> NPQ -> released, mirroring
    test_reports.py's own helper of the same name."""
    client_id = _create_client_record(client, headers, client_type=client_type)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)

    cs_res = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_for_option}, headers=headers)
    client.post(f"/cost-sheets/{cs_res.json()['id']}/verify", headers=headers)

    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": cost_for_option}]},
        headers=headers,
    ).json()
    option_id = estimate["options"][0]["id"]
    client.patch(
        f"/estimates/{estimate['id']}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test setup"},
        headers=headers,
    )

    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id]},
        headers=headers,
    ).json()
    release_res = client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    assert release_res.status_code == 200, release_res.text
    return release_res.json(), project_id


def test_dashboard_requires_auth(client):
    res = client.get("/dashboard")
    assert res.status_code == 401


def test_open_projects_count_excludes_won_and_lost(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    _create_project(client, headers, client_id)  # untouched -- stays open

    quotation, _ = _released_quotation(client, headers)
    client.post(f"/quotations/{quotation['id']}/send", headers=headers)
    won_res = client.post(
        f"/quotations/{quotation['id']}/mark-won",
        json={"waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert won_res.status_code == 200, won_res.text

    res = client.get("/dashboard", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    # one open (untouched) project + one WON project not counted as open
    assert body["summary"]["open_projects_count"] == 1


def test_won_this_month_total_sums_only_won_quotations(client, director_user):
    headers = _director_headers(client, director_user)

    quotation, _ = _released_quotation(client, headers, cost_for_option=850000)
    client.post(f"/quotations/{quotation['id']}/send", headers=headers)
    won_res = client.post(
        f"/quotations/{quotation['id']}/mark-won",
        json={"waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert won_res.status_code == 200, won_res.text
    won_total = won_res.json()["quotation_total"]

    # A second, merely-released (not won) quotation must not be counted.
    _released_quotation(client, headers, cost_for_option=500000)

    res = client.get("/dashboard", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["summary"]["won_this_month_total"] == won_total


def test_pending_estimates_and_quotations_counts(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)

    cs_res = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": 100000}, headers=headers)
    client.post(f"/cost-sheets/{cs_res.json()['id']}/verify", headers=headers)
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 100000}]},
        headers=headers,
    ).json()
    send_res = client.post(f"/estimates/{estimate['id']}/send", headers=headers)
    assert send_res.status_code == 200, send_res.text

    res = client.get("/dashboard", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["summary"]["pending_estimates_count"] == 1
    assert body["summary"]["pending_quotations_count"] == 0  # none created yet


def test_overdue_clients_count(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    flag_res = client.patch(f"/clients/{client_id}", json={"overdue_flag": True}, headers=headers)
    assert flag_res.status_code == 200, flag_res.text

    res = client.get("/dashboard", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["summary"]["overdue_clients_count"] == 1


def test_recent_projects_lists_newest_first_with_client_name(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, name="Older Client")
    _create_project(client, headers, client_id, city="Pune")
    client_id_2 = _create_client_record(client, headers, name="Newer Client")
    newest_id = _create_project(client, headers, client_id_2, city="Chennai")

    res = client.get("/dashboard", headers=headers)
    assert res.status_code == 200, res.text
    recent = res.json()["recent_projects"]
    assert recent[0]["id"] == newest_id
    assert recent[0]["client_name"] == "Newer Client"
    assert recent[0]["city"] == "Chennai"


def test_recent_activity_visible_to_director_only(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    create_res = client.post(
        "/users",
        json={"name": "Audit Trigger", "email": "audit-trigger@test.local", "role": "sales", "password": "TestPass!1"},
        headers=director_headers,
    )
    assert create_res.status_code == 201, create_res.text

    director_res = client.get("/dashboard", headers=director_headers)
    assert director_res.status_code == 200, director_res.text
    assert director_res.json()["recent_activity"] is not None
    assert len(director_res.json()["recent_activity"]) >= 1

    sales_headers = _sales_headers(client, db_session)
    sales_res = client.get("/dashboard", headers=sales_headers)
    assert sales_res.status_code == 200, sales_res.text
    assert sales_res.json()["recent_activity"] is None
