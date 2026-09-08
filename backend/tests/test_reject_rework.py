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
        name="Test Sales", email="sales@test.local",
        hashed_password=hash_password("TestPass!1"), role=UserRole.SALES,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales@test.local")


def _create_client_record(client, headers, client_type="school", name="Reject Rework Client"):
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


def _cost_sheet(client, headers, project_id, cost_total=850000):
    res = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_total}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _verified_cost_sheet(client, headers, project_id, cost_total=850000):
    cost_sheet_id = _cost_sheet(client, headers, project_id, cost_total)
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


def _audit_entries(client, headers, **params):
    res = client.get("/audit-log", params=params, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


# ---------------------------------------------------------------------------
# reject_cost_sheet
# ---------------------------------------------------------------------------


def test_rejecting_a_verified_cost_sheet_returns_it_to_draft(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _verified_cost_sheet(client, headers, project_id)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/reject",
        json={"reason_category": "wrong_quantities", "note": "quantities look off for the court count"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "draft"
    assert body["verified_by_id"] is None
    assert body["verified_at"] is None


def test_rejecting_a_cost_sheet_flips_dependent_quotations_to_unverified(client, director_user):
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
    assert quotation["cost_basis_unverified"] is False

    client.post(
        f"/cost-sheets/{cost_sheet_id}/reject",
        json={"reason_category": "margin", "note": "margin too thin, rework the rates"},
        headers=headers,
    )

    refreshed = client.get(f"/quotations/{quotation['id']}", headers=headers).json()
    assert refreshed["cost_basis_unverified"] is True


def test_rejecting_an_unverified_skip_generated_cost_sheet_also_works(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    req = client.post(
        f"/projects/{project_id}/skip-requests",
        json={"stage_skipped": "cost_sheet", "reason": "client wants a quotation directly"},
        headers=headers,
    ).json()
    approved = client.post(f"/skip-requests/{req['id']}/approve", json={"cost_total": 500000}, headers=headers).json()
    cost_sheet_id = approved["resulting_cost_sheet_id"]

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/reject",
        json={"reason_category": "scope_unclear", "note": "scope needs clarification before verifying"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "draft"


def test_rejecting_a_draft_cost_sheet_fails(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _cost_sheet(client, headers, project_id)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/reject",
        json={"reason_category": "other", "note": "nothing to reject"},
        headers=headers,
    )
    assert res.status_code == 400


def test_rejecting_an_unknown_cost_sheet_404s(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/cost-sheets/00000000-0000-0000-0000-000000000000/reject",
        json={"reason_category": "other", "note": "n/a"},
        headers=headers,
    )
    assert res.status_code == 404


def test_sales_cannot_reject_a_cost_sheet(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, director_headers)
    project_id = _create_project(client, director_headers, client_id)
    cost_sheet_id = _verified_cost_sheet(client, director_headers, project_id)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/reject",
        json={"reason_category": "other", "note": "n/a"},
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_rejecting_a_cost_sheet_writes_an_audit_log_entry(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _verified_cost_sheet(client, headers, project_id)

    client.post(
        f"/cost-sheets/{cost_sheet_id}/reject",
        json={"reason_category": "rate_not_confirmed", "note": "vendor rate still pending"},
        headers=headers,
    )

    entries = _audit_entries(client, headers, document_type="cost_sheet", document_id=cost_sheet_id)
    entry = next(e for e in entries if e["new_value"] == "draft")
    assert entry["old_value"] == "verified"
    assert entry["reason"] == "rate_not_confirmed: vendor rate still pending"


def test_rejected_cost_sheet_can_be_reworked_and_reverified(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _verified_cost_sheet(client, headers, project_id)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/reject",
        json={"reason_category": "wrong_quantities", "note": "recount needed"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "draft"

    # Draft is editable -- the cost_total from creation is still positive,
    # so the reworked sheet can be verified again without further changes.
    res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "verified"


# ---------------------------------------------------------------------------
# reject_quotation
# ---------------------------------------------------------------------------


def test_rejecting_a_released_quotation_returns_it_to_draft(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate_id, option_id = _draft_estimate(client, headers, project_id, project_sport_id)
    quotation_id = _released_quotation(client, headers, project_id, estimate_id, option_id)

    res = client.post(
        f"/quotations/{quotation_id}/reject",
        json={"reason_category": "margin", "note": "director wants a higher margin before this goes out"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "draft"
    assert body["released_by_id"] is None
    assert body["released_at"] is None


def test_rejecting_a_sent_quotation_returns_it_to_draft_and_clears_validity(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate_id, option_id = _draft_estimate(client, headers, project_id, project_sport_id)
    quotation_id = _released_quotation(client, headers, project_id, estimate_id, option_id)
    client.post(f"/quotations/{quotation_id}/send", headers=headers)

    res = client.post(
        f"/quotations/{quotation_id}/reject",
        json={"reason_category": "evidence_missing", "note": "no approval evidence attached yet"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "draft"
    assert body["sent_at"] is None
    assert body["expires_at"] is None


def test_rejecting_a_draft_quotation_fails(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
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

    res = client.post(
        f"/quotations/{quotation['id']}/reject",
        json={"reason_category": "other", "note": "nothing to reject"},
        headers=headers,
    )
    assert res.status_code == 400


def test_rejecting_an_unknown_quotation_404s(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/quotations/00000000-0000-0000-0000-000000000000/reject",
        json={"reason_category": "other", "note": "n/a"},
        headers=headers,
    )
    assert res.status_code == 404


def test_sales_cannot_reject_a_quotation(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, director_headers)
    project_id = _create_project(client, director_headers, client_id)
    project_sport_id = _add_project_sport(client, director_headers, project_id)
    _verified_cost_sheet(client, director_headers, project_id)
    estimate_id, option_id = _draft_estimate(client, director_headers, project_id, project_sport_id)
    quotation_id = _released_quotation(client, director_headers, project_id, estimate_id, option_id)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/quotations/{quotation_id}/reject",
        json={"reason_category": "other", "note": "n/a"},
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_rejecting_a_quotation_writes_an_audit_log_entry(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate_id, option_id = _draft_estimate(client, headers, project_id, project_sport_id)
    quotation_id = _released_quotation(client, headers, project_id, estimate_id, option_id)

    client.post(
        f"/quotations/{quotation_id}/reject",
        json={"reason_category": "scope_unclear", "note": "scope needs to be reconfirmed with client"},
        headers=headers,
    )

    entries = _audit_entries(client, headers, document_type="quotation", document_id=quotation_id)
    entry = next(e for e in entries if e["new_value"] == "draft")
    assert entry["old_value"] == "released"
    assert entry["reason"] == "scope_unclear: scope needs to be reconfirmed with client"


def test_rejected_quotation_can_be_reworked_and_rereleased(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate_id, option_id = _draft_estimate(client, headers, project_id, project_sport_id)
    quotation_id = _released_quotation(client, headers, project_id, estimate_id, option_id)

    client.post(
        f"/quotations/{quotation_id}/reject",
        json={"reason_category": "margin", "note": "rework the numbers"},
        headers=headers,
    )

    res = client.post(f"/quotations/{quotation_id}/release", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "released"


def test_all_six_reject_reason_categories_are_accepted(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)

    categories = [
        "wrong_quantities", "rate_not_confirmed", "margin",
        "scope_unclear", "evidence_missing", "other",
    ]
    for category in categories:
        # A project only ever has one active Cost Sheet, so each category
        # gets its own project.
        project_id = _create_project(client, headers, client_id)
        cost_sheet_id = _verified_cost_sheet(client, headers, project_id)
        res = client.post(
            f"/cost-sheets/{cost_sheet_id}/reject",
            json={"reason_category": category, "note": f"testing {category}"},
            headers=headers,
        )
        assert res.status_code == 200, res.text


def test_reject_requires_a_non_empty_note(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _verified_cost_sheet(client, headers, project_id)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/reject",
        json={"reason_category": "other", "note": ""},
        headers=headers,
    )
    assert res.status_code == 422
