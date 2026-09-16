"""Amendment 13 (Section 12): POST /reports/{report_id}/summary -- a
narrative paragraph over a report's own already-computed content, never
persisted. Same T.2 rule 3 gate (role matches VISIBLE_ROLES for that
report_type) as GET /reports/{report_id}. No network access in tests --
app.api.reports.ai_content is monkeypatched, same discipline as
test_wa_gateway_integration.py."""

from datetime import UTC, datetime

from app.api import reports as reports_api
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.services.ai_content import AiContentError

TODAY = datetime.now(UTC).date().isoformat()


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _pm_headers(client, db_session):
    user = User(name="Test PM", email="pm-summary@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.PM)
    db_session.add(user)
    db_session.commit()
    return _login(client, "pm-summary@test.local")


def _sales_headers(client, db_session):
    user = User(
        name="Test Sales", email="sales-summary@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.SALES,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales-summary@test.local")


def _pipeline_report(client, headers):
    res = client.post(
        "/reports/generate", json={"report_type": "pipeline", "period_from": TODAY, "period_to": TODAY}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _margin_report(client, headers):
    res = client.post(
        "/reports/generate", json={"report_type": "margin", "period_from": TODAY, "period_to": TODAY}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_summary_requires_auth(client):
    res = client.post("/reports/00000000-0000-0000-0000-000000000000/summary")
    assert res.status_code == 401


def test_summary_not_found(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post("/reports/00000000-0000-0000-0000-000000000000/summary", headers=headers)
    assert res.status_code == 404


def test_summary_not_configured_fails_fast(client, director_user, monkeypatch):
    """Forces the key unset regardless of the real environment's own
    .env (a dev/local .env may carry a real ANTHROPIC_API_KEY for manual
    testing) -- this must fail immediately with a clear 503 either way."""
    from app.config import settings

    monkeypatch.setattr(settings, "anthropic_api_key", "")
    headers = _director_headers(client, director_user)
    report_id = _pipeline_report(client, headers)

    res = client.post(f"/reports/{report_id}/summary", headers=headers)
    assert res.status_code == 503
    assert "not configured" in res.json()["detail"].lower()


def test_sales_cannot_summarize_a_margin_report(client, director_user, db_session):
    """Same T.2 rule 3 gate as viewing the report itself -- a summary
    reveals nothing the report doesn't already show, so it inherits the
    identical role restriction rather than a broader one."""
    director_headers = _director_headers(client, director_user)
    report_id = _margin_report(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(f"/reports/{report_id}/summary", headers=sales_headers)
    assert res.status_code == 403


def test_pm_can_summarize_a_pipeline_report(client, director_user, db_session, monkeypatch):
    director_headers = _director_headers(client, director_user)
    report_id = _pipeline_report(client, director_headers)

    monkeypatch.setattr(reports_api.ai_content, "generate_text", lambda prompt, max_tokens=500: "A quiet period overall.")

    pm_headers = _pm_headers(client, db_session)
    res = client.post(f"/reports/{report_id}/summary", headers=pm_headers)
    assert res.status_code == 200, res.text
    assert res.json() == {"summary": "A quiet period overall."}


def test_summary_never_persists_onto_the_report(client, director_user, monkeypatch):
    headers = _director_headers(client, director_user)
    report_id = _pipeline_report(client, headers)

    monkeypatch.setattr(reports_api.ai_content, "generate_text", lambda prompt, max_tokens=500: "Summary text.")
    client.post(f"/reports/{report_id}/summary", headers=headers)

    fetched = client.get(f"/reports/{report_id}", headers=headers)
    assert "summary" not in fetched.json()
    assert "Summary text." not in fetched.json()["content"]


def test_summary_service_failure_surfaces_as_503(client, director_user, monkeypatch):
    headers = _director_headers(client, director_user)
    report_id = _pipeline_report(client, headers)

    def _boom(prompt, max_tokens=500):
        raise AiContentError("AI drafting returned 401: invalid api key")

    monkeypatch.setattr(reports_api.ai_content, "generate_text", _boom)

    res = client.post(f"/reports/{report_id}/summary", headers=headers)
    assert res.status_code == 503
    assert "invalid api key" in res.json()["detail"].lower()
