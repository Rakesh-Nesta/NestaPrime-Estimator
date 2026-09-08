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


def _pm_headers(client, db_session):
    user = User(
        name="Test PM", email="pm@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.PM
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "pm@test.local")


def _create_client_record(client, headers, client_type="school", name="Skip Request Client"):
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


def _approved_skip_request(client, headers, project_id, cost_total=850000):
    req = client.post(
        f"/projects/{project_id}/skip-requests",
        json={"stage_skipped": "cost_sheet", "reason": "Client wants a quotation directly"},
        headers=headers,
    ).json()
    approved = client.post(
        f"/skip-requests/{req['id']}/approve", json={"cost_total": cost_total}, headers=headers
    ).json()
    return req, approved


# ---------------------------------------------------------------------------
# Creating a skip request (Sales/PM/Director may request)
# ---------------------------------------------------------------------------


def test_sales_can_create_a_skip_request(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, director_headers)
    project_id = _create_project(client, director_headers, client_id)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/projects/{project_id}/skip-requests",
        json={"stage_skipped": "cost_sheet", "reason": "Client wants a quotation directly"},
        headers=sales_headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "pending"
    assert body["stage_skipped"] == "cost_sheet"
    assert body["approved_by_id"] is None


def test_skip_request_rejected_if_an_active_cost_sheet_already_exists(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": 100000}, headers=headers)

    res = client.post(
        f"/projects/{project_id}/skip-requests",
        json={"stage_skipped": "cost_sheet", "reason": "test"},
        headers=headers,
    )
    assert res.status_code == 400


def test_cannot_have_two_pending_skip_requests_for_the_same_project(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    client.post(
        f"/projects/{project_id}/skip-requests",
        json={"stage_skipped": "cost_sheet", "reason": "first"},
        headers=headers,
    )

    res = client.post(
        f"/projects/{project_id}/skip-requests",
        json={"stage_skipped": "cost_sheet", "reason": "second"},
        headers=headers,
    )
    assert res.status_code == 400


def test_skip_request_for_unknown_project_404s(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/projects/00000000-0000-0000-0000-000000000000/skip-requests",
        json={"stage_skipped": "cost_sheet", "reason": "test"},
        headers=headers,
    )
    assert res.status_code == 404


def test_list_skip_requests(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    client.post(
        f"/projects/{project_id}/skip-requests",
        json={"stage_skipped": "cost_sheet", "reason": "test"},
        headers=headers,
    )

    res = client.get(f"/projects/{project_id}/skip-requests", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 1


# ---------------------------------------------------------------------------
# Approving a skip request (M.2 rule 3: "Sales cannot skip alone")
# ---------------------------------------------------------------------------


def test_sales_cannot_approve_a_skip_request(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, director_headers)
    project_id = _create_project(client, director_headers, client_id)
    req = client.post(
        f"/projects/{project_id}/skip-requests",
        json={"stage_skipped": "cost_sheet", "reason": "test"},
        headers=director_headers,
    ).json()

    sales_headers = _sales_headers(client, db_session)
    res = client.post(f"/skip-requests/{req['id']}/approve", json={"cost_total": 850000}, headers=sales_headers)
    assert res.status_code == 403


def test_pm_can_approve_a_skip_request(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, director_headers)
    project_id = _create_project(client, director_headers, client_id)
    req = client.post(
        f"/projects/{project_id}/skip-requests",
        json={"stage_skipped": "cost_sheet", "reason": "test"},
        headers=director_headers,
    ).json()

    pm_headers = _pm_headers(client, db_session)
    res = client.post(f"/skip-requests/{req['id']}/approve", json={"cost_total": 850000}, headers=pm_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "approved"
    assert body["resulting_cost_sheet_id"] is not None
    assert body["decided_at"] is not None


def test_approving_creates_an_unverified_auto_generated_cost_sheet(client, director_user):
    """M.1: 'Unverified = auto-generated by a skip (rule 3), behaves as
    Draft for editing but allows the next stage to be created.'"""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_no = client.get(f"/projects/{project_id}", headers=headers).json()["project_no"]
    _, approved = _approved_skip_request(client, headers, project_id, cost_total=850000)

    cost_sheet = client.get(f"/cost-sheets/{approved['resulting_cost_sheet_id']}", headers=headers).json()
    assert cost_sheet["status"] == "unverified"
    assert cost_sheet["cost_total"] == 850000
    expected_suffix = project_no.split("-", 1)[1]
    assert cost_sheet["document_no"] == f"CS-{expected_suffix}-R1"


def test_cannot_approve_an_already_decided_skip_request(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    req, _ = _approved_skip_request(client, headers, project_id)

    res = client.post(f"/skip-requests/{req['id']}/approve", json={"cost_total": 100000}, headers=headers)
    assert res.status_code == 400


def test_approve_unknown_skip_request_404s(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/skip-requests/00000000-0000-0000-0000-000000000000/approve", json={"cost_total": 100000}, headers=headers
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Downstream consequences: Unverified cost sheet "behaves as Draft" for
# editing, unblocks Estimate creation, and flows into
# Quotation.cost_basis_unverified (M.2 rules 1 and 3)
# ---------------------------------------------------------------------------


def test_lines_can_be_added_to_and_recomputed_on_an_unverified_cost_sheet(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    _, approved = _approved_skip_request(client, headers, project_id, cost_total=1)
    cost_sheet_id = approved["resulting_cost_sheet_id"]

    add_res = client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={"work_package": "structure", "category": "MS structure", "item_name": "SHS 3x3", "unit": "kg", "quantity": 100, "rate": 68},
        headers=headers,
    )
    assert add_res.status_code == 201, add_res.text

    recompute_res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    assert recompute_res.status_code == 200, recompute_res.text
    assert recompute_res.json()["status"] == "unverified"  # recompute doesn't change status


def test_unverified_cost_sheet_can_be_verified_later(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    _, approved = _approved_skip_request(client, headers, project_id, cost_total=850000)

    res = client.post(f"/cost-sheets/{approved['resulting_cost_sheet_id']}/verify", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "verified"


def test_estimate_can_be_created_from_an_unverified_cost_sheet(client, director_user):
    """M.2 rule 1's exception: an Unverified cost sheet 'permits creation
    of the next stage.'"""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _approved_skip_request(client, headers, project_id, cost_total=850000)

    res = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 850000}]},
        headers=headers,
    )
    assert res.status_code == 201, res.text


def test_quotation_from_unverified_cost_sheet_carries_cost_basis_unverified_flag(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _approved_skip_request(client, headers, project_id, cost_total=850000)

    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 850000}]},
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
    assert quotation["cost_basis_unverified"] is True


def test_pm_cannot_release_quotation_with_unverified_cost_basis_only_director_can(client, director_user, db_session):
    """M.1: 'Director if ... the underlying Cost Sheet is Unverified.'"""
    director_headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, director_headers)
    project_id = _create_project(client, director_headers, client_id)
    project_sport_id = _add_project_sport(client, director_headers, project_id)
    _approved_skip_request(client, director_headers, project_id, cost_total=850000)

    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 850000}]},
        headers=director_headers,
    ).json()
    option_id = estimate["options"][0]["id"]
    client.patch(
        f"/estimates/{estimate['id']}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test setup"},
        headers=director_headers,
    )
    quotation_id = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id]},
        headers=director_headers,
    ).json()["id"]

    pm_headers = _pm_headers(client, db_session)
    pm_attempt = client.post(f"/quotations/{quotation_id}/release", headers=pm_headers)
    assert pm_attempt.status_code == 403

    director_attempt = client.post(f"/quotations/{quotation_id}/release", headers=director_headers)
    assert director_attempt.status_code == 200


