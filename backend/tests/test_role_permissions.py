"""Amendment 51 (Section 55): the Director's "who can do what" screen is generated
from the live route table (require_roles tags its dependency with the roles it
enforces), so it cannot drift from the code the way the old hand-kept mirror did.

These tests pin known gates and compare completeness with OpenAPI -- an
independent list of routes -- so a FastAPI upgrade that changes the internals
the generator reads fails here, loudly, and not silently on the Director's screen."""
from fastapi import Depends

from app.core.auth import require_roles
from app.core.security import hash_password
from app.main import app
from app.models.user import User, UserRole

ALL_ROLES = ["sales", "pm", "director", "procurement", "site_engineer", "ca_tax", "admin"]  # Amendment 59: a seventh role


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _role_headers(client, db_session, role, email):
    user = User(name=f"Test {role.value}", email=email, hashed_password=hash_password("TestPass!1"), role=role)
    db_session.add(user)
    db_session.commit()
    return _login(client, email)


def _fetch(client, director_user):
    res = client.get("/role-permissions", headers=_director_headers(client, director_user))
    assert res.status_code == 200, res.text
    return res.json()


def _gated_lookup(body):
    """{(method, path): (roles, label)} for every gated route."""
    lookup = {}
    for area in body["areas"]:
        for group in area["groups"]:
            for item in group["items"]:
                key = (item["method"], item["path"])
                assert key not in lookup, f"{key} listed twice"
                lookup[key] = (group["roles"], item["label"])
    return lookup


# --- the tag on the gate ----------------------------------------------------


def test_require_roles_exposes_the_roles_it_enforces():
    dependency = require_roles("pm", "director")
    assert dependency.allowed_roles == ("pm", "director")


# --- who may read it --------------------------------------------------------


def test_only_the_director_can_read_role_permissions(client, director_user, db_session):
    assert client.get("/role-permissions").status_code == 401
    for role, email in (
        (UserRole.SALES, "sales-rp@test.local"),
        (UserRole.PM, "pm-rp@test.local"),
        (UserRole.PROCUREMENT, "proc-rp@test.local"),
        (UserRole.SITE_ENGINEER, "eng-rp@test.local"),
        (UserRole.CA_TAX, "ca-rp@test.local"),
    ):
        headers = _role_headers(client, db_session, role, email)
        assert client.get("/role-permissions", headers=headers).status_code == 403, role
    assert client.get("/role-permissions", headers=_director_headers(client, director_user)).status_code == 200


# --- shape ------------------------------------------------------------------


def test_the_response_lists_the_seven_roles_and_counts_its_routes(client, director_user):
    body = _fetch(client, director_user)
    assert body["roles"] == ALL_ROLES
    listed = sum(len(g["items"]) for a in body["areas"] for g in a["groups"])
    assert body["gated_route_count"] == listed > 100
    for area in body["areas"]:
        for group in area["groups"]:
            assert group["roles"], "a gate with no roles"
            assert set(group["roles"]) <= set(ALL_ROLES)
            assert group["roles"] == [r for r in ALL_ROLES if r in group["roles"]]  # canonical order


# --- completeness, against an independent list ------------------------------


def test_every_route_openapi_knows_about_is_listed_exactly_once(client, director_user):
    body = _fetch(client, director_user)
    gated = set(_gated_lookup(body))
    ungated = {(u["method"], u["path"]) for u in body["ungated"]}
    assert not (gated & ungated), "a route is both gated and ungated"
    assert len(ungated) == len(body["ungated"]), "an ungated route is listed twice"

    documented = set()
    for path, methods in app.openapi()["paths"].items():
        for method in methods:
            if method.upper() not in ("HEAD", "OPTIONS"):
                documented.add((method.upper(), path))
    assert gated | ungated == documented


# --- known gates, hard-coded from the code ----------------------------------


def test_known_gates_match_the_code(client, director_user):
    lookup = _gated_lookup(_fetch(client, director_user))
    expected = {
        ("GET", "/payments"): ["pm", "director", "ca_tax"],  # Amendment 50: CA/Tax reads
        ("GET", "/work-orders/{work_order_id}/payment-milestones"): ["pm", "director", "ca_tax"],
        ("POST", "/work-orders/{work_order_id}/payment-milestones"): ["pm", "director"],
        ("POST", "/settings"): ["director", "admin"],  # Amendment 59: an Admin, company identity only
        ("GET", "/settings"): ["pm", "director", "admin"],
        ("POST", "/users"): ["pm", "director", "admin"],  # Amendment 59: a PM creates the four operational roles only
        ("GET", "/quotations"): ["sales", "pm", "director"],  # Amendment 49
        ("GET", "/quotations/export"): ["director"],
        ("POST", "/projects"): ["sales", "pm", "director"],
        ("GET", "/opportunities"): ["sales", "pm", "director", "procurement"],
        ("PATCH", "/clients/{client_id}"): ["director"],  # client flags are Director-only
        ("GET", "/dashboard"): [r for r in ALL_ROLES if r != "admin"],  # an Admin has no business dashboard (Amendment 59)
        ("GET", "/role-permissions"): ["director", "admin"],  # Amendment 59
    }
    for key, roles in expected.items():
        assert key in lookup, f"{key} missing"
        assert lookup[key][0] == roles, f"{key}: {lookup[key][0]} != {roles}"


def test_routes_that_need_no_particular_role_are_classified(client, director_user):
    ungated = {(u["method"], u["path"]): u["access"] for u in _fetch(client, director_user)["ungated"]}
    assert ungated[("POST", "/auth/login")] == "public"
    assert ungated[("GET", "/health")] == "public"
    assert ungated[("GET", "/auth/me")] == "any_signed_in"
    assert ungated[("POST", "/auth/change-password")] == "any_signed_in"


def test_labels_are_readable(client, director_user):
    lookup = _gated_lookup(_fetch(client, director_user))
    assert lookup[("POST", "/projects")][1] == "Create project"
    assert lookup[("GET", "/payments")][1] == "List payments"


# --- it cannot drift ---------------------------------------------------------


def test_a_newly_gated_route_appears_with_no_other_change(client, director_user):
    """The point of generating this screen: add a gate anywhere and it shows up."""

    def probe_role_gate(current_user=Depends(require_roles("procurement"))):
        return {"ok": True}

    app.add_api_route("/__probe_role_gate", probe_role_gate, methods=["GET"], tags=["probe"])
    try:
        body = _fetch(client, director_user)
        area = next(a for a in body["areas"] if a["area"] == "probe")
        [group] = area["groups"]
        assert group["roles"] == ["procurement"]
        assert group["items"] == [{"method": "GET", "path": "/__probe_role_gate", "label": "Probe role gate"}]
    finally:
        app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) != "/__probe_role_gate"]
        app.openapi_schema = None

    assert all(a["area"] != "probe" for a in _fetch(client, director_user)["areas"])
