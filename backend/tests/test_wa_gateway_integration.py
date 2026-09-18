"""Amendment 8 (Section 8) + its Section 17 continuation: real WhatsApp
(wa-gateway) / Telegram / Email (SMTP) sending, delivery status,
placeholder rendering, and the wa-gateway webhook.

Every provider call is monkeypatched -- no network access in tests, same
discipline as the rest of this suite. Monkeypatching the functions
imported into app.api.messages (not the ones in app.services.wa_gateway/
telegram/email_gateway) matches how `from app.services import
email_gateway, telegram, wa_gateway` resolves calls through that module
reference.
"""

from app.api import messages as messages_api
from app.config import settings
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.services.email_gateway import EmailGatewayError
from app.services.telegram import TelegramError
from app.services.wa_gateway import WaGatewayError


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


def _create_client_record(client, headers, name="WA Gateway Client"):
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


def _verified_cost_sheet(client, headers, project_id, cost_total=850000):
    create_res = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_total}, headers=headers)
    assert create_res.status_code == 201, create_res.text
    verify_res = client.post(f"/cost-sheets/{create_res.json()['id']}/verify", headers=headers)
    assert verify_res.status_code == 200, verify_res.text


def _client_facing_estimate(client, headers, client_name="WA Gateway Client"):
    client_id = _create_client_record(client, headers, name=client_name)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate_res = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 850000}]},
        headers=headers,
    )
    assert estimate_res.status_code == 201, estimate_res.text
    return client_id, project_id, estimate_res.json()["id"]


def _approved_quotation(client, headers, client_name="WA Gateway Client"):
    client_id, project_id, estimate_id = _client_facing_estimate(client, headers, client_name)
    estimate = client.get(f"/estimates/{estimate_id}", headers=headers).json()
    option_id = estimate["options"][0]["id"]
    client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    res = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate_id, "included_option_ids": [option_id]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return client_id, res.json()["id"]


def _opt_in_whatsapp(client, headers, client_id):
    res = client.patch(f"/clients/{client_id}/consent", json={"whatsapp_opt_in": True}, headers=headers)
    assert res.status_code == 200, res.text


def _opt_in_telegram(client, headers, client_id, chat_id="123456789"):
    res = client.patch(
        f"/clients/{client_id}/consent", json={"telegram_opt_in": True, "telegram_chat_id": chat_id}, headers=headers
    )
    assert res.status_code == 200, res.text


# ---------------------------------------------------------------------------
# WhatsApp -- success / failure / provider id
# ---------------------------------------------------------------------------


