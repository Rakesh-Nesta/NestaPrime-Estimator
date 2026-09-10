"""Blueprint Ledger gap #6: M.2 rule 8's small-job fast-track --
"Resurfacing / Repair jobs below Rs 2,00,000 [confirm] may go Cost Sheet
-> Quotation with a standing PM pre-approval; logged as a fast-track,
not a skip." Unlike M.2 rule 3's SkipRequest (an ad-hoc, per-instance
approval), eligibility here is a standing rule -- project_type in
(Resurfacing, Repair) and a Verified Cost Sheet total under the
Director-set fast_track_limit_rs Master Setting -- so a PM/Director can
act directly with no separate request/approve step. An Estimate and a
single, auto-approved EstimateOption are still created behind the
scenes (the data model's numbering/revision/floor-target machinery all
assumes one exists), matching the same "client-facing step is skipped,
but the underlying row still exists" pattern Tender Mode's M.2 rule 7
exception already uses."""


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _sales_headers(client, db_session):
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    user = User(name="Test Sales", email="sales-ft@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.SALES)
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales-ft@test.local")


def _create_client_record(client, headers, client_type="school", name="Fast Track Test School"):
    res = client.post("/clients", json={"name": name, "type": client_type}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_project(client, headers, client_id, **overrides):
    fields = {
        "client_id": client_id, "city": "Mumbai", "site_condition": "level", "soil_type": "normal",
        "building_status": "open_air", "site_access": "good", "power_available": "yes",
        "water_available": True, "package": "standard",
        **overrides,
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


def _verified_cost_sheet(client, headers, project_id, cost_total):
    create_res = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_total}, headers=headers)
    assert create_res.status_code == 201, create_res.text
    cost_sheet_id = create_res.json()["id"]
    verify_res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert verify_res.status_code == 200, verify_res.text
    return verify_res.json()


def _resurfacing_project_with_sport(client, headers, cost_total=150000, project_type="resurfacing"):
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id, project_type=project_type)
    _add_project_sport(client, headers, project_id)
    cost_sheet = _verified_cost_sheet(client, headers, project_id, cost_total)
    return project_id, cost_sheet


