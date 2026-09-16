"""Amendment 13 (Section 12): POST /messages/draft -- AI can draft the
message note, but never saves or sends anything itself; the person still
reviews/edits it and clicks the existing Send button. No network access
in tests -- app.api.messages.ai_content is monkeypatched, same
discipline as test_wa_gateway_integration.py."""

from app.api import messages as messages_api
from app.core.security import hash_password
from app.models.message import Message
from app.models.user import User, UserRole
from app.services.ai_content import AiContentError


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _procurement_headers(client, db_session):
    user = User(
        name="Test Procurement", email="procurement-draft@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.PROCUREMENT,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "procurement-draft@test.local")


def _create_client_record(client, headers, name="Message Draft Client"):
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
    cost_sheet_id = client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_total}, headers=headers
    ).json()["id"]
    res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert res.status_code == 200, res.text


def _client_facing_estimate(client, headers, client_name="Message Draft Client"):
    client_id = _create_client_record(client, headers, client_name)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 850000}]},
        headers=headers,
    ).json()
    return estimate["id"]


def test_draft_message_requires_auth(client):
    res = client.post(
        "/messages/draft",
        json={"doc_type": "estimate", "doc_id": "00000000-0000-0000-0000-000000000000", "channel": "email"},
    )
    assert res.status_code == 401


def test_draft_message_not_configured_fails_fast(client, director_user, monkeypatch):
    """Forces the key unset regardless of the real environment's own
    .env (a dev/local .env may carry a real ANTHROPIC_API_KEY for manual
    testing) -- this must fail immediately with a clear 503 either way."""
    from app.config import settings

    monkeypatch.setattr(settings, "anthropic_api_key", "")
    headers = _director_headers(client, director_user)
    estimate_id = _client_facing_estimate(client, headers)

    res = client.post(
        "/messages/draft", json={"doc_type": "estimate", "doc_id": estimate_id, "channel": "whatsapp"}, headers=headers
    )
    assert res.status_code == 503
    assert "not configured" in res.json()["detail"].lower()


def test_draft_message_success_returns_draft_and_creates_no_message_record(client, director_user, monkeypatch, db_session):
    headers = _director_headers(client, director_user)
    estimate_id = _client_facing_estimate(client, headers, client_name="Draft Message Success Client")

    captured_prompt = {}

    def _fake_generate_text(prompt, max_tokens=400):
        captured_prompt["prompt"] = prompt
        return "Hi! Your estimate is ready whenever you'd like to take a look."

    monkeypatch.setattr(messages_api.ai_content, "generate_text", _fake_generate_text)

    res = client.post(
        "/messages/draft", json={"doc_type": "estimate", "doc_id": estimate_id, "channel": "whatsapp"}, headers=headers
    )
    assert res.status_code == 200, res.text
    assert res.json() == {"draft": "Hi! Your estimate is ready whenever you'd like to take a look."}
    assert "Draft Message Success Client" in captured_prompt["prompt"]
    assert "WhatsApp/Telegram" in captured_prompt["prompt"]

    # The draft endpoint never creates a Message record -- only a real
    # POST /messages send does.
    assert db_session.query(Message).count() == 0


def test_draft_message_service_failure_surfaces_as_503(client, director_user, monkeypatch):
    headers = _director_headers(client, director_user)
    estimate_id = _client_facing_estimate(client, headers)

    def _boom(prompt, max_tokens=400):
        raise AiContentError("AI drafting returned 401: invalid api key")

    monkeypatch.setattr(messages_api.ai_content, "generate_text", _boom)

    res = client.post(
        "/messages/draft", json={"doc_type": "estimate", "doc_id": estimate_id, "channel": "email"}, headers=headers
    )
    assert res.status_code == 503
    assert "invalid api key" in res.json()["detail"].lower()


def test_draft_message_respects_the_same_doc_type_role_gate_as_a_real_send(client, db_session, director_user, monkeypatch):
    """Procurement can't manage Estimate messages for the same reason it
    can't send them for real (M.4/DOCUMENT_ROLES) -- drafting text
    shouldn't be a backdoor around that gate."""
    director_headers = _director_headers(client, director_user)
    estimate_id = _client_facing_estimate(client, director_headers)

    procurement_headers = _procurement_headers(client, db_session)
    res = client.post(
        "/messages/draft",
        json={"doc_type": "estimate", "doc_id": estimate_id, "channel": "email"},
        headers=procurement_headers,
    )
    assert res.status_code == 403