def test_whatsapp_send_success_sets_sent_status_and_provider_id(client, director_user, monkeypatch):
    headers = _director_headers(client, director_user)
    client_id, _, estimate_id = _client_facing_estimate(client, headers)
    _opt_in_whatsapp(client, headers, client_id)

    monkeypatch.setattr(messages_api.wa_gateway, "send_text", lambda to, text: "wamid.ABC123")

    res = client.post(
        "/messages",
        json={
            "doc_type": "estimate", "doc_id": estimate_id, "channel": "whatsapp",
            "recipient": "+911234567890", "body_note": "Hi, your estimate is ready.",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "sent"
    assert body["provider_message_id"] == "wamid.ABC123"


def test_whatsapp_send_failure_sets_failed_status_but_still_records(client, director_user, monkeypatch):
    """M.7.2 rule 1: every send creates a MESSAGES record -- even one
    that failed to actually deliver."""
    headers = _director_headers(client, director_user)
    client_id, _, estimate_id = _client_facing_estimate(client, headers)
    _opt_in_whatsapp(client, headers, client_id)

    def _boom(to, text):
        raise WaGatewayError("instance not connected")

    monkeypatch.setattr(messages_api.wa_gateway, "send_text", _boom)

    res = client.post(
        "/messages",
        json={"doc_type": "estimate", "doc_id": estimate_id, "channel": "whatsapp", "recipient": "+911234567890"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "failed"
    assert body["provider_message_id"] is None


def test_whatsapp_not_configured_fails_fast_without_network(client, director_user):
    """No monkeypatch here -- the real app.services.wa_gateway.send_text
    runs, and with WA_GATEWAY_BASE_URL unset in the test environment it
    must fail immediately (WaGatewayError), never attempt a real
    request."""
    headers = _director_headers(client, director_user)
    client_id, _, estimate_id = _client_facing_estimate(client, headers)
    _opt_in_whatsapp(client, headers, client_id)

    res = client.post(
        "/messages",
        json={"doc_type": "estimate", "doc_id": estimate_id, "channel": "whatsapp", "recipient": "+911234567890"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "failed"


# ---------------------------------------------------------------------------
# Telegram -- success / consent / internal-doc gate
# ---------------------------------------------------------------------------


def test_telegram_send_success_sets_sent_status_and_provider_id(client, director_user, monkeypatch):
    headers = _director_headers(client, director_user)
    client_id, _, estimate_id = _client_facing_estimate(client, headers)
    _opt_in_telegram(client, headers, client_id)

    monkeypatch.setattr(messages_api.telegram, "send_text", lambda chat_id, text: "998877")

    res = client.post(
        "/messages",
        json={"doc_type": "estimate", "doc_id": estimate_id, "channel": "telegram", "recipient": "123456789"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "sent"
    assert res.json()["provider_message_id"] == "998877"


def test_telegram_send_failure_sets_failed_status(client, director_user, monkeypatch):
    headers = _director_headers(client, director_user)
    client_id, _, estimate_id = _client_facing_estimate(client, headers)
    _opt_in_telegram(client, headers, client_id)

    def _boom(chat_id, text):
        raise TelegramError("chat not found")

    monkeypatch.setattr(messages_api.telegram, "send_text", _boom)

    res = client.post(
        "/messages",
        json={"doc_type": "estimate", "doc_id": estimate_id, "channel": "telegram", "recipient": "999999999"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "failed"


def test_telegram_requires_client_consent(client, director_user):
    """Same M.7.2 rule 5 opt-in discipline as WhatsApp -- a client with
    telegram_opt_in still False (the default) can't be Telegram-messaged."""
    headers = _director_headers(client, director_user)
    _, _, estimate_id = _client_facing_estimate(client, headers)

    res = client.post(
        "/messages",
        json={"doc_type": "estimate", "doc_id": estimate_id, "channel": "telegram", "recipient": "123456789"},
        headers=headers,
    )
    assert res.status_code == 400
    assert "telegram" in res.json()["detail"].lower()


def test_telegram_blocked_outright_for_internal_documents(client, director_user):
    """Same absolute internal-document gate as WhatsApp (M.7.1/M.7.2
    rule 7) -- Cost Sheet may never go by Telegram either."""
    headers = _director_headers(client, director_user)
    cs_res = client.post(
        "/projects",
        json={
            "client_id": _create_client_record(client, headers), "city": "Mumbai", "site_condition": "level",
            "soil_type": "normal", "building_status": "open_air", "site_access": "good",
            "power_available": "yes", "water_available": True, "package": "standard",
        },
        headers=headers,
    )
    project_id = cs_res.json()["id"]
    cost_sheet = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": 100000}, headers=headers)

    res = client.post(
        "/messages",
        json={
            "doc_type": "cost_sheet", "doc_id": cost_sheet.json()["id"], "channel": "telegram",
            "recipient": "123456789",
        },
        headers=headers,
    )
    assert res.status_code == 400
    assert "telegram" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# include_document -- generated PDF attachment
# ---------------------------------------------------------------------------


def test_include_document_sends_the_generated_pdf_via_whatsapp(client, director_user, monkeypatch):
    headers = _director_headers(client, director_user)
    client_id, _, estimate_id = _client_facing_estimate(client, headers)
    _opt_in_whatsapp(client, headers, client_id)

    captured = {}

    def _fake_send_media(to, document_type, base64_content, filename, mimetype, caption=None):
        captured["to"] = to
        captured["document_type"] = document_type
        captured["filename"] = filename
        captured["mimetype"] = mimetype
        return "wamid.DOC1"

    def _fail_send_text(to, text):
        raise AssertionError("send_text should not be called when include_document=True")

    monkeypatch.setattr(messages_api.wa_gateway, "send_media", _fake_send_media)
    monkeypatch.setattr(messages_api.wa_gateway, "send_text", _fail_send_text)

    res = client.post(
        "/messages",
        json={
            "doc_type": "estimate", "doc_id": estimate_id, "channel": "whatsapp",
            "recipient": "+911234567890", "include_document": True,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "sent"
    assert captured["document_type"] == "document"
    assert captured["mimetype"] == "application/pdf"
    assert captured["filename"].endswith(".pdf")


def test_include_document_rejected_for_a_doc_type_with_no_pdf(client, director_user):
    headers = _director_headers(client, director_user)
    project_res = client.post(
        "/projects",
        json={
            "client_id": _create_client_record(client, headers), "city": "Mumbai", "site_condition": "level",
            "soil_type": "normal", "building_status": "open_air", "site_access": "good",
            "power_available": "yes", "water_available": True, "package": "standard",
        },
        headers=headers,
    )
    cost_sheet = client.post(
        f"/projects/{project_res.json()['id']}/cost-sheets", json={"cost_total": 100000}, headers=headers
    )

    res = client.post(
        "/messages",
        json={
            "doc_type": "cost_sheet", "doc_id": cost_sheet.json()["id"], "channel": "email",
            "recipient": "ops@test.local", "include_document": True,
        },
        headers=headers,
    )
    assert res.status_code == 422
    assert "no generated document" in res.json()["detail"].lower()


def test_attachment_id_takes_precedence_over_include_document(client, director_user, monkeypatch):
    headers = _director_headers(client, director_user)
    client_id, _, estimate_id = _client_facing_estimate(client, headers)
    _opt_in_whatsapp(client, headers, client_id)

    upload_res = client.post(
        "/attachments",
        data={"doc_type": "estimate", "doc_id": estimate_id, "tag": "photo"},
        files={"file": ("signed.pdf", b"fake pdf bytes", "application/pdf")},
        headers=headers,
    )
    attachment_id = upload_res.json()["id"]

    captured = {}
    monkeypatch.setattr(
        messages_api.wa_gateway, "send_media",
        lambda to, document_type, base64_content, filename, mimetype, caption=None: captured.update(filename=filename) or "wamid.X",
    )

    res = client.post(
        "/messages",
        json={
            "doc_type": "estimate", "doc_id": estimate_id, "channel": "whatsapp", "recipient": "+911234567890",
            "attachment_id": attachment_id, "include_document": True,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert captured["filename"] == "signed.pdf"


# ---------------------------------------------------------------------------
# Placeholder rendering
# ---------------------------------------------------------------------------


def test_placeholders_are_rendered_against_the_real_document_for_a_real_send(client, director_user, monkeypatch):
    headers = _director_headers(client, director_user)
    client_id, quotation_id = _approved_quotation(client, headers, client_name="Placeholder Academy")
    _opt_in_whatsapp(client, headers, client_id)

    captured = {}
    monkeypatch.setattr(
        messages_api.wa_gateway, "send_text",
        lambda to, text: captured.update(text=text) or "wamid.RENDER1",
    )

    res = client.post(
        "/messages",
        json={
            "doc_type": "quotation", "doc_id": quotation_id, "channel": "whatsapp", "recipient": "+911234567890",
            "body_note": "Hi {client_name}, your quotation {quotation_number} for Rs {amount} is ready. See {unknown_token}.",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text

    # The stored record keeps the literal template text, unchanged.
    assert "{client_name}" in res.json()["body_note"]

    # The text actually sent is rendered against the real quotation.
    rendered = captured["text"]
    assert "Placeholder Academy" in rendered
    assert "{client_name}" not in rendered
    assert "{quotation_number}" not in rendered
    assert "{amount}" not in rendered
    assert "{unknown_token}" in rendered  # unresolved placeholders stay literal, never crash


# ---------------------------------------------------------------------------
# wa-gateway delivery-status webhook
# ---------------------------------------------------------------------------


def test_wa_gateway_webhook_requires_the_configured_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "wa_gateway_webhook_secret", "correct-secret")

    wrong = client.post(
        "/integrations/wa-gateway/webhook",
        json={"event": "message.sent", "data": {"msgId": "wamid.ABC"}},
        headers={"X-Webhook-Secret": "wrong-secret"},
    )
    assert wrong.status_code == 401

    missing = client.post(
        "/integrations/wa-gateway/webhook", json={"event": "message.sent", "data": {"msgId": "wamid.ABC"}}
    )
    assert missing.status_code == 401


def test_wa_gateway_webhook_reconciles_a_matching_message(client, director_user, db_session, monkeypatch):
    from app.models.message import Message, MessageChannel, MessageStatus
    from app.models.setting import DocumentType

    headers = _director_headers(client, director_user)
    monkeypatch.setattr(settings, "wa_gateway_webhook_secret", "correct-secret")

    message = Message(
        doc_type=DocumentType.ESTIMATE, doc_id=director_user.id, channel=MessageChannel.WHATSAPP,
        recipient="+911234567890", sender_id=director_user.id, status=MessageStatus.RECORDED,
        provider_message_id="wamid.WEBHOOK1",
    )
    db_session.add(message)
    db_session.commit()

    res = client.post(
        "/integrations/wa-gateway/webhook",
        json={"event": "message.sent", "data": {"msgId": "wamid.WEBHOOK1"}},
        headers={"X-Webhook-Secret": "correct-secret"},
    )
    assert res.status_code == 200, res.text

    db_session.refresh(message)
    assert message.status == MessageStatus.SENT


def test_wa_gateway_webhook_ignores_unmatched_events(client, monkeypatch):
    monkeypatch.setattr(settings, "wa_gateway_webhook_secret", "correct-secret")

    res = client.post(
        "/integrations/wa-gateway/webhook",
        json={"event": "message.sent", "data": {"msgId": "no-such-message"}},
        headers={"X-Webhook-Secret": "correct-secret"},
    )
    assert res.status_code == 200
    assert res.json() == {"ok": True}


def test_wa_gateway_webhook_ignores_other_event_types(client, monkeypatch):
    monkeypatch.setattr(settings, "wa_gateway_webhook_secret", "correct-secret")

    res = client.post(
        "/integrations/wa-gateway/webhook",
        json={"event": "message.received", "data": {"msgId": "wamid.INBOUND"}},
        headers={"X-Webhook-Secret": "correct-secret"},
    )
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# Email (Section 17) -- success / failure / not configured / attachment
# ---------------------------------------------------------------------------


def test_email_send_success_sets_sent_status(client, director_user, monkeypatch):
    """Client.email_opt_in defaults True (an opt-out model, unlike
    WhatsApp/Telegram's opt-in default), so no consent helper is needed
    here the way _opt_in_whatsapp/_opt_in_telegram are."""
    headers = _director_headers(client, director_user)
    _, _, estimate_id = _client_facing_estimate(client, headers)

    monkeypatch.setattr(messages_api.email_gateway, "send_email", lambda *a, **kw: None)

    res = client.post(
        "/messages",
        json={
            "doc_type": "estimate", "doc_id": estimate_id, "channel": "email",
            "recipient": "client@example.com", "subject": "Your estimate", "body_note": "Please find it attached.",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "sent"
    # SMTP gives no provider message id the way wa-gateway/Telegram's own APIs do.
    assert body["provider_message_id"] is None


def test_email_send_failure_sets_failed_status(client, director_user, monkeypatch):
    headers = _director_headers(client, director_user)
    _, _, estimate_id = _client_facing_estimate(client, headers)

    def _boom(to, subject, body, attachment_bytes=None, attachment_filename=None):
        raise EmailGatewayError("SMTP authentication failed")

    monkeypatch.setattr(messages_api.email_gateway, "send_email", _boom)

    res = client.post(
        "/messages",
        json={"doc_type": "estimate", "doc_id": estimate_id, "channel": "email", "recipient": "client@example.com"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "failed"


def test_email_not_configured_fails_fast_without_network(client, director_user):
    """No monkeypatch here -- the real app.services.email_gateway.send_email
    runs, and with SMTP_HOST/USERNAME/PASSWORD unset in the test
    environment it must fail immediately (EmailGatewayError), never
    attempt a real SMTP connection."""
    headers = _director_headers(client, director_user)
    _, _, estimate_id = _client_facing_estimate(client, headers)

    res = client.post(
        "/messages",
        json={"doc_type": "estimate", "doc_id": estimate_id, "channel": "email", "recipient": "client@example.com"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "failed"


def test_email_requires_client_consent(client, director_user, db_session):
    """Same M.7.2 rule 5 gate as WhatsApp/Telegram, but email defaults
    opted-in -- this test explicitly opts a client out first."""
    headers = _director_headers(client, director_user)
    client_id, _, estimate_id = _client_facing_estimate(client, headers)
    res = client.patch(f"/clients/{client_id}/consent", json={"email_opt_in": False}, headers=headers)
    assert res.status_code == 200, res.text

    res = client.post(
        "/messages",
        json={"doc_type": "estimate", "doc_id": estimate_id, "channel": "email", "recipient": "client@example.com"},
        headers=headers,
    )
    assert res.status_code == 400
    assert "email" in res.json()["detail"].lower()


def test_include_document_sends_the_generated_pdf_via_email(client, director_user, monkeypatch):
    headers = _director_headers(client, director_user)
    _, _, estimate_id = _client_facing_estimate(client, headers)

    captured = {}

    def _fake_send_email(to, subject, body, attachment_bytes=None, attachment_filename=None):
        captured["attachment_bytes"] = attachment_bytes
        captured["attachment_filename"] = attachment_filename

    monkeypatch.setattr(messages_api.email_gateway, "send_email", _fake_send_email)

    res = client.post(
        "/messages",
        json={
            "doc_type": "estimate", "doc_id": estimate_id, "channel": "email",
            "recipient": "client@example.com", "include_document": True,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "sent"
    assert captured["attachment_bytes"] is not None
    assert captured["attachment_filename"].endswith(".pdf")
