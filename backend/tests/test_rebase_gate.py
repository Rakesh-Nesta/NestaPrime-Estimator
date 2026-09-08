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


def _create_client_record(client, headers, name="Rebase Client"):
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
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": cost_for_option}]},
        headers=headers,
    ).json()
    return estimate["id"], estimate["options"][0]["id"]


def _released_quotation(client, headers, project_id, estimate_id, option_id):
    client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate_id, "included_option_ids": [option_id]},
        headers=headers,
    ).json()
    res = client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    assert res.status_code == 200, res.text
    return quotation["id"]


def _revise_and_reverify(client, headers, cost_sheet_id, cost_total=900000):
    res = client.post(f"/cost-sheets/{cost_sheet_id}/revise", json={"cost_total": cost_total}, headers=headers)
    assert res.status_code == 201, res.text
    new_cost_sheet_id = res.json()["id"]
    res = client.post(f"/cost-sheets/{new_cost_sheet_id}/verify", headers=headers)
    assert res.status_code == 200, res.text
    return new_cost_sheet_id


def _audit_entries(client, headers, **params):
    res = client.get("/audit-log", params=params, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


# ---------------------------------------------------------------------------
# Estimate
# ---------------------------------------------------------------------------


def test_estimate_flags_rebase_required_after_cost_sheet_revision(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = _verified_cost_sheet(client, headers, project_id)
    estimate_id, _ = _draft_estimate(client, headers, project_id, project_sport_id)

    fresh = client.get(f"/estimates/{estimate_id}", headers=headers).json()
    assert fresh["cost_basis_rebase_required"] is False

    _revise_and_reverify(client, headers, cost_sheet_id)

    stale = client.get(f"/estimates/{estimate_id}", headers=headers).json()
    assert stale["cost_basis_rebase_required"] is True


def test_cannot_send_a_stale_estimate(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = _verified_cost_sheet(client, headers, project_id)
    estimate_id, _ = _draft_estimate(client, headers, project_id, project_sport_id)
    _revise_and_reverify(client, headers, cost_sheet_id)

    res = client.post(f"/estimates/{estimate_id}/send", headers=headers)
    assert res.status_code == 400
    assert "rebase" in res.json()["detail"].lower()


def test_rebase_estimate_clears_the_flag_and_allows_send(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = _verified_cost_sheet(client, headers, project_id)
    estimate_id, _ = _draft_estimate(client, headers, project_id, project_sport_id)
    new_cost_sheet_id = _revise_and_reverify(client, headers, cost_sheet_id)

    res = client.post(f"/estimates/{estimate_id}/rebase", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["cost_basis_rebase_required"] is False
    assert body["cost_sheet_id"] == new_cost_sheet_id

    res = client.post(f"/estimates/{estimate_id}/send", headers=headers)
    assert res.status_code == 200, res.text


def test_rebase_fails_when_nothing_to_rebase(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate_id, _ = _draft_estimate(client, headers, project_id, project_sport_id)

    res = client.post(f"/estimates/{estimate_id}/rebase", headers=headers)
    assert res.status_code == 400
    assert "nothing to rebase" in res.json()["detail"].lower()


def test_rebase_fails_when_new_revision_not_yet_verified(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = _verified_cost_sheet(client, headers, project_id)
    estimate_id, _ = _draft_estimate(client, headers, project_id, project_sport_id)

    res = client.post(f"/cost-sheets/{cost_sheet_id}/revise", json={"cost_total": 900000}, headers=headers)
    assert res.status_code == 201, res.text

    res = client.post(f"/estimates/{estimate_id}/rebase", headers=headers)
    assert res.status_code == 400
    assert "not yet verified" in res.json()["detail"].lower()


def test_rebase_writes_an_audit_log_entry(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = _verified_cost_sheet(client, headers, project_id)
    estimate_id, _ = _draft_estimate(client, headers, project_id, project_sport_id)
    _revise_and_reverify(client, headers, cost_sheet_id)

    client.post(f"/estimates/{estimate_id}/rebase", headers=headers)

    entries = _audit_entries(client, headers, document_type="estimate", document_id=estimate_id)
    entry = next(e for e in entries if e["field"] == "cost_sheet_id")
    assert "Rebased to" in entry["reason"]


def test_sales_cannot_rebase_an_estimate(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = _verified_cost_sheet(client, headers, project_id)
    estimate_id, _ = _draft_estimate(client, headers, project_id, project_sport_id)
    _revise_and_reverify(client, headers, cost_sheet_id)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(f"/estimates/{estimate_id}/rebase", headers=sales_headers)
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Quotation (chained through its Estimate)
# ---------------------------------------------------------------------------


def test_quotation_flags_rebase_required_via_its_estimate(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = _verified_cost_sheet(client, headers, project_id)
    estimate_id, option_id = _draft_estimate(client, headers, project_id, project_sport_id)
    quotation_id = _released_quotation(client, headers, project_id, estimate_id, option_id)

    fresh = client.get(f"/quotations/{quotation_id}", headers=headers).json()
    assert fresh["cost_basis_rebase_required"] is False

    _revise_and_reverify(client, headers, cost_sheet_id)

    stale = client.get(f"/quotations/{quotation_id}", headers=headers).json()
    assert stale["cost_basis_rebase_required"] is True


def test_cannot_send_a_stale_quotation(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = _verified_cost_sheet(client, headers, project_id)
    estimate_id, option_id = _draft_estimate(client, headers, project_id, project_sport_id)
    quotation_id = _released_quotation(client, headers, project_id, estimate_id, option_id)
    _revise_and_reverify(client, headers, cost_sheet_id)

    res = client.post(f"/quotations/{quotation_id}/send", headers=headers)
    assert res.status_code == 400
    assert "rebase" in res.json()["detail"].lower()


def test_cannot_release_a_draft_quotation_whose_estimate_is_stale(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = _verified_cost_sheet(client, headers, project_id)
    estimate_id, option_id = _draft_estimate(client, headers, project_id, project_sport_id)
    client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate_id, "included_option_ids": [option_id]},
        headers=headers,
    ).json()
    _revise_and_reverify(client, headers, cost_sheet_id)

    res = client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    assert res.status_code == 400
    assert "rebase" in res.json()["detail"].lower()


def test_rebasing_the_estimate_clears_rebase_required_on_its_quotation_too(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = _verified_cost_sheet(client, headers, project_id)
    estimate_id, option_id = _draft_estimate(client, headers, project_id, project_sport_id)
    quotation_id = _released_quotation(client, headers, project_id, estimate_id, option_id)
    _revise_and_reverify(client, headers, cost_sheet_id)

    stale = client.get(f"/quotations/{quotation_id}", headers=headers).json()
    assert stale["cost_basis_rebase_required"] is True

    client.post(f"/estimates/{estimate_id}/rebase", headers=headers)

    fresh = client.get(f"/quotations/{quotation_id}", headers=headers).json()
    assert fresh["cost_basis_rebase_required"] is False

    res = client.post(f"/quotations/{quotation_id}/send", headers=headers)
    assert res.status_code == 200, res.text
