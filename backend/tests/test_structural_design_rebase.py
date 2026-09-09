import io

from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _sales_headers(client, db_session, email="sales@test.local"):
    user = User(name="Test Sales", email=email, hashed_password=hash_password("TestPass!1"), role=UserRole.SALES)
    db_session.add(user)
    db_session.commit()
    return _login(client, email), email


def _create_client_record(client, headers, name="Structural Rebase Client"):
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


def _cost_sheet(client, headers, project_id, cost_total=850000):
    return client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_total}, headers=headers
    ).json()["id"]


def _verify(client, headers, cost_sheet_id):
    res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _draft_estimate(client, headers, project_id, project_sport_id, cost_for_option=850000):
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": cost_for_option}]},
        headers=headers,
    ).json()
    return estimate["id"], estimate["options"][0]["id"]


def _upload_structural_design(client, headers, cost_sheet_id, filename="engineer_design.pdf"):
    return client.post(
        "/attachments",
        data={"doc_type": "cost_sheet", "doc_id": cost_sheet_id, "tag": "structural_design"},
        files={"file": (filename, io.BytesIO(b"%PDF-1.4 fake engineer design"), "application/pdf")},
        headers=headers,
    )


def _cost_sheets_for(client, headers, project_id):
    res = client.get(f"/projects/{project_id}/cost-sheets", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def test_uploading_structural_design_creates_new_cost_sheet_revision(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _cost_sheet(client, headers, project_id)
    _verify(client, headers, cost_sheet_id)

    res = _upload_structural_design(client, headers, cost_sheet_id)
    assert res.status_code == 201, res.text

    sheets = _cost_sheets_for(client, headers, project_id)
    assert len(sheets) == 2
    old = next(s for s in sheets if s["id"] == cost_sheet_id)
    new = next(s for s in sheets if s["id"] != cost_sheet_id)
    assert old["status"] == "superseded"
    assert new["status"] == "draft"
    assert new["revision_major"] == old["revision_major"] + 1
    assert new["cost_total"] == old["cost_total"]


def test_no_new_revision_when_cost_sheet_is_not_verified(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _cost_sheet(client, headers, project_id)

    res = _upload_structural_design(client, headers, cost_sheet_id)
    assert res.status_code == 201, res.text

    sheets = _cost_sheets_for(client, headers, project_id)
    assert len(sheets) == 1
    assert sheets[0]["status"] == "draft"


def test_no_trigger_for_a_different_attachment_tag(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _cost_sheet(client, headers, project_id)
    _verify(client, headers, cost_sheet_id)

    res = client.post(
        "/attachments",
        data={"doc_type": "cost_sheet", "doc_id": cost_sheet_id, "tag": "drawing"},
        files={"file": ("drawing.pdf", io.BytesIO(b"%PDF-1.4 fake drawing"), "application/pdf")},
        headers=headers,
    )
    assert res.status_code == 201, res.text

    sheets = _cost_sheets_for(client, headers, project_id)
    assert len(sheets) == 1
    assert sheets[0]["status"] == "verified"


def test_uploading_structural_design_flags_the_estimate_rebase_required(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = _cost_sheet(client, headers, project_id)
    _verify(client, headers, cost_sheet_id)
    estimate_id, _ = _draft_estimate(client, headers, project_id, project_sport_id)

    fresh = client.get(f"/estimates/{estimate_id}", headers=headers).json()
    assert fresh["cost_basis_rebase_required"] is False

    _upload_structural_design(client, headers, cost_sheet_id)

    stale = client.get(f"/estimates/{estimate_id}", headers=headers).json()
    assert stale["cost_basis_rebase_required"] is True


def test_uploading_structural_design_notifies_every_sales_user(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    _, sales_email_1 = _sales_headers(client, db_session, email="sales1@test.local")
    _, sales_email_2 = _sales_headers(client, db_session, email="sales2@test.local")
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = _cost_sheet(client, headers, project_id)
    _verify(client, headers, cost_sheet_id)
    estimate_id, _ = _draft_estimate(client, headers, project_id, project_sport_id)

    _upload_structural_design(client, headers, cost_sheet_id)

    res = client.get("/messages", params={"doc_type": "estimate", "doc_id": estimate_id}, headers=headers)
    assert res.status_code == 200, res.text
    messages = res.json()
    assert len(messages) == 2
    recipients = {m["recipient"] for m in messages}
    assert recipients == {sales_email_1, sales_email_2}
    for m in messages:
        assert m["template_key"] == "structural_rebase_required"
        assert "rebase" in m["body_note"].lower()
        assert "already Sent" not in m["body_note"]


def test_notification_mentions_major_revision_when_estimate_already_sent(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    _sales_headers(client, db_session)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = _cost_sheet(client, headers, project_id)
    _verify(client, headers, cost_sheet_id)
    estimate_id, _ = _draft_estimate(client, headers, project_id, project_sport_id)
    res = client.post(f"/estimates/{estimate_id}/send", headers=headers)
    assert res.status_code == 200, res.text

    _upload_structural_design(client, headers, cost_sheet_id)

    messages = client.get(
        "/messages", params={"doc_type": "estimate", "doc_id": estimate_id}, headers=headers
    ).json()
    assert len(messages) == 1
    assert "already Sent" in messages[0]["body_note"]


def test_no_estimates_means_no_messages_but_still_revises(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    _sales_headers(client, db_session)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _cost_sheet(client, headers, project_id)
    _verify(client, headers, cost_sheet_id)

    res = _upload_structural_design(client, headers, cost_sheet_id)
    assert res.status_code == 201, res.text

    sheets = _cost_sheets_for(client, headers, project_id)
    assert len(sheets) == 2


def test_supersede_also_triggers_the_rebase(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _cost_sheet(client, headers, project_id)

    res = client.post(
        "/attachments",
        data={"doc_type": "cost_sheet", "doc_id": cost_sheet_id, "tag": "drawing"},
        files={"file": ("drawing.pdf", io.BytesIO(b"%PDF-1.4 fake drawing"), "application/pdf")},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    attachment_id = res.json()["id"]

    _verify(client, headers, cost_sheet_id)

    res = client.post(
        f"/attachments/{attachment_id}/supersede",
        data={"tag": "structural_design"},
        files={"file": ("engineer_design_v2.pdf", io.BytesIO(b"%PDF-1.4 revised design"), "application/pdf")},
        headers=headers,
    )
    assert res.status_code == 201, res.text

    sheets = _cost_sheets_for(client, headers, project_id)
    assert len(sheets) == 2
    assert any(s["status"] == "superseded" for s in sheets)
    assert any(s["status"] == "draft" for s in sheets)


def test_uploading_structural_design_writes_an_audit_log_entry(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _cost_sheet(client, headers, project_id)
    _verify(client, headers, cost_sheet_id)

    _upload_structural_design(client, headers, cost_sheet_id)

    entries = client.get(
        "/audit-log", params={"document_type": "cost_sheet", "document_id": cost_sheet_id}, headers=headers
    ).json()
    entry = next(e for e in entries if e["field"] == "status" and e["new_value"] == "superseded")
    assert "structural engineer design" in entry["reason"].lower()
