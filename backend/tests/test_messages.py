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
    """Cost Sheet is an internal document (M.7.2 rule 7), so the
    recipient must be on the internal-domain list -- test.local, the
    domain of the director_user fixture itself, since no explicit
    internal_email_domains Setting is configured in this test."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)

    res = _log_message(
        client, headers, "cost_sheet", cost_sheet_id, recipient="ops@test.local",
        subject="Cost sheet shared", body_note="Sent for internal review",
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["channel"] == "email"
    assert body["recipient"] == "ops@test.local"
    assert body["status"] == "recorded"
    assert body["subject"] == "Cost sheet shared"

    listed = client.get(
        "/messages", params={"doc_type": "cost_sheet", "doc_id": cost_sheet_id}, headers=headers
    ).json()
    assert len(listed) == 1
    assert listed[0]["id"] == body["id"]


def test_messages_are_independently_repeatable(client, director_user):
    """Unlike the /send status-transition endpoints, logging a message is
    not a one-time state change -- a resend or a follow-up to a
    different recipient should both be recordable. Cost Sheet can no
    longer exercise this across channels (WhatsApp is blocked outright
    for internal documents, M.7.2 rule 7) so this uses two internal
    email recipients instead; test_sales_can_log_a_message_on_an_estimate
    below covers a genuinely different channel on a client-facing doc."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)

    _log_message(client, headers, "cost_sheet", cost_sheet_id, recipient="pm@test.local")
    _log_message(client, headers, "cost_sheet", cost_sheet_id, recipient="director@test.local")

    listed = client.get(
        "/messages", params={"doc_type": "cost_sheet", "doc_id": cost_sheet_id}, headers=headers
    ).json()
    assert len(listed) == 2
    recipients = {m["recipient"] for m in listed}
    assert recipients == {"pm@test.local", "director@test.local"}


def test_whatsapp_is_blocked_outright_for_internal_documents(client, director_user):
    """M.7.1 / M.7.2 rule 7: Cost Sheet 'may be emailed only to addresses
    on the COMPANY domain list and never by WhatsApp' -- unlike the
    client-consent gate (M.7.2 rule 5), there is no opt-in that makes
    this acceptable."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)

    res = _log_message(client, headers, "cost_sheet", cost_sheet_id, channel="whatsapp", recipient="+911234567890")
    assert res.status_code == 400
    assert "whatsapp" in res.json()["detail"].lower()


def test_internal_document_email_rejected_outside_the_domain_list(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)

    res = _log_message(client, headers, "cost_sheet", cost_sheet_id, recipient="client@example.com")
    assert res.status_code == 400
    assert "internal-domain" in res.json()["detail"].lower()


def test_internal_document_email_allowed_within_the_domain_list(client, director_user):
    """No internal_email_domains Setting is configured in this test, so
    the check falls back to the domains already in use by this
    installation's own users -- test.local, from the director_user
    fixture."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)

    res = _log_message(client, headers, "cost_sheet", cost_sheet_id, recipient="accounts@test.local")
    assert res.status_code == 201, res.text


def test_internal_domain_list_can_be_configured_explicitly(client, director_user):
    """Once the Director sets internal_email_domains explicitly (Q.1
    Communications), it replaces the user-email fallback rather than
    extending it -- a domain no longer in the configured list is
    rejected even if a user happens to have that email domain."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)

    setting_res = client.post(
        "/settings",
        json={"key": "internal_email_domains", "value": "nestaprime.com", "reason": "go-live domain"},
        headers=headers,
    )
    assert setting_res.status_code == 201, setting_res.text

    still_blocked = _log_message(client, headers, "cost_sheet", cost_sheet_id, recipient="ops@test.local")
    assert still_blocked.status_code == 400

    now_allowed = _log_message(client, headers, "cost_sheet", cost_sheet_id, recipient="ops@nestaprime.com")
    assert now_allowed.status_code == 201, now_allowed.text


def test_domain_restriction_does_not_apply_to_client_facing_documents(client, director_user):
    """Estimate/Quotation are governed only by the client's own consent
    (M.7.2 rule 5), not the internal-domain list -- an external client
    email address must still work."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate_res = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 100000}]},
        headers=headers,
    )
    estimate_id = estimate_res.json()["id"]

    res = _log_message(client, headers, "estimate", estimate_id, recipient="client@example.com")
    assert res.status_code == 201, res.text


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

    res = _log_message(client, headers, "cost_sheet", cost_sheet_id, recipient="ops@test.local", attachment_id=attachment_id)
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

    res = _log_message(client, headers, "cost_sheet", cost_sheet_id, recipient="ops@test.local", attachment_id=attachment_id)
    assert res.status_code == 400


