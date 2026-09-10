"""M.7.2 rule 6: 'Director-managed library of message templates per
document and channel ... WhatsApp templates are submitted to Meta for
approval through the provider; only approved templates are used.'"""

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


def _pm_headers(client, db_session):
    user = User(
        name="Test PM", email="pm-templates@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.PM
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "pm-templates@test.local")


def _create_template(client, headers, channel="whatsapp", name="Quotation follow-up", **overrides):
    payload = {
        "channel": channel, "name": name, "body": "Hi {client_name}, your quotation is ready.",
        **overrides,
    }
    res = client.post("/message-templates", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def test_message_template_catalog_starts_empty(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.get("/message-templates", headers=headers)
    assert res.status_code == 200
    assert res.json() == []


def test_director_can_create_a_whatsapp_template_starting_as_draft(client, director_user):
    headers = _director_headers(client, director_user)
    template = _create_template(client, headers, channel="whatsapp")
    assert template["whatsapp_template_status"] == "draft"
    assert template["version"] == 1
    assert template["is_active"] is True
    assert template["language"] == "en"


def test_director_can_create_an_email_template_with_no_whatsapp_status(client, director_user):
    headers = _director_headers(client, director_user)
    template = _create_template(
        client, headers, channel="email", name="Quotation email", subject="Your NestaPrime quotation"
    )
    assert template["whatsapp_template_status"] is None
    assert template["subject"] == "Your NestaPrime quotation"


def test_sales_cannot_create_a_message_template(client, director_user, db_session):
    _director_headers(client, director_user)
    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        "/message-templates",
        json={"channel": "email", "name": "X", "body": "Y"},
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_pm_cannot_create_a_message_template(client, director_user, db_session):
    """M.4's own rights table: 'Manage templates ... Director only.'"""
    _director_headers(client, director_user)
    pm_headers = _pm_headers(client, db_session)
    res = client.post(
        "/message-templates",
        json={"channel": "email", "name": "X", "body": "Y"},
        headers=pm_headers,
    )
    assert res.status_code == 403


def test_sales_can_list_message_templates(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    _create_template(client, headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.get("/message-templates", headers=sales_headers)
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_duplicate_name_and_channel_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    _create_template(client, headers, channel="email", name="Reminder")

    res = client.post(
        "/message-templates", json={"channel": "email", "name": "Reminder", "body": "x"}, headers=headers
    )
    assert res.status_code == 409


def test_same_name_is_allowed_on_a_different_channel(client, director_user):
    headers = _director_headers(client, director_user)
    _create_template(client, headers, channel="email", name="Reminder")

    res = client.post(
        "/message-templates", json={"channel": "whatsapp", "name": "Reminder", "body": "x"}, headers=headers
    )
    assert res.status_code == 201, res.text


def test_editing_content_increments_version(client, director_user):
    headers = _director_headers(client, director_user)
    template = _create_template(client, headers, channel="email")

    res = client.patch(
        f"/message-templates/{template['id']}", json={"body": "Updated body"}, headers=headers
    )
    assert res.status_code == 200, res.text
    assert res.json()["version"] == 2
    assert res.json()["body"] == "Updated body"


def test_editing_metadata_only_does_not_increment_version(client, director_user):
    headers = _director_headers(client, director_user)
    template = _create_template(client, headers, channel="email")

    res = client.patch(
        f"/message-templates/{template['id']}", json={"language": "hi"}, headers=headers
    )
    assert res.status_code == 200, res.text
    assert res.json()["version"] == 1


def test_editing_content_resets_an_approved_whatsapp_template_to_draft(client, director_user):
    headers = _director_headers(client, director_user)
    template = _create_template(client, headers, channel="whatsapp")
    client.patch(
        f"/message-templates/{template['id']}", json={"whatsapp_template_status": "approved"}, headers=headers
    )

    res = client.patch(
        f"/message-templates/{template['id']}", json={"body": "New wording"}, headers=headers
    )
    assert res.status_code == 200, res.text
    assert res.json()["whatsapp_template_status"] == "draft"
    assert res.json()["version"] == 2


def test_content_edit_with_an_explicit_new_status_does_not_get_overridden(client, director_user):
    headers = _director_headers(client, director_user)
    template = _create_template(client, headers, channel="whatsapp")

    res = client.patch(
        f"/message-templates/{template['id']}",
        json={"body": "Resubmitted wording", "whatsapp_template_status": "submitted"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["whatsapp_template_status"] == "submitted"


def test_whatsapp_template_status_rejected_for_an_email_template(client, director_user):
    headers = _director_headers(client, director_user)
    template = _create_template(client, headers, channel="email")

    res = client.patch(
        f"/message-templates/{template['id']}", json={"whatsapp_template_status": "approved"}, headers=headers
    )
    assert res.status_code == 422


def test_filter_by_channel_and_document_type(client, director_user):
    headers = _director_headers(client, director_user)
    _create_template(client, headers, channel="email", name="A")
    _create_template(client, headers, channel="whatsapp", name="B", document_type="quotation")

    email_only = client.get("/message-templates", params={"channel": "email"}, headers=headers).json()
    assert {t["name"] for t in email_only} == {"A"}

    quotation_only = client.get(
        "/message-templates", params={"document_type": "quotation"}, headers=headers
    ).json()
    assert {t["name"] for t in quotation_only} == {"B"}


def test_deactivated_template_excluded_by_default(client, director_user):
    headers = _director_headers(client, director_user)
    template = _create_template(client, headers)
    client.patch(f"/message-templates/{template['id']}", json={"is_active": False}, headers=headers)

    active = client.get("/message-templates", headers=headers).json()
    assert active == []
    all_templates = client.get("/message-templates?include_inactive=true", headers=headers).json()
    assert len(all_templates) == 1


def test_renaming_to_a_duplicate_name_and_channel_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    _create_template(client, headers, channel="email", name="Existing")
    other = _create_template(client, headers, channel="email", name="Other")

    res = client.patch(f"/message-templates/{other['id']}", json={"name": "Existing"}, headers=headers)
    assert res.status_code == 409


def test_unknown_template_404s_on_update(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.patch(
        "/message-templates/00000000-0000-0000-0000-000000000000", json={"name": "x"}, headers=headers
    )
    assert res.status_code == 404
