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


def _create_client_record(client, headers, client_type="school", name="Audit Log Client"):
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


def _draft_estimate(client, headers, project_id, project_sport_id, cost_for_option=850000):
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": cost_for_option}]},
        headers=headers,
    ).json()
    return estimate["id"], estimate["options"][0]["id"]


def _audit_entries(client, headers, **params):
    res = client.get("/audit-log", params=params, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


# ---------------------------------------------------------------------------
# Settings changes (Q.2 rule 7: "Settings changes are in the audit log")
# ---------------------------------------------------------------------------


def test_creating_a_setting_writes_an_audit_log_entry(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/settings", json={"key": "gst_rate_percent", "value": "20.0", "reason": "GST rate change"}, headers=headers
    )
    assert res.status_code == 201, res.text

    entries = _audit_entries(client, headers, document_type="setting")
    assert len(entries) == 1
    entry = entries[0]
    assert entry["field"] == "gst_rate_percent"
    assert entry["new_value"] == "20.0"
    assert entry["reason"] == "GST rate change"
    assert entry["old_value"] is None  # no prior value existed


def test_a_second_setting_version_records_the_prior_value_as_old_value(client, director_user):
    headers = _director_headers(client, director_user)
    client.post("/settings", json={"key": "gst_rate_percent", "value": "18.0"}, headers=headers)
    client.post("/settings", json={"key": "gst_rate_percent", "value": "20.0", "reason": "rate revised"}, headers=headers)

    entries = _audit_entries(client, headers, document_type="setting")
    assert len(entries) == 2
    latest = entries[0]  # newest first
    assert latest["old_value"] == "18.0"
    assert latest["new_value"] == "20.0"


def test_bulk_update_writes_one_audit_entry_per_changed_setting(client, director_user):
    headers = _director_headers(client, director_user)
    client.post("/settings", json={"key": "steel_rate_per_kg", "value": "70"}, headers=headers)
    client.post("/settings", json={"key": "steel_wastage_percent", "value": "5"}, headers=headers)

    res = client.post(
        "/settings/bulk-update",
        json={"key_prefix": "steel_", "percent_change": 6.0, "reason": "vendor deal"},
        headers=headers,
    )
    assert res.status_code == 200, res.text

    entries = _audit_entries(client, headers, document_type="setting")
    bulk_entries = [e for e in entries if e["reason"] == "vendor deal"]
    assert len(bulk_entries) == 2
    fields = {e["field"] for e in bulk_entries}
    assert fields == {"steel_rate_per_kg", "steel_wastage_percent"}


# ---------------------------------------------------------------------------
# Estimate-option approvals + approval-evidence waivers (M.5)
# ---------------------------------------------------------------------------


def test_approving_an_estimate_option_writes_an_audit_log_entry(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate_id, option_id = _draft_estimate(client, headers, project_id, project_sport_id)

    res = client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "client confirmed on call"},
        headers=headers,
    )
    assert res.status_code == 200, res.text

    entries = _audit_entries(client, headers, document_type="estimate_option", document_id=option_id)
    status_entry = next(e for e in entries if e["field"] == "client_status")
    assert status_entry["old_value"] == "pending"
    assert status_entry["new_value"] == "approved"

    waiver_entries = _audit_entries(client, headers, document_type="estimate")
    waiver_entry = next(e for e in waiver_entries if e["field"] == "approval_evidence_waiver")
    assert waiver_entry["document_id"] == estimate_id
    assert waiver_entry["reason"] == "client confirmed on call"


def test_no_waiver_entry_when_real_evidence_is_used_instead(client, director_user, db_session):
    """The waiver audit entry should only appear when a waiver actually
    happened -- not every approval goes through one."""
    import io

    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate_id, option_id = _draft_estimate(client, headers, project_id, project_sport_id)

    client.post(
        "/attachments",
        data={"doc_type": "estimate", "doc_id": estimate_id, "tag": "approval_evidence", "approval_strength": "formal"},
        files={"file": ("evidence.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
        headers=headers,
    )
    client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "approved"},
        headers=headers,
    )

    entries = _audit_entries(client, headers, document_type="estimate", document_id=estimate_id)
    assert all(e["field"] != "approval_evidence_waiver" for e in entries)


# ---------------------------------------------------------------------------
# Quotation discounts and below-floor Director release (M.5: "discounts")
# ---------------------------------------------------------------------------


