"""Amendment 53 (Section 57): global quick search -- GET /search.

One box finds a client, a lead, a project or a quotation. It must show a role
nothing that role could not already open (each kind reuses its list endpoint's
own gate, and a test below pins that they still match), it never carries an
amount (K.3), `%` and `_` are matched literally, and the result counts are true."""

import json

from app.api import clients as clients_api
from app.api import opportunities as opportunities_api
from app.api import projects as projects_api
from app.api import quotations_admin as quotations_api
from app.api.role_permissions import build_role_permissions
from app.main import app
from app.models.user import UserRole
from tests.test_quotations_admin import (
    _create_client_record,
    _create_project,
    _login,
    _quotation_for_new_project,
    _role_headers,
)

ROLE_USERS = {
    "sales": (UserRole.SALES, "sales-s@test.local"),
    "pm": (UserRole.PM, "pm-s@test.local"),
    "procurement": (UserRole.PROCUREMENT, "proc-s@test.local"),
    "site_engineer": (UserRole.SITE_ENGINEER, "eng-s@test.local"),
    "ca_tax": (UserRole.CA_TAX, "ca-s@test.local"),
}
ITEM_KEYS = {"kind", "id", "primary", "secondary", "client_id", "project_id", "opportunity_id"}


def _director(client, director_user):
    return _login(client, "director@test.local")


