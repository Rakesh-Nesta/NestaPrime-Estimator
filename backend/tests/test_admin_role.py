"""Amendment 59 (Section 62): the Admin role, and who can do what.

An Admin runs the system (people, access, company identity, templates, field settings) and does not approve,
price or see cost and margin. A Director and a PM keep the business decisions; a PM may also create the four
operational roles; only an Admin creates an Admin (after the one-time start by the Director)."""

import pytest

from app.api.role_permissions import build_role_permissions
from app.main import app
from app.models.audit_log import AuditLogEntry
from app.models.user import UserRole
from tests.test_attachments import _director_headers
from tests.test_quotations_admin import _role_headers

PASSWORD = "TempPass!123"


def _user(role, email, name="Made By A Test"):
    return {"name": name, "email": email, "role": role, "password": PASSWORD}


def _admin(client, db_session, email="admin-a@test.local"):
    return _role_headers(client, db_session, UserRole.ADMIN, email)


def _pm(client, db_session, email="pm-a@test.local"):
    return _role_headers(client, db_session, UserRole.PM, email)


# --- creating people ----------------------------------------------------------------------------


def test_the_director_starts_the_first_admin_once_and_after_that_only_an_admin_creates_one(client, director_user, db_session):
    director = _director_headers(client, director_user)
    first = client.post("/users", json=_user("admin", "first-admin@test.local"), headers=director)
    assert first.status_code == 201, first.text  # the one-time start: no active Admin exists yet
    assert first.json()["role"] == "admin"

    second = client.post("/users", json=_user("admin", "second-admin@test.local"), headers=director)
    assert second.status_code == 403 and "Only an Admin can create an Admin" in second.json()["detail"]

    admin = _admin(client, db_session)
    third = client.post("/users", json=_user("admin", "third-admin@test.local"), headers=admin)
    assert third.status_code == 201, third.text


@pytest.mark.parametrize("role", ["director", "pm", "sales", "procurement", "site_engineer", "ca_tax", "admin"])
def test_an_admin_can_create_any_role(client, director_user, db_session, role):
    admin = _admin(client, db_session)
    assert client.post("/users", json=_user(role, f"by-admin-{role}@test.local"), headers=admin).status_code == 201


@pytest.mark.parametrize("role", ["director", "pm", "sales", "procurement", "site_engineer", "ca_tax"])
def test_a_director_can_create_any_role_except_admin_once_an_admin_exists(client, director_user, db_session, role):
    _admin(client, db_session)
    director = _director_headers(client, director_user)
    assert client.post("/users", json=_user(role, f"by-director-{role}@test.local"), headers=director).status_code == 201


@pytest.mark.parametrize("role", ["sales", "procurement", "site_engineer", "ca_tax"])
def test_a_pm_can_create_the_four_operational_roles(client, director_user, db_session, role):
    pm = _pm(client, db_session)
    res = client.post("/users", json=_user(role, f"by-pm-{role}@test.local"), headers=pm)
    assert res.status_code == 201, res.text
    assert res.json()["must_change_password"] is True


@pytest.mark.parametrize("role", ["director", "pm", "admin"])
def test_a_pm_can_never_create_a_director_a_pm_or_an_admin(client, director_user, db_session, role):
    pm = _pm(client, db_session)
    res = client.post("/users", json=_user(role, f"pm-refused-{role}@test.local"), headers=pm)
    assert res.status_code == 403
    assert "Sales, Procurement, Site Engineer and CA/Tax accounts only" in res.json()["detail"]


@pytest.mark.parametrize("role", [UserRole.SALES, UserRole.PROCUREMENT, UserRole.SITE_ENGINEER, UserRole.CA_TAX])
def test_the_other_roles_cannot_list_or_create_users(client, director_user, db_session, role):
    headers = _role_headers(client, db_session, role, f"nobody-{role.value}@test.local")
    assert client.get("/users", headers=headers).status_code == 403
    assert client.post("/users", json=_user("sales", "x-refused@test.local"), headers=headers).status_code == 403


def test_admin_director_and_pm_can_list_people(client, director_user, db_session):
    for headers in (_admin(client, db_session), _director_headers(client, director_user), _pm(client, db_session)):
        assert client.get("/users", headers=headers).status_code == 200


# --- managing people ----------------------------------------------------------------------------


def test_only_an_admin_or_a_director_can_manage_and_a_pm_cannot(client, director_user, db_session):
    director = _director_headers(client, director_user)
    target = client.post("/users", json=_user("sales", "manage-me@test.local"), headers=director).json()["id"]
    pm = _pm(client, db_session)
    assert client.patch(f"/users/{target}", json={"is_active": False}, headers=pm).status_code == 403
    assert client.post(f"/users/{target}/reset-password", json={"new_password": "AnotherLong!77"}, headers=pm).status_code == 403


