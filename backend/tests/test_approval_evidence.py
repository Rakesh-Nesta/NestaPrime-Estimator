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


def _create_client_record(client, headers, client_type="school"):
    res = client.post("/clients", json={"name": "Evidence Client", "type": client_type}, headers=headers)
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


def _add_project_sport(client, headers, project_id, sport_key="box_cricket"):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports", json={"sport_id": sport_id, "building_status": "open_air"}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _draft_estimate(client, headers, client_type="school", cost_for_option=100000):
    client_id = _create_client_record(client, headers, client_type=client_type)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_for_option}, headers=headers
    ).json()["id"]
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": cost_for_option}]},
        headers=headers,
    ).json()
    return project_id, estimate["id"], estimate["options"][0]["id"]


def _upload_evidence(client, headers, doc_type, doc_id, strength="informal"):
    res = client.post(
        "/attachments",
        data={"doc_type": doc_type, "doc_id": doc_id, "tag": "approval_evidence", "approval_strength": strength},
        files={"file": ("evidence.png", b"screenshot bytes", "image/png")},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------------------
# Estimate option approval (M.3)
# ---------------------------------------------------------------------------


def test_cannot_approve_without_evidence_or_waiver(client, director_user):
    headers = _director_headers(client, director_user)
    _, estimate_id, option_id = _draft_estimate(client, headers)

    res = client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "approved"},
        headers=headers,
    )
    assert res.status_code == 422


def test_approval_succeeds_once_evidence_is_uploaded(client, director_user):
    headers = _director_headers(client, director_user)
    _, estimate_id, option_id = _draft_estimate(client, headers)
    _upload_evidence(client, headers, "estimate", estimate_id)

    res = client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "approved"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["client_status"] == "approved"


def test_sales_cannot_waive_evidence_only_pm_director_can(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    _, estimate_id, option_id = _draft_estimate(client, headers)

    sales_headers = _sales_headers(client, db_session)
    sales_attempt = client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "trust me"},
        headers=sales_headers,
    )
    assert sales_attempt.status_code == 403

    pm_headers = _pm_headers(client, db_session)
    pm_attempt = client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "client confirmed verbally, formal evidence pending"},
        headers=pm_headers,
    )
    assert pm_attempt.status_code == 200, pm_attempt.text


def test_rejecting_an_option_does_not_require_evidence(client, director_user):
    """The evidence gate only applies to moving to Approved, not Rejected
    or Demand received."""
    headers = _director_headers(client, director_user)
    _, estimate_id, option_id = _draft_estimate(client, headers)

    res = client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "rejected"},
        headers=headers,
    )
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# Quotation mark-won (M.3): Formal required above Rs 25L or Government/Tender
# ---------------------------------------------------------------------------


def _sent_quotation(client, headers, client_type="school", cost_for_option=100000):
    project_id, estimate_id, option_id = _draft_estimate(client, headers, client_type=client_type, cost_for_option=cost_for_option)
    _upload_evidence(client, headers, "estimate", estimate_id)
    client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "approved"},
        headers=headers,
    )
    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate_id, "included_option_ids": [option_id]},
        headers=headers,
    ).json()
    client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    client.post(f"/quotations/{quotation['id']}/send", headers=headers)
    return quotation["id"]


def test_mark_won_requires_evidence(client, director_user):
    headers = _director_headers(client, director_user)
    quotation_id = _sent_quotation(client, headers)

    res = client.post(f"/quotations/{quotation_id}/mark-won", json={}, headers=headers)
    assert res.status_code == 422


def test_informal_evidence_is_enough_below_the_formal_threshold(client, director_user):
    headers = _director_headers(client, director_user)
    quotation_id = _sent_quotation(client, headers, client_type="school", cost_for_option=100000)
    _upload_evidence(client, headers, "quotation", quotation_id, strength="informal")

    res = client.post(f"/quotations/{quotation_id}/mark-won", json={}, headers=headers)
    assert res.status_code == 200, res.text


def test_government_client_requires_formal_evidence_even_below_25l(client, director_user):
    """M.3: 'Government / Tender Mode ... require Formal evidence before Won.'"""
    headers = _director_headers(client, director_user)
    quotation_id = _sent_quotation(client, headers, client_type="government", cost_for_option=100000)
    _upload_evidence(client, headers, "quotation", quotation_id, strength="informal")

    informal_attempt = client.post(f"/quotations/{quotation_id}/mark-won", json={}, headers=headers)
    assert informal_attempt.status_code == 422

    _upload_evidence(client, headers, "quotation", quotation_id, strength="formal")
    formal_attempt = client.post(f"/quotations/{quotation_id}/mark-won", json={}, headers=headers)
    assert formal_attempt.status_code == 200, formal_attempt.text


def test_large_quotation_requires_formal_evidence(client, director_user):
    """M.3: 'any quotation above Rs 25 L require Formal evidence before Won.'"""
    headers = _director_headers(client, director_user)
    quotation_id = _sent_quotation(client, headers, client_type="school", cost_for_option=3000000)
    _upload_evidence(client, headers, "quotation", quotation_id, strength="informal")

    informal_attempt = client.post(f"/quotations/{quotation_id}/mark-won", json={}, headers=headers)
    assert informal_attempt.status_code == 422

    _upload_evidence(client, headers, "quotation", quotation_id, strength="formal")
    formal_attempt = client.post(f"/quotations/{quotation_id}/mark-won", json={}, headers=headers)
    assert formal_attempt.status_code == 200, formal_attempt.text


def test_director_can_waive_evidence_for_mark_won(client, director_user):
    headers = _director_headers(client, director_user)
    quotation_id = _sent_quotation(client, headers)

    res = client.post(
        f"/quotations/{quotation_id}/mark-won",
        json={"waive_evidence_reason": "director accepted verbally, documenting later"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