def test_quotation_cannot_be_marked_won_until_cost_sheet_is_verified(client, director_user):
    """M.2 rule 1: 'cannot be marked Won until the Cost Sheet is verified.'"""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _, approved = _approved_skip_request(client, headers, project_id, cost_total=850000)

    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 850000}]},
        headers=headers,
    ).json()
    option_id = estimate["options"][0]["id"]
    client.patch(
        f"/estimates/{estimate['id']}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    quotation_id = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id]},
        headers=headers,
    ).json()["id"]
    client.post(f"/quotations/{quotation_id}/release", headers=headers)
    client.post(f"/quotations/{quotation_id}/send", headers=headers)

    won_attempt = client.post(
        f"/quotations/{quotation_id}/mark-won",
        json={"reason": "test", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert won_attempt.status_code == 400

    client.post(f"/cost-sheets/{approved['resulting_cost_sheet_id']}/verify", headers=headers)
    won_retry = client.post(
        f"/quotations/{quotation_id}/mark-won",
        json={"reason": "test", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert won_retry.status_code == 200, won_retry.text


def test_skip_request_endpoints_require_auth(client):
    assert client.post("/projects/00000000-0000-0000-0000-000000000000/skip-requests", json={
        "stage_skipped": "cost_sheet", "reason": "x"
    }).status_code == 401
    assert client.post("/skip-requests/00000000-0000-0000-0000-000000000000/approve", json={
        "cost_total": 100
    }).status_code == 401