def test_message_rejects_an_unknown_attachment(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    res = _log_message(
        client, headers, "cost_sheet", cost_sheet_id, recipient="ops@test.local",
        attachment_id="00000000-0000-0000-0000-000000000000",
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


# ---------------------------------------------------------------------------
# template_id (M.7.2 rule 6 -- Director-managed MESSAGE_TEMPLATES library)
# ---------------------------------------------------------------------------


def _create_template(client, headers, channel="email", name="Quotation follow-up", **overrides):
    payload = {"channel": channel, "name": name, "body": "Hi {client_name}, your quotation is ready.", **overrides}
    res = client.post("/message-templates", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _client_facing_estimate(client, headers):
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate_res = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 100000}]},
        headers=headers,
    )
    assert estimate_res.status_code == 201, estimate_res.text
    return client_id, estimate_res.json()["id"]


def test_message_can_reference_an_approved_whatsapp_template(client, director_user):
    headers = _director_headers(client, director_user)
    client_id, estimate_id = _client_facing_estimate(client, headers)
    client.patch(f"/clients/{client_id}/consent", json={"whatsapp_opt_in": True}, headers=headers)
    template = _create_template(client, headers, channel="whatsapp", name="Estimate ready")
    client.patch(
        f"/message-templates/{template['id']}", json={"whatsapp_template_status": "approved"}, headers=headers
    )

    res = _log_message(
        client, headers, "estimate", estimate_id, channel="whatsapp", recipient="+911234567890",
        template_id=template["id"],
    )
    assert res.status_code == 201, res.text
    assert res.json()["template_id"] == template["id"]
    assert res.json()["body_note"] == template["body"]


def test_message_rejects_a_non_approved_whatsapp_template(client, director_user):
    headers = _director_headers(client, director_user)
    client_id, estimate_id = _client_facing_estimate(client, headers)
    client.patch(f"/clients/{client_id}/consent", json={"whatsapp_opt_in": True}, headers=headers)
    template = _create_template(client, headers, channel="whatsapp", name="Estimate ready")  # still draft

    res = _log_message(
        client, headers, "estimate", estimate_id, channel="whatsapp", recipient="+911234567890",
        template_id=template["id"],
    )
    assert res.status_code == 422
    assert "not meta-approved" in res.json()["detail"].lower()


def test_message_rejects_a_template_for_the_wrong_channel(client, director_user):
    headers = _director_headers(client, director_user)
    client_id, estimate_id = _client_facing_estimate(client, headers)
    client.patch(f"/clients/{client_id}/consent", json={"whatsapp_opt_in": True}, headers=headers)
    template = _create_template(client, headers, channel="email", name="Email only")

    res = _log_message(
        client, headers, "estimate", estimate_id, channel="whatsapp", recipient="+911234567890",
        template_id=template["id"],
    )
    assert res.status_code == 422
    assert "not whatsapp" in res.json()["detail"].lower()


def test_message_rejects_a_template_for_the_wrong_document_type(client, director_user):
    headers = _director_headers(client, director_user)
    _, estimate_id = _client_facing_estimate(client, headers)
    template = _create_template(
        client, headers, channel="email", name="Quotation-only", document_type="quotation"
    )

    res = _log_message(client, headers, "estimate", estimate_id, recipient="client@example.com", template_id=template["id"])
    assert res.status_code == 422
    assert "quotation" in res.json()["detail"].lower()


def test_message_rejects_an_inactive_template(client, director_user):
    headers = _director_headers(client, director_user)
    _, estimate_id = _client_facing_estimate(client, headers)
    template = _create_template(client, headers, channel="email")
    client.patch(f"/message-templates/{template['id']}", json={"is_active": False}, headers=headers)

    res = _log_message(client, headers, "estimate", estimate_id, recipient="client@example.com", template_id=template["id"])
    assert res.status_code == 422
    assert "not active" in res.json()["detail"].lower()


def test_message_rejects_an_unknown_template_id(client, director_user):
    headers = _director_headers(client, director_user)
    _, estimate_id = _client_facing_estimate(client, headers)

    res = _log_message(
        client, headers, "estimate", estimate_id, recipient="client@example.com",
        template_id="00000000-0000-0000-0000-000000000000",
    )
    assert res.status_code == 404


def test_template_subject_and_body_default_into_the_message(client, director_user):
    headers = _director_headers(client, director_user)
    _, estimate_id = _client_facing_estimate(client, headers)
    template = _create_template(
        client, headers, channel="email", name="Estimate cover note", subject="Your estimate is ready",
    )

    res = _log_message(client, headers, "estimate", estimate_id, recipient="client@example.com", template_id=template["id"])
    assert res.status_code == 201, res.text
    assert res.json()["subject"] == "Your estimate is ready"
    assert res.json()["body_note"] == template["body"]


def test_explicit_subject_overrides_the_template(client, director_user):
    headers = _director_headers(client, director_user)
    _, estimate_id = _client_facing_estimate(client, headers)
    template = _create_template(
        client, headers, channel="email", name="Estimate cover note", subject="Default subject",
    )

    res = _log_message(
        client, headers, "estimate", estimate_id, recipient="client@example.com",
        template_id=template["id"], subject="Custom subject for this send",
    )
    assert res.status_code == 201, res.text
    assert res.json()["subject"] == "Custom subject for this send"