def test_an_admin_can_manage_anyone_including_a_director_and_another_admin(client, director_user, db_session):
    admin = _admin(client, db_session)
    other_admin = client.post("/users", json=_user("admin", "other-admin@test.local"), headers=admin).json()["id"]
    assert client.patch(f"/users/{director_user.id}", json={"role": "pm"}, headers=admin).status_code in (200, 400)
    assert client.post(f"/users/{other_admin}/reset-password", json={"new_password": "ResetByAdmin!77"}, headers=admin).status_code == 200
    assert client.patch(f"/users/{other_admin}", json={"is_active": False}, headers=admin).status_code == 200


def test_a_director_cannot_touch_an_admin_and_cannot_make_one(client, director_user, db_session):
    admin = _admin(client, db_session)
    admin_id = client.get("/users", headers=admin).json()
    admin_id = next(u["id"] for u in admin_id if u["email"] == "admin-a@test.local")
    director = _director_headers(client, director_user)
    for call in (
        lambda: client.patch(f"/users/{admin_id}", json={"is_active": False}, headers=director),
        lambda: client.patch(f"/users/{admin_id}", json={"role": "pm"}, headers=director),
        lambda: client.post(f"/users/{admin_id}/reset-password", json={"new_password": "ResetByDirector!7"}, headers=director),
    ):
        res = call()
        assert res.status_code == 403 and "Only an Admin can change an Admin" in res.json()["detail"]
    someone = client.post("/users", json=_user("sales", "promote-me@test.local"), headers=director).json()["id"]
    res = client.patch(f"/users/{someone}", json={"role": "admin"}, headers=director)
    assert res.status_code == 403 and "Only an Admin can make someone an Admin" in res.json()["detail"]


def test_nobody_deactivates_or_changes_the_role_of_themselves(client, director_user, db_session):
    admin = _admin(client, db_session)
    client.post("/users", json=_user("admin", "second-admin-self@test.local"), headers=admin)  # so it is not the last one
    me = next(u["id"] for u in client.get("/users", headers=admin).json() if u["email"] == "admin-a@test.local")
    assert client.patch(f"/users/{me}", json={"is_active": False}, headers=admin).status_code == 400
    res = client.patch(f"/users/{me}", json={"role": "director"}, headers=admin)
    assert res.status_code == 400 and "own role" in res.json()["detail"]
    # ... and the sole Admin gets the more specific message


def test_a_director_creating_the_first_admin_can_also_promote_before_one_exists(client, director_user):
    director = _director_headers(client, director_user)
    person = client.post("/users", json=_user("pm", "future-admin@test.local"), headers=director).json()["id"]
    res = client.patch(f"/users/{person}", json={"role": "admin"}, headers=director)
    assert res.status_code == 200, res.text  # the one-time start, again


# --- settings: company identity only ------------------------------------------------------------


def test_an_admin_changes_company_identity_but_nothing_that_prices_or_pays(client, director_user, db_session):
    admin = _admin(client, db_session)
    ok = client.post("/settings", json={"key": "company_legal_name", "value": "Nesta Sports Pvt Ltd"}, headers=admin)
    assert ok.status_code == 201, ok.text
    for key in ("gst_rate_percent", "contingency_civil_percent", "quotation_terms_and_conditions",
                "company_bank_account_number", "company_bank_ifsc"):
        res = client.post("/settings", json={"key": key, "value": "1"}, headers=admin)
        assert res.status_code == 403, key
        assert "company-identity settings only" in res.json()["detail"]
    scoped = client.post(
        "/settings", json={"key": "company_gstin", "value": "X", "scope": "sport", "scope_value": "badminton"}, headers=admin
    )
    assert scoped.status_code == 403
    assert client.post("/settings/bulk-update", json={"key_prefix": "contingency", "percent_change": 1, "reason": "x"}, headers=admin).status_code == 403


def test_an_admin_sees_only_company_identity_in_the_settings_list_and_history(client, director_user, db_session):
    director = _director_headers(client, director_user)
    client.post("/settings", json={"key": "gst_rate_percent", "value": "18"}, headers=director)
    client.post("/settings", json={"key": "company_pan", "value": "ABCDE1234F"}, headers=director)
    admin = _admin(client, db_session)
    keys = {row["key"] for row in client.get("/settings", headers=admin).json()}
    assert "company_pan" in keys and "gst_rate_percent" not in keys
    assert client.get("/settings/company_pan/history", headers=admin).status_code == 200
    assert client.get("/settings/gst_rate_percent/history", headers=admin).status_code == 403
    assert "gst_rate_percent" in {row["key"] for row in client.get("/settings", headers=director).json()}  # unchanged for the Director


def test_the_director_keeps_every_setting(client, director_user):
    director = _director_headers(client, director_user)
    for key in ("gst_rate_percent", "company_bank_account_number", "company_legal_name"):
        assert client.post("/settings", json={"key": key, "value": "1"}, headers=director).status_code == 201


# --- the audit log: who and when, not cost or margin --------------------------------------------