def test_fast_track_creates_quotation_with_auto_approved_estimate(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, cost_sheet = _resurfacing_project_with_sport(client, headers, cost_total=150000)

    res = client.post(
        f"/projects/{project_id}/quotations/fast-track",
        json={"cost_sheet_id": cost_sheet["id"], "package": "standard"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    quotation = res.json()
    assert quotation["fast_track_flag"] is True
    assert quotation["cost_total"] == 150000
    assert quotation["status"] == "draft"

    estimates = client.get(f"/projects/{project_id}/estimates", headers=headers).json()
    assert len(estimates) == 1
    estimate = estimates[0]
    assert estimate["client_status"] == "approved"
    assert len(estimate["options"]) == 1
    assert estimate["options"][0]["client_status"] == "approved"
    assert estimate["options"][0]["cost_for_option"] == 150000

    # Same project numbering discipline as every other document chain.
    project_no = client.get(f"/projects/{project_id}", headers=headers).json()["project_no"]
    suffix = project_no.split("-", 1)[1]
    assert estimate["document_no"] == f"EST-{suffix}-R1"
    assert quotation["document_no"] == f"NPQ-{suffix}-R1"


def test_fast_track_logs_an_audit_entry_not_a_skip_request(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, cost_sheet = _resurfacing_project_with_sport(client, headers, cost_total=100000)

    res = client.post(
        f"/projects/{project_id}/quotations/fast-track",
        json={"cost_sheet_id": cost_sheet["id"], "package": "standard"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    quotation_id = res.json()["id"]

    audit = client.get(f"/audit-log?document_type=quotation&document_id={quotation_id}", headers=headers).json()
    fast_track_entries = [e for e in audit if e["field"] == "fast_track_flag"]
    assert len(fast_track_entries) == 1
    assert fast_track_entries[0]["new_value"] == "True"
    assert "M.2 rule 8" in fast_track_entries[0]["reason"]

    skip_requests = client.get(f"/projects/{project_id}/skip-requests", headers=headers).json()
    assert skip_requests == []


def test_fast_track_rejected_for_new_build_project(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, cost_sheet = _resurfacing_project_with_sport(client, headers, cost_total=100000, project_type="new_build")

    res = client.post(
        f"/projects/{project_id}/quotations/fast-track",
        json={"cost_sheet_id": cost_sheet["id"], "package": "standard"},
        headers=headers,
    )
    assert res.status_code == 422
    assert "Resurfacing/Repair" in res.text


def test_fast_track_accepts_repair_project_type(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, cost_sheet = _resurfacing_project_with_sport(client, headers, cost_total=100000, project_type="repair")

    res = client.post(
        f"/projects/{project_id}/quotations/fast-track",
        json={"cost_sheet_id": cost_sheet["id"], "package": "standard"},
        headers=headers,
    )
    assert res.status_code == 201, res.text


def test_fast_track_rejected_at_or_above_the_default_limit(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, cost_sheet = _resurfacing_project_with_sport(client, headers, cost_total=200000)

    res = client.post(
        f"/projects/{project_id}/quotations/fast-track",
        json={"cost_sheet_id": cost_sheet["id"], "package": "standard"},
        headers=headers,
    )
    assert res.status_code == 422
    assert "fast-track limit" in res.text


def test_fast_track_rejected_when_cost_sheet_not_verified(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id, project_type="resurfacing")
    _add_project_sport(client, headers, project_id)
    draft_cs = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": 100000}, headers=headers).json()

    res = client.post(
        f"/projects/{project_id}/quotations/fast-track",
        json={"cost_sheet_id": draft_cs["id"], "package": "standard"},
        headers=headers,
    )
    assert res.status_code == 400
    assert "Verified" in res.text


def test_fast_track_rejected_for_multi_sport_projects(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id, project_type="resurfacing")
    _add_project_sport(client, headers, project_id, sport_key="badminton")
    _add_project_sport(client, headers, project_id, sport_key="table_tennis")
    cost_sheet = _verified_cost_sheet(client, headers, project_id, 100000)

    res = client.post(
        f"/projects/{project_id}/quotations/fast-track",
        json={"cost_sheet_id": cost_sheet["id"], "package": "standard"},
        headers=headers,
    )
    assert res.status_code == 422
    assert "exactly one sport" in res.text


def test_sales_cannot_use_fast_track(client, db_session):
    headers = _sales_headers(client, db_session)
    res = client.post(
        "/projects/00000000-0000-0000-0000-000000000000/quotations/fast-track",
        json={"cost_sheet_id": "00000000-0000-0000-0000-000000000000", "package": "standard"},
        headers=headers,
    )
    assert res.status_code == 403


def test_director_editable_fast_track_limit_changes_eligibility(client, director_user):
    """Q.1 'Thresholds & modes': fast-track limit is a Director-editable
    Master Setting, not hard-coded."""
    headers = _director_headers(client, director_user)
    lower_res = client.post(
        "/settings", json={"key": "fast_track_limit_rs", "value": "50000"}, headers=headers
    )
    assert lower_res.status_code == 201, lower_res.text

    project_id, cost_sheet = _resurfacing_project_with_sport(client, headers, cost_total=75000)
    res = client.post(
        f"/projects/{project_id}/quotations/fast-track",
        json={"cost_sheet_id": cost_sheet["id"], "package": "standard"},
        headers=headers,
    )
    assert res.status_code == 422
    assert "fast-track limit" in res.text

    raise_res = client.post(
        "/settings", json={"key": "fast_track_limit_rs", "value": "1000000"}, headers=headers
    )
    assert raise_res.status_code == 201, raise_res.text
    res2 = client.post(
        f"/projects/{project_id}/quotations/fast-track",
        json={"cost_sheet_id": cost_sheet["id"], "package": "standard"},
        headers=headers,
    )
    assert res2.status_code == 201, res2.text


def test_normal_quotation_path_has_fast_track_flag_false(client, director_user):
    """The ordinary Cost Sheet -> Estimate -> Quotation chain must not be
    silently marked as a fast-track."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, client_type="government", name="Fast Track Government Corp")
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet = _verified_cost_sheet(client, headers, project_id, 850000)

    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 850000}]},
        headers=headers,
    ).json()
    option_id = estimate["options"][0]["id"]
    client.patch(
        f"/estimates/{estimate['id']}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test"},
        headers=headers,
    )
    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id]},
        headers=headers,
    ).json()
    assert quotation["fast_track_flag"] is False
