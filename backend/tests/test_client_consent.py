from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _sales_headers(client, db_session):
    user = User(name="Test Sales", email="sales@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.SALES)
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales@test.local")


def _procurement_headers(client, db_session):
    user = User(
        name="Test Procurement", email="procurement@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.PROCUREMENT,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "procurement@test.local")


def _create_client_record(client, headers, name="Consent Client", **overrides):
    payload = {"name": name, "type": "school", **overrides}
    res = client.post("/clients", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


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


def _draft_estimate(client, headers, project_id, project_sport_id, cost_for_option=850000):
    cs_id = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_for_option}, headers=headers).json()["id"]
    client.post(f"/cost-sheets/{cs_id}/verify", headers=headers)
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": cost_for_option}]},
        headers=headers,
    ).json()
    return estimate


def _log_message(client, headers, doc_type, doc_id, **overrides):
    payload = {"doc_type": doc_type, "doc_id": doc_id, "channel": "email", "recipient": "client@example.com"}
    payload.update(overrides)
    return client.post("/messages", json=payload, headers=headers)


def test_client_defaults_to_whatsapp_opted_out_email_opted_in(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client_record(client, headers)
    assert row["whatsapp_opt_in"] is False
    assert row["email_opt_in"] is True
    assert row["consent_date"] is None


def test_whatsapp_message_blocked_without_opt_in(client, director_user):
    headers = _director_headers(client, director_user)
    client_row = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_row["id"])
    project_sport_id = _add_project_sport(client, headers, project_id)
    estimate = _draft_estimate(client, headers, project_id, project_sport_id)

    res = _log_message(client, headers, "estimate", estimate["id"], channel="whatsapp", recipient="+911234567890")
    assert res.status_code == 400
    assert "whatsapp" in res.json()["detail"].lower()


def test_whatsapp_message_allowed_after_opt_in(client, director_user):
    headers = _director_headers(client, director_user)
    client_row = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_row["id"])
    project_sport_id = _add_project_sport(client, headers, project_id)
    estimate = _draft_estimate(client, headers, project_id, project_sport_id)

    res = client.patch(
        f"/clients/{client_row['id']}/consent",
        json={"whatsapp_opt_in": True, "consent_date": "2026-09-01"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["whatsapp_opt_in"] is True

    res = _log_message(client, headers, "estimate", estimate["id"], channel="whatsapp", recipient="+911234567890")
    assert res.status_code == 201, res.text


def test_email_message_allowed_by_default(client, director_user):
    headers = _director_headers(client, director_user)
    client_row = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_row["id"])
    project_sport_id = _add_project_sport(client, headers, project_id)
    estimate = _draft_estimate(client, headers, project_id, project_sport_id)

    res = _log_message(client, headers, "estimate", estimate["id"])
    assert res.status_code == 201, res.text


def test_email_message_blocked_after_opt_out(client, director_user):
    headers = _director_headers(client, director_user)
    client_row = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_row["id"])
    project_sport_id = _add_project_sport(client, headers, project_id)
    estimate = _draft_estimate(client, headers, project_id, project_sport_id)

    client.patch(f"/clients/{client_row['id']}/consent", json={"email_opt_in": False}, headers=headers)

    res = _log_message(client, headers, "estimate", estimate["id"])
    assert res.status_code == 400
    assert "email" in res.json()["detail"].lower()


def test_quotation_messages_are_also_gated(client, director_user):
    headers = _director_headers(client, director_user)
    client_row = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_row["id"])
    project_sport_id = _add_project_sport(client, headers, project_id)
    estimate = _draft_estimate(client, headers, project_id, project_sport_id)
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

    res = _log_message(client, headers, "quotation", quotation["id"], channel="whatsapp", recipient="+911234567890")
    assert res.status_code == 400


def test_cost_sheet_messages_are_not_gated_by_client_consent(client, director_user):
    """Cost Sheet is internal-only (M.7.2 rule 7) -- there's no client
    consent question to ask for a document that never reaches the client
    at all, regardless of the client's own opt-in state. Uses an internal
    email recipient rather than WhatsApp: WhatsApp is blocked outright
    for internal documents by the (separate) internal-domain restriction
    rule, which is what this test needs to NOT be about -- that rule is
    covered on its own in test_messages.py."""
    headers = _director_headers(client, director_user)
    client_row = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_row["id"])
    cs_id = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": 850000}, headers=headers).json()["id"]

    res = _log_message(client, headers, "cost_sheet", cs_id, recipient="ops@test.local")
    assert res.status_code == 201, res.text


def test_consent_update_writes_an_audit_log_entry(client, director_user):
    headers = _director_headers(client, director_user)
    client_row = _create_client_record(client, headers)

    client.patch(f"/clients/{client_row['id']}/consent", json={"whatsapp_opt_in": True}, headers=headers)

    entries = client.get(
        "/audit-log", params={"document_type": "client", "document_id": client_row["id"]}, headers=headers
    ).json()
    entry = next(e for e in entries if e["field"] == "whatsapp_opt_in")
    assert entry["old_value"] == "False"
    assert entry["new_value"] == "True"


def test_sales_can_update_client_consent(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    client_row = _create_client_record(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.patch(
        f"/clients/{client_row['id']}/consent", json={"whatsapp_opt_in": True}, headers=sales_headers
    )
    assert res.status_code == 200, res.text


def test_procurement_cannot_update_client_consent(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    client_row = _create_client_record(client, director_headers)

    procurement_headers = _procurement_headers(client, db_session)
    res = client.patch(
        f"/clients/{client_row['id']}/consent", json={"whatsapp_opt_in": True}, headers=procurement_headers
    )
    assert res.status_code == 403
