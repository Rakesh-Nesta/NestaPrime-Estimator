from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _pm_headers(client, db_session):
    user = User(
        name="Test PM", email="pm@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.PM
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "pm@test.local")


def _create_client_record(client, headers, client_type="school", name="Flagged Client"):
    res = client.post("/clients", json={"name": name, "type": client_type}, headers=headers)
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
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    return cost_sheet_id


def _draft_quotation(client, headers, project_id, project_sport_id, cost_for_option=850000):
    _verified_cost_sheet(client, headers, project_id, cost_for_option)
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
    return quotation["id"]


# ---------------------------------------------------------------------------
# Director-only client flag management
# ---------------------------------------------------------------------------


def test_client_flags_default_to_false(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    body = client.get(f"/clients/{client_id}", headers=headers).json()
    assert body["overdue_flag"] is False
    assert body["blacklist_flag"] is False


def test_director_can_set_and_clear_client_flags(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)

    res = client.patch(f"/clients/{client_id}", json={"blacklist_flag": True}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["blacklist_flag"] is True
    assert res.json()["overdue_flag"] is False  # untouched

    res = client.patch(f"/clients/{client_id}", json={"blacklist_flag": False, "overdue_flag": True}, headers=headers)
    assert res.json()["blacklist_flag"] is False
    assert res.json()["overdue_flag"] is True


def test_pm_cannot_set_client_flags(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, director_headers)

    pm_headers = _pm_headers(client, db_session)
    res = client.patch(f"/clients/{client_id}", json={"blacklist_flag": True}, headers=pm_headers)
    assert res.status_code == 403


def test_client_flags_update_for_unknown_client_404s(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.patch(
        "/clients/00000000-0000-0000-0000-000000000000", json={"blacklist_flag": True}, headers=headers
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# blacklist_flag blocks new Estimates (Part O)
# ---------------------------------------------------------------------------


def test_blacklisted_client_cannot_get_a_new_estimate(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    client.patch(f"/clients/{client_id}", json={"blacklist_flag": True}, headers=headers)

    res = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 850000}]},
        headers=headers,
    )
    assert res.status_code == 400
    assert "blacklist" in res.json()["detail"].lower()


def test_clearing_blacklist_flag_allows_estimate_creation_again(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    client.patch(f"/clients/{client_id}", json={"blacklist_flag": True}, headers=headers)
    client.patch(f"/clients/{client_id}", json={"blacklist_flag": False}, headers=headers)

    res = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 850000}]},
        headers=headers,
    )
    assert res.status_code == 201, res.text


def test_non_blacklisted_client_is_unaffected(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)

    res = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 850000}]},
        headers=headers,
    )
    assert res.status_code == 201, res.text


# ---------------------------------------------------------------------------
# overdue_flag blocks new Quotation release until a Director clears it
# ---------------------------------------------------------------------------


def test_overdue_client_quotation_cannot_be_released(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    quotation_id = _draft_quotation(client, headers, project_id, project_sport_id)
    client.patch(f"/clients/{client_id}", json={"overdue_flag": True}, headers=headers)

    res = client.post(f"/quotations/{quotation_id}/release", headers=headers)
    assert res.status_code == 400
    assert "overdue" in res.json()["detail"].lower()


def test_overdue_flag_blocks_release_even_for_director(client, director_user):
    """Part O: 'blocks new Quotation release until Director clears' -- the
    block is on the FLAG, not the releasing role; a Director must clear
    the flag first, not simply release anyway."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    quotation_id = _draft_quotation(client, headers, project_id, project_sport_id)
    client.patch(f"/clients/{client_id}", json={"overdue_flag": True}, headers=headers)

    res = client.post(f"/quotations/{quotation_id}/release", headers=headers)
    assert res.status_code == 400


def test_clearing_overdue_flag_allows_release_again(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    quotation_id = _draft_quotation(client, headers, project_id, project_sport_id)
    client.patch(f"/clients/{client_id}", json={"overdue_flag": True}, headers=headers)
    client.patch(f"/clients/{client_id}", json={"overdue_flag": False}, headers=headers)

    res = client.post(f"/quotations/{quotation_id}/release", headers=headers)
    assert res.status_code == 200, res.text


def test_non_overdue_client_quotation_releases_normally(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    quotation_id = _draft_quotation(client, headers, project_id, project_sport_id)

    res = client.post(f"/quotations/{quotation_id}/release", headers=headers)
    assert res.status_code == 200, res.text
