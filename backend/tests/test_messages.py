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


def _procurement_headers(client, db_session):
    user = User(
        name="Test Procurement", email="procurement@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.PROCUREMENT,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "procurement@test.local")


def _create_client_record(client, headers):
    res = client.post("/clients", json={"name": "Messages Client", "type": "school"}, headers=headers)
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


def _draft_cost_sheet(client, headers):
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    res = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": 100000}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _add_project_sport(client, headers, project_id, sport_key="badminton"):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports", json={"sport_id": sport_id, "building_status": "open_air"}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _verified_cost_sheet(client, headers, project_id, cost_total=100000):
    create_res = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_total}, headers=headers)
    assert create_res.status_code == 201, create_res.text
    cost_sheet_id = create_res.json()["id"]
    verify_res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert verify_res.status_code == 200, verify_res.text
    return cost_sheet_id


def _log_message(client, headers, doc_type, doc_id, **overrides):
    payload = {"doc_type": doc_type, "doc_id": doc_id, "channel": "email", "recipient": "client@example.com"}
    payload.update(overrides)
    return client.post("/messages", json=payload, headers=headers)


# ---------------------------------------------------------------------------
# Create / list
# ---------------------------------------------------------------------------


def test_log_and_list_a_message(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)

    res = _log_message(
        client, headers, "cost_sheet", cost_sheet_id,
        subject="Cost sheet shared", body_note="Sent for internal review",
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["channel"] == "email"
    assert body["recipient"] == "client@example.com"
    assert body["status"] == "recorded"
    assert body["subject"] == "Cost sheet shared"

    listed = client.get(
        "/messages", params={"doc_type": "cost_sheet", "doc_id": cost_sheet_id}, headers=headers
    ).json()
    assert len(listed) == 1
    assert listed[0]["id"] == body["id"]


def test_messages_are_independently_repeatable(client, director_user):
    """Unlike the /send status-transition endpoints, logging a message is
    not a one-time state change -- a resend or a follow-up on a different
    channel should both be recordable."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)

    _log_message(client, headers, "cost_sheet", cost_sheet_id, channel="email")
    _log_message(client, headers, "cost_sheet", cost_sheet_id, channel="whatsapp", recipient="+911234567890")

    listed = client.get(
        "/messages", params={"doc_type": "cost_sheet", "doc_id": cost_sheet_id}, headers=headers
    ).json()
    assert len(listed) == 2
    channels = {m["channel"] for m in listed}
    assert channels == {"email", "whatsapp"}


def test_message_requires_the_document_to_exist(client, director_user):
    headers = _director_headers(client, director_user)
    res = _log_message(client, headers, "cost_sheet", "00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404


def test_message_rejects_empty_recipient(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    res = _log_message(client, headers, "cost_sheet", cost_sheet_id, recipient="")
    assert res.status_code == 422


def test_message_can_reference_an_existing_attachment(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    upload_res = client.post(
        "/attachments",
        data={"doc_type": "cost_sheet", "doc_id": cost_sheet_id, "tag": "photo"},
        files={"file": ("site.jpg", b"fake image bytes", "image/jpeg")},
        headers=headers,
    )
    attachment_id = upload_res.json()["id"]

    res = _log_message(client, headers, "cost_sheet", cost_sheet_id, attachment_id=attachment_id)
    assert res.status_code == 201, res.text
    assert res.json()["attachment_id"] == attachment_id


def test_message_rejects_an_attachment_from_a_different_document(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    other_cost_sheet_id = _draft_cost_sheet(client, headers)
    upload_res = client.post(
        "/attachments",
        data={"doc_type": "cost_sheet", "doc_id": other_cost_sheet_id, "tag": "photo"},
        files={"file": ("site.jpg", b"fake image bytes", "image/jpeg")},
        headers=headers,
    )
    attachment_id = upload_res.json()["id"]

    res = _log_message(client, headers, "cost_sheet", cost_sheet_id, attachment_id=attachment_id)
    assert res.status_code == 400


def test_message_rejects_an_unknown_attachment(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    res = _log_message(
        client, headers, "cost_sheet", cost_sheet_id, attachment_id="00000000-0000-0000-0000-000000000000"
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Role gates -- mirrors attachments.py's own split
# ---------------------------------------------------------------------------


def test_sales_cannot_log_a_message_on_a_cost_sheet(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = _log_message(client, sales_headers, "cost_sheet", cost_sheet_id)
    assert res.status_code == 403


def test_sales_can_log_a_message_on_an_estimate(client, director_user, db_session):
    """Estimate/Quotation follow the document-editing roles (M.4), which
    include Sales -- unlike Cost Sheet, which stays cost-gated."""
    director_headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, director_headers)
    project_id = _create_project(client, director_headers, client_id)
    project_sport_id = _add_project_sport(client, director_headers, project_id)
    _verified_cost_sheet(client, director_headers, project_id)
    estimate_res = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 100000}]},
        headers=director_headers,
    )
    assert estimate_res.status_code == 201, estimate_res.text
    estimate_id = estimate_res.json()["id"]

    sales_headers = _sales_headers(client, db_session)
    res = _log_message(client, sales_headers, "estimate", estimate_id, recipient="client@example.com")
    assert res.status_code == 201, res.text


def test_procurement_cannot_log_a_message(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)

    procurement_headers = _procurement_headers(client, db_session)
    res = _log_message(client, procurement_headers, "cost_sheet", cost_sheet_id)
    assert res.status_code == 403


def test_messages_require_auth(client):
    res = client.get("/messages", params={"doc_type": "cost_sheet", "doc_id": "00000000-0000-0000-0000-000000000000"})
    assert res.status_code == 401