def test_quotation_with_a_discount_writes_an_audit_log_entry(client, director_user):
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
        json={
            "estimate_id": estimate_id, "included_option_ids": [option_id],
            "discount_type": "amount", "discount_value": 20000,
        },
        headers=headers,
    ).json()

    entries = _audit_entries(client, headers, document_type="quotation", document_id=quotation["id"])
    discount_entry = next(e for e in entries if e["field"] == "discount_value")
    assert discount_entry["new_value"] == "20000.0"
    assert "amount" in discount_entry["reason"]


def test_quotation_without_a_discount_writes_no_discount_audit_entry(client, director_user):
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

    entries = _audit_entries(client, headers, document_type="quotation", document_id=quotation["id"])
    assert all(e["field"] != "discount_value" for e in entries)


def test_below_floor_director_release_writes_an_audit_log_entry(client, director_user):
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
        json={
            "estimate_id": estimate_id, "included_option_ids": [option_id],
            "discount_type": "amount", "discount_value": 200000,  # pushes margin below floor
        },
        headers=headers,
    ).json()
    assert quotation["below_floor"] is True

    res = client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    assert res.status_code == 200, res.text

    entries = _audit_entries(client, headers, document_type="quotation", document_id=quotation["id"])
    release_entry = next(e for e in entries if e["field"] == "status" and e["new_value"] == "released")
    assert "below_floor" in release_entry["reason"]


def test_normal_release_above_floor_writes_no_release_audit_entry(client, director_user):
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
    assert quotation["below_floor"] is False

    client.post(f"/quotations/{quotation['id']}/release", headers=headers)

    entries = _audit_entries(client, headers, document_type="quotation", document_id=quotation["id"])
    assert all(not (e["field"] == "status" and e["new_value"] == "released") for e in entries)


# ---------------------------------------------------------------------------
# Skip-request approvals (M.5: "skips")
# ---------------------------------------------------------------------------


def test_approving_a_skip_request_writes_an_audit_log_entry(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    req = client.post(
        f"/projects/{project_id}/skip-requests",
        json={"stage_skipped": "cost_sheet", "reason": "client wants a quotation directly"},
        headers=headers,
    ).json()
    client.post(f"/skip-requests/{req['id']}/approve", json={"cost_total": 500000}, headers=headers)

    entries = _audit_entries(client, headers, document_type="skip_request", document_id=req["id"])
    assert len(entries) == 1
    assert entries[0]["new_value"] == "approved"
    assert entries[0]["reason"] == "client wants a quotation directly"


# ---------------------------------------------------------------------------
# Access control and filtering
# ---------------------------------------------------------------------------


def test_pm_cannot_view_the_audit_log(client, director_user, db_session):
    """M.5: 'Exportable for Director review' is the only role the
    blueprint ever names -- treated as Director-only end to end."""
    director_headers = _director_headers(client, director_user)
    client.post("/settings", json={"key": "gst_rate_percent", "value": "18"}, headers=director_headers)

    pm_headers = _pm_headers(client, db_session)
    res = client.get("/audit-log", headers=pm_headers)
    assert res.status_code == 403


def test_pm_cannot_export_the_audit_log(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    pm_headers = _pm_headers(client, db_session)
    res = client.get("/audit-log/export", headers=pm_headers)
    assert res.status_code == 403


def test_audit_log_export_returns_csv(client, director_user):
    headers = _director_headers(client, director_user)
    client.post("/settings", json={"key": "gst_rate_percent", "value": "18", "reason": "init"}, headers=headers)

    res = client.get("/audit-log/export", headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    text = res.content.decode()
    assert "timestamp,user_id,role,document_type" in text
    assert "gst_rate_percent" in text


def test_audit_log_filters_by_document_type_and_id(client, director_user):
    headers = _director_headers(client, director_user)
    client.post("/settings", json={"key": "gst_rate_percent", "value": "18"}, headers=headers)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    req = client.post(
        f"/projects/{project_id}/skip-requests",
        json={"stage_skipped": "cost_sheet", "reason": "test"},
        headers=headers,
    ).json()
    client.post(f"/skip-requests/{req['id']}/approve", json={"cost_total": 100000}, headers=headers)

    all_entries = _audit_entries(client, headers)
    assert len(all_entries) == 2

    setting_only = _audit_entries(client, headers, document_type="setting")
    assert len(setting_only) == 1

    skip_only = _audit_entries(client, headers, document_id=req["id"])
    assert len(skip_only) == 1
    assert skip_only[0]["document_type"] == "skip_request"


def test_audit_log_endpoints_require_auth(client):
    assert client.get("/audit-log").status_code == 401
    assert client.get("/audit-log/export").status_code == 401