def test_an_admin_reads_the_audit_log_with_cost_and_margin_values_hidden(client, director_user, db_session):
    director = _director_headers(client, director_user)
    client.post("/settings", json={"key": "gst_rate_percent", "value": "18", "reason": "budget 2026"}, headers=director)
    client.post("/settings", json={"key": "company_legal_name", "value": "Visible Name Pvt Ltd"}, headers=director)
    client.post("/users", json=_user("sales", "audited-user@test.local"), headers=director)
    admin = _admin(client, db_session)

    rows = client.get("/audit-log", headers=admin).json()
    gst = next(r for r in rows if r["document_type"] == "setting" and r["field"] == "gst_rate_percent")
    assert gst["new_value"] == "(hidden for your role)" and gst["reason"] == "(hidden for your role)"
    name = next(r for r in rows if r["field"] == "company_legal_name")
    assert name["new_value"] == "Visible Name Pvt Ltd"
    created = next(r for r in rows if r["document_type"] == "user" and r["field"] == "created")
    assert "audited-user@test.local" in created["new_value"]

    raw = client.get("/audit-log", headers=director).json()
    assert next(r for r in raw if r["field"] == "gst_rate_percent")["new_value"] == "18"  # the Director sees everything

    export = client.get("/audit-log/export", headers=admin)
    assert export.status_code == 200 and "budget 2026" not in export.text and "hidden for your role" in export.text


def test_the_admin_overview_shows_people_and_masked_recent_activity(client, director_user, db_session):
    director = _director_headers(client, director_user)
    client.post("/settings", json={"key": "gst_rate_percent", "value": "18"}, headers=director)
    admin = _admin(client, db_session)
    body = client.get("/admin/overview", headers=admin).json()
    assert body["active_users_by_role"]["admin"] >= 1 and set(body) >= {"inactive_users", "locked_accounts", "recent_activity"}
    assert all(r["new_value"] in (None, "(hidden for your role)") or r["document_type"] in ("user", "field_setting", "message_template")
               for r in body["recent_activity"] if r["field"] == "gst_rate_percent")
    assert client.get("/admin/overview", headers=director).status_code == 200
    assert client.get("/admin/overview", headers=_pm(client, db_session)).status_code == 403


# --- an Admin has no business surface ------------------------------------------------------------

# Every route an Admin may reach, spelled out: adding one here is a decision, not a side effect.
ADMIN_ROUTES = {
    ("GET", "/users"),
    ("POST", "/users"),
    ("PATCH", "/users/{user_id}"),
    ("POST", "/users/{user_id}/reset-password"),
    ("GET", "/audit-log"),
    ("GET", "/audit-log/export"),
    ("GET", "/role-permissions"),
    ("GET", "/admin/overview"),
    ("GET", "/settings"),
    ("POST", "/settings"),
    ("GET", "/settings/{key}/history"),
    ("POST", "/company/logo"),
    ("GET", "/message-templates"),
    ("POST", "/message-templates"),
    ("PATCH", "/message-templates/{template_id}"),
    ("GET", "/field-settings"),
    ("PATCH", "/field-settings/{field_key}"),
}


def test_the_routes_an_admin_can_reach_are_exactly_the_administration_routes(client):
    table = build_role_permissions(app.routes)
    reachable = {
        (item.method, item.path)
        for area in table.areas
        for group in area.groups
        if "admin" in group.roles
        for item in group.items
    }
    assert reachable == ADMIN_ROUTES, (reachable - ADMIN_ROUTES, ADMIN_ROUTES - reachable)


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/clients"), ("GET", "/projects"), ("GET", "/opportunities"), ("GET", "/dashboard"),
        ("GET", "/search?q=school"), ("GET", "/quotations"), ("GET", "/quotations/export"), ("GET", "/rate-items"),
        ("GET", "/reports/summary"), ("GET", "/sports"), ("GET", "/payments/overview"), ("GET", "/vendors"),
    ],
)
def test_an_admin_is_refused_every_business_screen(client, director_user, db_session, method, path):
    admin = _admin(client, db_session)
    assert client.request(method, path, headers=admin).status_code in (403, 404, 405), path


def test_the_role_table_lists_seven_roles(client, director_user):
    director = _director_headers(client, director_user)
    table = client.get("/role-permissions", headers=director).json()
    assert table["roles"] == ["sales", "pm", "director", "procurement", "site_engineer", "ca_tax", "admin"]


def test_an_admin_can_also_read_the_role_table_but_a_pm_cannot(client, director_user, db_session):
    assert client.get("/role-permissions", headers=_admin(client, db_session)).status_code == 200
    assert client.get("/role-permissions", headers=_pm(client, db_session)).status_code == 403


def test_the_sole_admin_cannot_be_demoted_even_by_themselves(client, director_user, db_session):
    admin = _admin(client, db_session, "sole-admin@test.local")
    me = next(u["id"] for u in client.get("/users", headers=admin).json() if u["email"] == "sole-admin@test.local")
    res = client.patch(f"/users/{me}", json={"role": "pm"}, headers=admin)
    assert res.status_code == 400 and "last active Admin" in res.json()["detail"]
