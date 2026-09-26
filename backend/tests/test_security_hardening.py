"""Amendment 58 (Section 61): application security hardening -- the backend items.

Sessions end when the password changes, lockouts are audited, passwords need 10 characters, attachment
names and types are checked, and every route in the app needs a login unless it is on a written public list."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.api.role_permissions import _flatten
from app.config import settings
from app.core.security import ALGORITHM
from app.main import app
from app.models.audit_log import AuditLogEntry
from tests.test_attachments import (
    _create_client_record,
    _create_project,
    _director_headers,
    _draft_cost_sheet,
    _upload,
)


def _login_token(client, email, password):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _make_user(client, director_headers, email, password="TempPass!123", role="pm"):
    res = client.post(
        "/users", json={"name": "Sec User", "email": email, "role": role, "password": password}, headers=director_headers
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


# --- item 5: a session ends when the password changes -------------------------------------------


def test_changing_your_password_ends_the_old_session_and_hands_back_a_new_one(client, director_user):
    headers = _director_headers(client, director_user)
    _make_user(client, headers, "sess-change@test.local")
    old_token = _login_token(client, "sess-change@test.local", "TempPass!123")
    assert client.get("/auth/me", headers=_bearer(old_token)).status_code == 200

    res = client.post(
        "/auth/change-password",
        json={"current_password": "TempPass!123", "new_password": "BrandNewPass!9"},
        headers=_bearer(old_token),
    )
    assert res.status_code == 200, res.text
    new_token = res.json()["access_token"]
    assert res.json()["must_change_password"] is False

    assert client.get("/auth/me", headers=_bearer(old_token)).status_code == 401  # the old session is over
    assert client.get("/auth/me", headers=_bearer(new_token)).status_code == 200  # the caller carries on
    assert _login_token(client, "sess-change@test.local", "BrandNewPass!9")


def test_a_directors_reset_ends_the_persons_sessions(client, director_user):
    headers = _director_headers(client, director_user)
    user_id = _make_user(client, headers, "sess-reset@test.local")
    token = _login_token(client, "sess-reset@test.local", "TempPass!123")
    assert client.get("/auth/me", headers=_bearer(token)).status_code == 200

    reset = client.post(f"/users/{user_id}/reset-password", json={"new_password": "ResetByDirector!7"}, headers=headers)
    assert reset.status_code == 200, reset.text
    assert client.get("/auth/me", headers=_bearer(token)).status_code == 401
    assert _login_token(client, "sess-reset@test.local", "ResetByDirector!7")


def test_a_token_with_no_fingerprint_is_refused(client, director_user):
    _director_headers(client, director_user)
    forged = jwt.encode(
        {"sub": "director@test.local", "role": "director", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        settings.secret_key,
        algorithm=ALGORITHM,
    )
    assert client.get("/auth/me", headers=_bearer(forged)).status_code == 401


def test_a_deactivated_user_is_still_refused_at_once(client, director_user):
    headers = _director_headers(client, director_user)
    user_id = _make_user(client, headers, "sess-off@test.local")
    token = _login_token(client, "sess-off@test.local", "TempPass!123")
    off = client.patch(f"/users/{user_id}", json={"is_active": False}, headers=headers)
    assert off.status_code == 200, off.text
    assert client.get("/auth/me", headers=_bearer(token)).status_code == 401


# --- item 6: lockouts and password changes are recorded -----------------------------------------


def test_a_lockout_is_written_to_the_audit_log_but_wrong_passwords_and_unknown_emails_are_not(
    client, director_user, db_session
):
    headers = _director_headers(client, director_user)
    user_id = _make_user(client, headers, "lockout@test.local")
    for _ in range(5):
        assert client.post("/auth/login", data={"username": "lockout@test.local", "password": "wrong-one"}).status_code == 401
    # locked: even the right password is refused
    assert client.post("/auth/login", data={"username": "lockout@test.local", "password": "TempPass!123"}).status_code == 401
    for _ in range(6):
        client.post("/auth/login", data={"username": "nobody@test.local", "password": "x"})

    entries = db_session.query(AuditLogEntry).filter(AuditLogEntry.field == "account_lock").all()
    assert len(entries) == 1
    assert str(entries[0].document_id) == user_id and entries[0].document_type == "user"
    assert "5 wrong passwords" in entries[0].new_value
    assert db_session.query(AuditLogEntry).filter(AuditLogEntry.field == "failed_login").count() == 0


def test_a_self_service_password_change_is_recorded_without_the_password(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    _make_user(client, headers, "audit-change@test.local")
    token = _login_token(client, "audit-change@test.local", "TempPass!123")
    client.post(
        "/auth/change-password",
        json={"current_password": "TempPass!123", "new_password": "AuditedChange!5"},
        headers=_bearer(token),
    )
    rows = db_session.query(AuditLogEntry).filter(AuditLogEntry.field == "password").all()
    assert any(r.old_value == "(self-service change)" for r in rows)
    assert not any("AuditedChange" in (r.new_value or "") or "TempPass" in (r.old_value or "") for r in rows)


# --- item 7: passwords -------------------------------------------------------------------------


def test_a_password_needs_ten_characters_and_may_not_be_the_email_or_the_current_one(client, director_user):
    headers = _director_headers(client, director_user)
    nine = client.post("/users", json={"name": "N", "email": "nine@test.local", "role": "pm", "password": "Nine9chr!"}, headers=headers)
    assert nine.status_code == 422
    ten = client.post("/users", json={"name": "T", "email": "ten@test.local", "role": "pm", "password": "Ten10char!"}, headers=headers)
    assert ten.status_code == 201, ten.text
    same_as_email = client.post(
        "/users",
        json={"name": "E", "email": "email-as-pw@test.local", "role": "pm", "password": "email-as-pw@test.local"},
        headers=headers,
    )
    assert same_as_email.status_code == 400 and "same as the email" in same_as_email.json()["detail"]

    token = _login_token(client, "ten@test.local", "Ten10char!")
    same = client.post(
        "/auth/change-password", json={"current_password": "Ten10char!", "new_password": "Ten10char!"}, headers=_bearer(token)
    )
    assert same.status_code == 400 and "different from the current" in same.json()["detail"]
    email_pw = client.post(
        "/auth/change-password", json={"current_password": "Ten10char!", "new_password": "ten@test.local"}, headers=_bearer(token)
    )
    assert email_pw.status_code == 400
    short = client.post(
        "/auth/change-password", json={"current_password": "Ten10char!", "new_password": "Short9chr"}, headers=_bearer(token)
    )
    assert short.status_code == 422

    user_id = ten.json()["id"]
    assert client.post(f"/users/{user_id}/reset-password", json={"new_password": "Short9chr"}, headers=headers).status_code == 422
    same_reset = client.post(f"/users/{user_id}/reset-password", json={"new_password": "Ten10char!"}, headers=headers)
    assert same_reset.status_code == 400


# --- item 8: attachments -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "sent,stored",
    [
        ("../x.pdf", "x.pdf"),
        ("a/b.pdf", "b.pdf"),
        ("C:\\dir\\evil.pdf", "evil.pdf"),
        ("we<ird>name?.png", "weirdname.png"),
        ("site drawing (v2).dwg", "site drawing (v2).dwg"),
    ],
)
def test_an_uploaded_file_keeps_only_a_plain_name(client, director_user, sent, stored):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    res = _upload(client, headers, "cost_sheet", cost_sheet_id, "soil_report", filename=sent)
    assert res.status_code == 201, res.text
    assert res.json()["original_filename"] == stored


def test_a_very_long_file_name_is_capped_and_keeps_its_extension(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    res = _upload(client, headers, "cost_sheet", cost_sheet_id, "soil_report", filename="n" * 400 + ".pdf")
    assert res.status_code == 201, res.text
    assert len(res.json()["original_filename"]) == 150 and res.json()["original_filename"].endswith(".pdf")


@pytest.mark.parametrize("name", ["page.html", "PAGE.HTM", "logo.svg", "run.exe", "x.js", "s.sh", "m.ps1"])
def test_files_that_can_run_or_render_as_a_page_are_refused(client, director_user, name):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    res = _upload(client, headers, "cost_sheet", cost_sheet_id, "soil_report", filename=name)
    assert res.status_code == 400
    assert "can't be attached" in res.json()["detail"]
    listed = client.get("/attachments", params={"doc_type": "cost_sheet", "doc_id": cost_sheet_id}, headers=headers).json()
    assert listed == []  # nothing was stored


@pytest.mark.parametrize("name", ["drawing.pdf", "photo.JPG", "sheet.xlsx", "walkthrough.mp4", "plan.dwg", "notes.txt"])
def test_ordinary_site_files_still_upload(client, director_user, name):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    res = _upload(client, headers, "cost_sheet", cost_sheet_id, "soil_report", filename=name)
    assert res.status_code == 201, res.text


# --- item 9: every route needs a login unless it is on the written public list -----------------

# Deliberately public: the sign-in itself, the health check, the API schema and its docs pages, and the
# WhatsApp delivery webhook (it checks its own shared secret instead of a user token).
PUBLIC_ROUTES = {
    ("POST", "/auth/login"),
    ("GET", "/health"),
    ("GET", "/openapi.json"),
    ("GET", "/docs"),
    ("GET", "/docs/oauth2-redirect"),
    ("GET", "/redoc"),
}
PUBLIC_PREFIXES = ("/webhooks/",)


def _all_routes():
    # Same walk the Role & Permissions screen uses (Amendment 51): newer FastAPI nests every included
    # router inside an internal wrapper, so a plain loop over app.routes sees none of them.
    for route in _flatten(app.routes):
        for method in sorted((route.methods or set()) - {"HEAD", "OPTIONS"}):
            yield method, route.path


def test_every_route_requires_a_login_unless_it_is_on_the_public_list(client):
    placeholder = str(uuid.UUID(int=0))
    open_routes = []
    checked = 0
    for method, path in _all_routes():
        if (method, path) in PUBLIC_ROUTES or path.startswith(PUBLIC_PREFIXES):
            continue
        url = path
        for part in [p for p in path.split("/") if p.startswith("{")]:
            url = url.replace(part, placeholder)
        res = client.request(method, url)
        checked += 1
        if res.status_code != 401:
            open_routes.append(f"{method} {path} -> {res.status_code}")
    assert checked > 200  # the guard is really walking the whole app, not an empty list
    assert not open_routes, "Routes reachable without a login (add authentication, or list them as public on purpose):\n" + "\n".join(open_routes)