def _search(client, headers, q):
    res = client.get("/search", params={"q": q}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _group(body, kind):
    return next((g for g in body["groups"] if g["kind"] == kind), None)


def _names(body, kind):
    group = _group(body, kind)
    return [i["primary"] for i in group["items"]] if group else []


def _new_client(client, headers, name, **extra):
    res = client.post("/clients", json={"name": name, "type": "school", **extra}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _new_lead(client, headers, name, **extra):
    res = client.post(
        "/opportunities", json={"lead_name": name, "next_follow_up_date": "2099-01-01", **extra}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


# --- access -----------------------------------------------------------------


def test_search_requires_a_login(client):
    assert client.get("/search", params={"q": "abc"}).status_code == 401


def test_each_role_receives_only_the_kinds_it_can_read(client, director_user, db_session):
    headers = _director(client, director_user)
    _quotation_for_new_project(client, headers, "Kinds Test School")

    expected = {
        "director": ["client", "lead", "project", "quotation"],
        "sales": ["client", "lead", "project", "quotation"],
        "pm": ["client", "lead", "project", "quotation"],
        "procurement": ["client", "lead", "project"],
        "site_engineer": ["project"],
        "ca_tax": ["project"],
    }
    for role, kinds in expected.items():
        h = headers if role == "director" else _role_headers(client, db_session, *ROLE_USERS[role])
        body = _search(client, h, "Kinds Test")
        assert [g["kind"] for g in body["groups"]] == kinds, role
        # every role can find the project by its client's name (all six read /projects)
        assert _names(body, "project"), role


def test_search_gates_match_the_live_route_gates():
    """The point of reusing the constants: if a list endpoint's gate changes, search follows."""
    gated = {}
    for area in build_role_permissions(app.routes).areas:
        for group in area.groups:
            for item in group.items:
                gated[(item.method, item.path)] = group.roles
    assert list(clients_api.READ_ROLES) == gated[("GET", "/clients")]
    assert list(opportunities_api.READ_ROLES) == gated[("GET", "/opportunities")]
    assert list(projects_api.LIST_ROLES) == gated[("GET", "/projects")]
    assert list(quotations_api.LIST_ROLES) == gated[("GET", "/quotations")]


def test_the_permissions_screen_labels_search_as_limited(client, director_user):
    res = client.get("/role-permissions", headers=_director(client, director_user))
    items = [i for a in res.json()["areas"] for g in a["groups"] for i in g["items"] if i["path"] == "/search"]
    assert [i["label"] for i in items] == ["Quick search (results limited to what the role can read)"]


# --- the query --------------------------------------------------------------


def test_a_query_under_two_characters_is_refused_clearly(client, director_user):
    headers = _director(client, director_user)
    for q in ("a", " a ", ""):
        res = client.get("/search", params={"q": q}, headers=headers)
        assert res.status_code == 422, q
        assert "at least 2 characters" in res.json()["detail"]
    assert client.get("/search", headers=headers).status_code == 422  # no q at all
    assert client.get("/search", params={"q": "ab"}, headers=headers).status_code == 200


def test_percent_and_underscore_are_matched_literally(client, director_user):
    headers = _director(client, director_user)
    _new_client(client, headers, "Sports 100% Club")
    _new_client(client, headers, "a_b Academy")
    _new_client(client, headers, "axb Academy")
    _new_client(client, headers, "Plain School")

    assert _names(_search(client, headers, "%%"), "client") == []  # "%%" is literal: no such name
    assert _names(_search(client, headers, "100%"), "client") == ["Sports 100% Club"]
    assert _names(_search(client, headers, "a_b"), "client") == ["a_b Academy"]
    only_underscore = _names(_search(client, headers, "_b"), "client")
    assert only_underscore == ["a_b Academy"]
    # a lone wildcard is under the 2-character minimum, so it can never "match everything"
    assert client.get("/search", params={"q": "%"}, headers=headers).status_code == 422


def test_clients_are_found_by_name_contact_phone_email_and_city(client, director_user):
    headers = _director(client, director_user)
    _new_client(
        client, headers, "Lakeview School", contact_name="Meera Kapoor", phone="+91-98765-43210",
        email="office@lakeview.example", city="Pune",
    )
    _new_client(client, headers, "Other School")
    for q in ("lakeview", "MEERA", "kapoor", "office@lake", "pune", "98765"):
        assert _names(_search(client, headers, q), "client") == ["Lakeview School"], q


def test_phone_numbers_match_on_digits_only_for_a_phone_like_query(client, director_user):
    headers = _director(client, director_user)
    _new_client(client, headers, "Phone Client", phone="+91-98765-43210")
    _new_client(client, headers, "Sunrise 98765 Club")  # a name that merely contains digits
    # different spacing/punctuation in the query still finds the stored number
    for q in ("9876543210", "98765 43210", "(98765) 43210", "+91 98765 43210"):
        assert _names(_search(client, headers, q), "client") == ["Phone Client"], q
    # not phone-like (has letters): matched as text only, so digits inside a phone are not searched
    assert _names(_search(client, headers, "Phone 98765"), "client") == []
    # under 3 digits: no digit matching (and "98" is a plain substring here)
    assert _names(_search(client, headers, "43"), "client") == ["Phone Client"]  # raw substring of the stored text


def test_blacklisted_and_overdue_clients_are_still_found(client, director_user):
    headers = _director(client, director_user)
    client_id = _new_client(client, headers, "Flagged Club")
    res = client.patch(f"/clients/{client_id}", json={"blacklist_flag": True, "overdue_flag": True}, headers=headers)
    assert res.status_code == 200, res.text
    assert _names(_search(client, headers, "Flagged"), "client") == ["Flagged Club"]


# --- leads ------------------------------------------------------------------


def test_leads_are_the_unlinked_open_opportunities_by_their_lead_fields(client, director_user):
    headers = _director(client, director_user)
    lead_id = _new_lead(client, headers, "Ravi Enquiry", lead_phone="98111 22233", lead_email="ravi@x.example")
    lost_id = _new_lead(client, headers, "Ravi Lost")
    res = client.patch(f"/opportunities/{lost_id}/stage", json={"stage": "lost", "lost_reason": "no budget"}, headers=headers)
    assert res.status_code == 200, res.text
    linked_client = _new_client(client, headers, "Ravi Real Client")
    linked_lead = _new_lead(client, headers, "Ravi Linked")
    assert client.patch(
        f"/opportunities/{linked_lead}/link-client", json={"client_id": linked_client}, headers=headers
    ).status_code == 200

    body = _search(client, headers, "ravi")
    leads = _group(body, "lead")
    ids = {i["id"] for i in leads["items"]}
    assert lead_id in ids
    assert lost_id not in ids  # Leads & Clients hides lost leads, so search does too
    assert linked_lead not in ids  # linked to a client -> it is that client, shown under Clients
    for i in leads["items"]:
        assert i["opportunity_id"] == i["id"] and i["client_id"] is None
    assert "Ravi Real Client" in _names(body, "client")
    # by lead phone digits and email
    assert lead_id in {i["id"] for i in _group(_search(client, headers, "9811122233"), "lead")["items"]}
    assert lead_id in {i["id"] for i in _group(_search(client, headers, "ravi@x"), "lead")["items"]}


# --- projects and quotations ------------------------------------------------


def test_projects_and_quotations_are_found_and_carry_what_opens_them(client, director_user):
    headers = _director(client, director_user)
    project_id, quotation = _quotation_for_new_project(client, headers, "Opening Test School")

    by_client = _search(client, headers, "Opening Test")
    project = _group(by_client, "project")["items"][0]
    assert project["project_id"] == project_id and project["primary"]
    assert "Opening Test School" in project["secondary"] and "Mumbai" in project["secondary"]

    by_doc = _search(client, headers, quotation["document_no"])
    q_item = _group(by_doc, "quotation")["items"][0]
    assert q_item["primary"] == quotation["document_no"]
    assert q_item["project_id"] == project_id and q_item["client_id"] is not None
    assert "Opening Test School" in q_item["secondary"]
    # project number finds both the project and its quotation
    by_project_no = _search(client, headers, project["primary"])
    assert project_id in {i["project_id"] for i in _group(by_project_no, "project")["items"]}
    assert project_id in {i["project_id"] for i in _group(by_project_no, "quotation")["items"]}


def test_no_result_carries_an_amount_or_cost_for_any_role(client, director_user, db_session):
    headers = _director(client, director_user)
    _quotation_for_new_project(client, headers, "Lookup Test School")
    forbidden = ("cost", "margin", "price", "amount", "selling", "quotation_total", "floor", "rate")
    for role in ("director", "sales", "pm", "procurement", "site_engineer", "ca_tax"):
        h = headers if role == "director" else _role_headers(client, db_session, *ROLE_USERS[role])
        body = _search(client, h, "Lookup Test")
        text = json.dumps(body).lower()
        for word in forbidden:
            assert word not in text, f"{role}: response mentions {word!r}"
        for group in body["groups"]:
            assert set(group) == {"kind", "label", "total", "items"}
            for item in group["items"]:
                assert set(item) == ITEM_KEYS, role


# --- caps, totals, ordering -------------------------------------------------


def test_each_group_is_capped_at_six_with_the_true_total(client, director_user):
    headers = _director(client, director_user)
    for n in range(1, 9):
        _new_client(client, headers, f"Cap Client {n}")
    body = _search(client, headers, "Cap Client")
    group = _group(body, "client")
    assert group["total"] == 8 and len(group["items"]) == 6
    assert body["limit"] == 6


def test_exact_matches_come_first_then_prefix_then_the_rest(client, director_user):
    headers = _director(client, director_user)
    _new_client(client, headers, "Zed Sports")
    _new_client(client, headers, "Sports Zed")
    _new_client(client, headers, "Sports")
    assert _names(_search(client, headers, "sports"), "client") == ["Sports", "Sports Zed", "Zed Sports"]


def test_nothing_matching_returns_empty_groups_not_an_error(client, director_user):
    headers = _director(client, director_user)
    body = _search(client, headers, "zzzz-no-such-thing")
    assert [g["total"] for g in body["groups"]] == [0, 0, 0, 0]
    assert all(g["items"] == [] for g in body["groups"])


def test_a_newly_created_record_is_found_immediately(client, director_user):
    headers = _director(client, director_user)
    assert _names(_search(client, headers, "Brand New Academy"), "client") == []
    _create_client_record(client, headers, "Brand New Academy")
    assert _names(_search(client, headers, "Brand New Academy"), "client") == ["Brand New Academy"]
    client_id = _create_client_record(client, headers, "Projectless Trust")
    _create_project(client, headers, client_id)
    assert _names(_search(client, headers, "Projectless"), "project") != []
