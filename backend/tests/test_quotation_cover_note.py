"""Amendment 13 (Section 12): Quotation.cover_note -- AI can draft it
(POST .../draft-cover-note, never persists), a human saves it
(PATCH .../cover-note). No network access in tests -- app.services.ai_content
is monkeypatched, same discipline as test_wa_gateway_integration.py."""

from app.api import documents as documents_api
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.services.ai_content import AiContentError


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _sales_headers(client, db_session):
    user = User(
        name="Test Sales", email="sales-covernote@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.SALES,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales-covernote@test.local")


def _create_client_record(client, headers, name="Cover Note Client"):
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


def _quotation_for_new_project(client, headers, client_name="Cover Note Client"):
    client_id = _create_client_record(client, headers, client_name)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate = client.post(
        f"/projects/{project_id}/estimates",
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
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id]},
        headers=headers,
    ).json()
    return quotation["id"]


def test_cover_note_requires_auth(client):
    assert client.patch("/quotations/00000000-0000-0000-0000-000000000000/cover-note", json={}).status_code == 401
    assert client.post("/quotations/00000000-0000-0000-0000-000000000000/draft-cover-note").status_code == 401


def test_sales_can_save_a_cover_note_and_it_appears_on_the_quotation(client, director_user, db_session):
    """Cost-sheet/quotation creation needs the stricter COST_ROLES gate
    elsewhere in this project, so the quotation itself is set up as
    Director -- this test is specifically about DOCUMENT_ROLES covering
    Sales for the cover-note save action."""
    director_headers = _director_headers(client, director_user)
    quotation_id = _quotation_for_new_project(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.patch(
        f"/quotations/{quotation_id}/cover-note",
        json={"cover_note": "Thank you for considering us."},
        headers=sales_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["cover_note"] == "Thank you for considering us."

    fetched = client.get(f"/quotations/{quotation_id}", headers=sales_headers)
    assert fetched.json()["cover_note"] == "Thank you for considering us."


def test_cover_note_can_be_cleared_back_to_null(client, director_user):
    headers = _director_headers(client, director_user)
    quotation_id = _quotation_for_new_project(client, headers)
    client.patch(f"/quotations/{quotation_id}/cover-note", json={"cover_note": "Draft text"}, headers=headers)

    res = client.patch(f"/quotations/{quotation_id}/cover-note", json={"cover_note": None}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["cover_note"] is None


def test_draft_cover_note_not_configured_fails_fast(client, director_user, monkeypatch):
    """Forces the key unset regardless of the real environment's own
    .env (a dev/local .env may carry a real ANTHROPIC_API_KEY for manual
    testing) -- the real ai_content.generate_text must still fail
    immediately with a clear 503, never a hang or a 500."""
    from app.config import settings

    monkeypatch.setattr(settings, "anthropic_api_key", "")
    headers = _director_headers(client, director_user)
    quotation_id = _quotation_for_new_project(client, headers)

    res = client.post(f"/quotations/{quotation_id}/draft-cover-note", headers=headers)
    assert res.status_code == 503
    assert "not configured" in res.json()["detail"].lower()


def test_draft_cover_note_success_returns_draft_without_saving(client, director_user, monkeypatch):
    headers = _director_headers(client, director_user)
    quotation_id = _quotation_for_new_project(client, headers, client_name="Draft Success Client")

    captured_prompt = {}

    def _fake_generate_text(prompt, max_tokens=400):
        captured_prompt["prompt"] = prompt
        return "A warm two-sentence introduction."

    monkeypatch.setattr(documents_api.ai_content, "generate_text", _fake_generate_text)

    res = client.post(f"/quotations/{quotation_id}/draft-cover-note", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json() == {"draft": "A warm two-sentence introduction."}
    assert "Draft Success Client" in captured_prompt["prompt"]

    # Never persisted by the draft endpoint itself.
    fetched = client.get(f"/quotations/{quotation_id}", headers=headers)
    assert fetched.json()["cover_note"] is None


def test_draft_cover_note_service_failure_surfaces_as_503(client, director_user, monkeypatch):
    headers = _director_headers(client, director_user)
    quotation_id = _quotation_for_new_project(client, headers)

    def _boom(prompt, max_tokens=400):
        raise AiContentError("AI drafting returned 401: invalid api key")

    monkeypatch.setattr(documents_api.ai_content, "generate_text", _boom)

    res = client.post(f"/quotations/{quotation_id}/draft-cover-note", headers=headers)
    assert res.status_code == 503
    assert "invalid api key" in res.json()["detail"].lower()
