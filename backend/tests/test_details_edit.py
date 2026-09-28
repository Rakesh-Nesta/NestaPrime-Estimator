"""Amendment 47 (Section 52): correcting a lead's or client's own name /
phone / email in place. Client renames are audit-logged; contact edits and
every Opportunity edit are not."""
from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _role_headers(client, db_session, role, email):
    user = User(name=f"Test {role.value}", email=email, hashed_password=hash_password("TestPass!1"), role=role)
    db_session.add(user)
    db_session.commit()
    return _login(client, email)


def _create_client_record(client, headers, **overrides):
    payload = {
        "name": "Original Name", "type": "school", "contact_name": "Asha", "phone": "9000000001",
        "email": "asha@example.com", **overrides,
    }
    res = client.post("/clients", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _satisfy_project_readiness(client, headers, project_id):
    res = client.post(f"/projects/{project_id}/scope-items/confirm-empty", headers=headers)
    assert res.status_code == 200, res.text

    survey = client.post(f"/projects/{project_id}/site-surveys", json={}, headers=headers).json()
    for i in range(4):
        res = client.post(
            "/attachments",
            data={"doc_type": "site_survey", "doc_id": survey["id"], "tag": "photo"},
            files={"file": (f"survey-photo-{i}.txt", b"photo", "text/plain")},
            headers=headers,
        )
        assert res.status_code == 201, res.text
    res = client.post(f"/site-surveys/{survey['id']}/complete", headers=headers)
    assert res.status_code == 200, res.text


def _create_opportunity(client, headers, **overrides):
    payload = {
        "lead_name": "Original Lead", "lead_phone": "9000000002", "lead_email": "lead@example.com",
        "next_follow_up_date": "2099-01-01", **overrides,
    }
    res = client.post("/opportunities", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _legitimately_won_opportunity(client, headers, lead_name="Won Lead"):
    """WP6 (correction plan, 2026-09-28, tightened after review): the only route to Won is
    Qualified -> Start Project -> Quotation marked Won -- a bare PATCH straight to Won is
    refused unconditionally now. Builds the real chain, since this file's own test
    specifically wants to prove detail-editing works at Won, not just any terminal stage."""
    client_row = _create_client_record(client, headers, name=f"{lead_name} Client")
    opp = _create_opportunity(client, headers, lead_name=lead_name, client_id=client_row["id"])
    client.patch(
        f"/opportunities/{opp['id']}/stage",
        json={"stage": "qualified", "next_follow_up_date": "2099-01-01"},
        headers=headers,
    )
    project = client.post(
        "/projects",
        json={
            "client_id": client_row["id"], "opportunity_id": opp["id"], "city": "Mumbai",
            "site_condition": "level", "soil_type": "normal", "building_status": "open_air",
            "site_access": "good", "power_available": "yes", "water_available": True, "package": "standard",
        },
        headers=headers,
    ).json()
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == "badminton")
    project_sport_id = client.post(
        f"/projects/{project['id']}/sports", json={"sport_id": sport_id, "building_status": "open_air"}, headers=headers
    ).json()["id"]
    cost_sheet_id = client.post(
        f"/projects/{project['id']}/cost-sheets", json={"cost_total": 850000}, headers=headers
    ).json()["id"]
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    _satisfy_project_readiness(client, headers, project["id"])
    estimate = client.post(
        f"/projects/{project['id']}/estimates",
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
        f"/projects/{project['id']}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id]},
        headers=headers,
    ).json()
    client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    client.post(f"/quotations/{quotation['id']}/send", headers=headers)
    won = client.post(
        f"/quotations/{quotation['id']}/mark-won",
        json={"reason": "Best offer", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert won.status_code == 200, won.text
    return client.get(f"/opportunities/{opp['id']}", headers=headers).json()


def _client_audit(client, headers, client_id):
    res = client.get("/audit-log", params={"document_type": "client", "document_id": client_id}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


# --- Opportunity details --------------------------------------------------


def test_edit_lead_details_corrects_name_phone_email(client, director_user):
    headers = _director_headers(client, director_user)
    opp = _create_opportunity(client, headers)

    res = client.patch(
        f"/opportunities/{opp['id']}/details",
        json={"lead_name": "Corrected Lead", "lead_phone": "9111111111", "lead_email": "fixed@example.com"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["lead_name"] == "Corrected Lead"
    assert body["lead_phone"] == "9111111111"
    assert body["lead_email"] == "fixed@example.com"


def test_lead_details_trims_the_name(client, director_user):
    headers = _director_headers(client, director_user)
    opp = _create_opportunity(client, headers)

    res = client.patch(f"/opportunities/{opp['id']}/details", json={"lead_name": "  Trimmed  "}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["lead_name"] == "Trimmed"


def test_lead_details_rejects_a_blank_name(client, director_user):
    headers = _director_headers(client, director_user)
    opp = _create_opportunity(client, headers)

    for blank in ("", "   "):
        res = client.patch(f"/opportunities/{opp['id']}/details", json={"lead_name": blank}, headers=headers)
        assert res.status_code == 400, res.text

    # Nothing was overwritten by the refused edits.
    assert client.get(f"/opportunities/{opp['id']}", headers=headers).json()["lead_name"] == "Original Lead"


def test_lead_details_omitted_contact_fields_are_left_unchanged(client, director_user):
    headers = _director_headers(client, director_user)
    opp = _create_opportunity(client, headers)

    res = client.patch(f"/opportunities/{opp['id']}/details", json={"lead_name": "Only Name"}, headers=headers)
    body = res.json()
    assert body["lead_phone"] == "9000000002"
    assert body["lead_email"] == "lead@example.com"


def test_lead_details_null_or_blank_clears_contact_fields(client, director_user):
    headers = _director_headers(client, director_user)
    opp = _create_opportunity(client, headers)

    res = client.patch(
        f"/opportunities/{opp['id']}/details",
        json={"lead_name": "Original Lead", "lead_phone": None, "lead_email": "   "},
        headers=headers,
    )
    body = res.json()
    assert body["lead_phone"] is None
    assert body["lead_email"] is None


def test_lead_details_editable_at_any_stage_including_won_and_lost(client, director_user):
    headers = _director_headers(client, director_user)
    won = _legitimately_won_opportunity(client, headers, lead_name="Won Lead")
    lost = _create_opportunity(client, headers, lead_name="Lost Lead")
    client.patch(f"/opportunities/{lost['id']}/stage", json={"stage": "lost", "lost_reason": "price"}, headers=headers)

    for opp, name in ((won, "Won Lead Fixed"), (lost, "Lost Lead Fixed")):
        res = client.patch(f"/opportunities/{opp['id']}/details", json={"lead_name": name}, headers=headers)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["lead_name"] == name
        # Editing details does not touch the workflow fields.
        assert body["stage"] in ("won", "lost")
        assert body["next_follow_up_date"] is None


def test_lead_details_unknown_opportunity_is_404(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.patch(
        "/opportunities/00000000-0000-0000-0000-000000000000/details", json={"lead_name": "X"}, headers=headers
    )
    assert res.status_code == 404


def test_lead_details_role_gate(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    opp = _create_opportunity(client, headers)

    sales = _role_headers(client, db_session, UserRole.SALES, "sales@test.local")
    res = client.patch(f"/opportunities/{opp['id']}/details", json={"lead_name": "By Sales"}, headers=sales)
    assert res.status_code == 200, res.text

    # Procurement can read the pipeline but not change it.
    procurement = _role_headers(client, db_session, UserRole.PROCUREMENT, "procurement@test.local")
    res = client.patch(f"/opportunities/{opp['id']}/details", json={"lead_name": "By Procurement"}, headers=procurement)
    assert res.status_code == 403


def test_lead_details_edit_is_not_audit_logged(client, director_user):
    headers = _director_headers(client, director_user)
    opp = _create_opportunity(client, headers)
    client.patch(f"/opportunities/{opp['id']}/details", json={"lead_name": "Renamed Lead"}, headers=headers)

    res = client.get("/audit-log", params={"document_type": "opportunity"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json() == []


# --- Client details -------------------------------------------------------


def test_edit_client_details(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client_record(client, headers)

    res = client.patch(
        f"/clients/{row['id']}/details",
        json={"name": "Corrected Name", "contact_name": "Asha K", "phone": "9222222222", "email": "asha.k@example.com"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["name"] == "Corrected Name"
    assert body["contact_name"] == "Asha K"
    assert body["phone"] == "9222222222"
    assert body["email"] == "asha.k@example.com"


def test_client_details_rejects_a_blank_name(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client_record(client, headers)

    for blank in ("", "   "):
        res = client.patch(f"/clients/{row['id']}/details", json={"name": blank}, headers=headers)
        assert res.status_code == 400, res.text
    assert client.get(f"/clients/{row['id']}", headers=headers).json()["name"] == "Original Name"
    assert _client_audit(client, headers, row["id"]) == []


def test_client_details_omitted_and_cleared_fields(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client_record(client, headers)

    res = client.patch(f"/clients/{row['id']}/details", json={"name": "Original Name"}, headers=headers)
    body = res.json()
    assert (body["contact_name"], body["phone"], body["email"]) == ("Asha", "9000000001", "asha@example.com")

    res = client.patch(
        f"/clients/{row['id']}/details",
        json={"name": "Original Name", "phone": None, "email": "  "},
        headers=headers,
    )
    body = res.json()
    assert body["phone"] is None
    assert body["email"] is None
    assert body["contact_name"] == "Asha"


def test_client_details_does_not_touch_type_or_flags_or_consent(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client_record(client, headers)

    # An attempt to smuggle a type change through the details endpoint is ignored.
    res = client.patch(
        f"/clients/{row['id']}/details", json={"name": "Renamed", "type": "corporate"}, headers=headers
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["type"] == "school"
    assert body["payment_terms"] == row["payment_terms"]
    assert body["whatsapp_opt_in"] == row["whatsapp_opt_in"]
    assert body["overdue_flag"] is False and body["blacklist_flag"] is False


def test_client_rename_is_audit_logged(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client_record(client, headers)

    client.patch(f"/clients/{row['id']}/details", json={"name": "Renamed Client"}, headers=headers)

    entries = _client_audit(client, headers, row["id"])
    assert len(entries) == 1
    assert entries[0]["field"] == "name"
    assert entries[0]["old_value"] == "Original Name"
    assert entries[0]["new_value"] == "Renamed Client"


def test_client_contact_edit_without_rename_is_not_audit_logged(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client_record(client, headers)

    # Same name (even with stray whitespace), only contact details change.
    client.patch(
        f"/clients/{row['id']}/details",
        json={"name": " Original Name ", "phone": "9333333333", "contact_name": "New Contact"},
        headers=headers,
    )
    assert _client_audit(client, headers, row["id"]) == []


def test_client_details_unknown_client_is_404(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.patch("/clients/00000000-0000-0000-0000-000000000000/details", json={"name": "X"}, headers=headers)
    assert res.status_code == 404


def test_client_details_role_gate(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    row = _create_client_record(client, headers)

    # Sales may correct details -- this is not the Director-only flags gate.
    sales = _role_headers(client, db_session, UserRole.SALES, "sales@test.local")
    res = client.patch(f"/clients/{row['id']}/details", json={"name": "By Sales"}, headers=sales)
    assert res.status_code == 200, res.text

    procurement = _role_headers(client, db_session, UserRole.PROCUREMENT, "procurement@test.local")
    res = client.patch(f"/clients/{row['id']}/details", json={"name": "By Procurement"}, headers=procurement)
    assert res.status_code == 403
