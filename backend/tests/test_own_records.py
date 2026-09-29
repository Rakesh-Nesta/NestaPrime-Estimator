"""Amendment 60 (Section 63): a Sales user sees only their own records, once the Director turns it on.

Two salespeople, A and B, and a world of records handed to A: B must not be able to list, search, open by id, attach
to, or build on any of it; a PM and the Director see everything; and with the switch off nothing changes for anyone.
The by-id part is a generated walk over every route a Sales user can reach, in the spirit of the all-routes test."""

import re
import uuid
from datetime import date, timedelta

import pytest

from app.api.role_permissions import build_role_permissions
from app.core.ownership import COVERED_PATH_PARAMS, UNSCOPED_PATH_PARAMS
from app.main import app
from app.models.audit_log import AuditLogEntry
from app.models.notification import Notification, NotificationKind
from app.models.user import UserRole
from tests.test_attachments import _director_headers, _upload
from tests.test_multi_sport_quotation import _approve, _create_estimate, _option
from tests.test_quotations_admin import (
    _add_project_sport,
    _create_client_record,
    _create_project,
    _role_headers,
    _verified_cost_sheet,
)


def _switch(client, headers, on=True):
    res = client.put("/ownership/switch", json={"on": on}, headers=headers)
    assert res.status_code == 200, res.text


def _me(client, headers):
    return client.get("/auth/me", headers=headers).json()["id"]


def _give(client, director, kind, record_id, owner_id, cascade=True):
    res = client.patch(f"/ownership/{kind}/{record_id}", json={"owner_id": owner_id, "cascade": cascade}, headers=director)
    assert res.status_code == 200, res.text


def _world(client, director, owner_id, name):
    """A client, a project with sport, verified cost sheet, approved estimate option and a quotation, an attachment, an
    enquiry and a signatory -- all built by the Director, then handed to `owner_id`."""
    client_id = _create_client_record(client, director, name)
    project_id = _create_project(client, director, client_id)
    selection = _add_project_sport(client, director, project_id, "badminton")
    cost_sheet = _verified_cost_sheet(client, director, project_id, 850000)
    estimate = _create_estimate(client, director, project_id, [_option(selection)]).json()
    option = estimate["options"][0]["id"]
    _approve(client, director, estimate["id"], option)
    quotation = client.post(
        f"/projects/{project_id}/quotations", json={"estimate_id": estimate["id"], "included_option_ids": [option]}, headers=director
    )
    assert quotation.status_code == 201, quotation.text
    attachment = _upload(client, director, "cost_sheet", cost_sheet, "soil_report")
    assert attachment.status_code == 201, attachment.text
    opportunity = client.post(
        "/opportunities", json={"lead_name": f"Lead of {name}", "next_follow_up_date": str(date.today() + timedelta(days=3))}, headers=director
    ).json()["id"]
    signatory = client.post(
        f"/clients/{client_id}/signatories",
        json={"name": "S. Signer", "designation": "Principal", "authorization_date": str(date.today())},
        headers=director,
    )
    _give(client, director, "client", client_id, owner_id)  # the client, and its project, follow
    _give(client, director, "opportunity", opportunity, owner_id)
    return {
        "client_id": client_id, "project_id": project_id, "selection_id": selection, "project_sport_id": selection,
        "cost_sheet_id": cost_sheet, "estimate_id": estimate["id"], "option_id": option, "quotation_id": quotation.json()["id"],
        "attachment_id": attachment.json()["id"], "opportunity_id": opportunity,
        "signatory_id": signatory.json().get("id") if signatory.status_code == 201 else None,
        "name": name,
    }


@pytest.fixture()
def two_sales(client, director_user, db_session):
    director = _director_headers(client, director_user)
    a = _role_headers(client, db_session, UserRole.SALES, "sales-a@own.test")
    b = _role_headers(client, db_session, UserRole.SALES, "sales-b@own.test")
    pm = _role_headers(client, db_session, UserRole.PM, "pm@own.test")
    ids = {"a": _me(client, a), "b": _me(client, b)}
    world_a = _world(client, director, ids["a"], "Alpha School A")
    world_b = _world(client, director, ids["b"], "Beta School B")
    return {"director": director, "a": a, "b": b, "pm": pm, "ids": ids, "wa": world_a, "wb": world_b}


# --- the switch is off by default: nothing changes ------------------------------------------------------------


def test_with_the_switch_off_a_salesperson_still_sees_everyone(client, two_sales):
    names = {c["name"] for c in client.get("/clients", headers=two_sales["b"]).json()}
    assert {"Alpha School A", "Beta School B"} <= names
    assert client.get(f"/clients/{two_sales['wa']['client_id']}", headers=two_sales["b"]).status_code == 200


def test_only_the_director_can_switch_it_and_it_is_audited(client, two_sales, db_session):
    assert client.put("/ownership/switch", json={"on": True}, headers=two_sales["pm"]).status_code == 403
    assert client.put("/ownership/switch", json={"on": True}, headers=two_sales["a"]).status_code == 403
    _switch(client, two_sales["director"], True)
    assert client.get("/ownership/overview", headers=two_sales["pm"]).json()["switch_on"] is True
    entries = db_session.query(AuditLogEntry).filter(AuditLogEntry.field == "sales_own_records_only").all()
    assert entries and entries[-1].new_value == "on"


# --- lists ----------------------------------------------------------------------------------------------------


def test_lists_hold_only_the_salespersons_own_records(client, two_sales):
    _switch(client, two_sales["director"])
    a, b, wa, wb = two_sales["a"], two_sales["b"], two_sales["wa"], two_sales["wb"]
    assert {c["name"] for c in client.get("/clients", headers=a).json()} == {"Alpha School A"}
    assert {p["id"] for p in client.get("/projects", headers=a).json()} == {wa["project_id"]}
    assert {o["id"] for o in client.get("/opportunities", headers=a).json()} == {wa["opportunity_id"]}
    assert {q["id"] for q in client.get("/quotations", headers=a).json()} == {wa["quotation_id"]}
    assert {e["id"] for e in client.get("/estimates", headers=a).json()} == {wa["estimate_id"]}
    assert {c["name"] for c in client.get("/clients", headers=b).json()} == {"Beta School B"}
    # a project with a search term that would match the other's client
    assert client.get("/projects", params={"search": "Alpha"}, headers=b).json() == []


def test_a_pm_and_the_director_see_everything(client, two_sales):
    _switch(client, two_sales["director"])
    for headers in (two_sales["pm"], two_sales["director"]):
        names = {c["name"] for c in client.get("/clients", headers=headers).json()}
        assert {"Alpha School A", "Beta School B"} <= names
        assert len(client.get("/quotations", headers=headers).json()) >= 2


def test_quick_search_finds_only_the_salespersons_own(client, two_sales):
    _switch(client, two_sales["director"])
    def found(headers, term):
        return [i["primary"] for g in client.get("/search", params={"q": term}, headers=headers).json()["groups"] for i in g["items"]]
    assert "Alpha School A" in found(two_sales["a"], "Alpha")
    assert found(two_sales["b"], "Alpha") == []
    assert "Alpha School A" in found(two_sales["pm"], "Alpha")


# --- by id: the generated walk --------------------------------------------------------------------------------


def _sales_routes():
    table = build_role_permissions(app.routes)
    return [
        (item.method, item.path)
        for area in table.areas
        for group in area.groups
        if "sales" in group.roles
        for item in group.items
        if "{" in item.path
    ]


def test_every_route_a_salesperson_can_reach_refuses_someone_elses_record_with_404(client, two_sales):
    _switch(client, two_sales["director"])
    world = two_sales["wa"]
    ids = {k: v for k, v in world.items() if k.endswith("_id") and v}
    checked, skipped = 0, set()
    leaks = []
    for method, path in _sales_routes():
        params = re.findall(r"\{([^}]+)\}", path)
        if all(p in UNSCOPED_PATH_PARAMS for p in params):
            continue  # the path carries a plain value (a client type), not a record -- nothing to hide
        if any(p not in ids and p not in UNSCOPED_PATH_PARAMS for p in params):
            skipped.update(p for p in params if p not in ids and p not in UNSCOPED_PATH_PARAMS)
            continue
        url = path
        for p in params:
            url = url.replace("{" + p + "}", ids.get(p, "school"))
        body = {} if method in ("POST", "PUT", "PATCH") else None
        theirs = client.request(method, url, json=body, headers=two_sales["b"])
        checked += 1
        if theirs.status_code != 404 or theirs.json().get("detail") != "Not found":
            leaks.append(f"{method} {path} -> {theirs.status_code} {theirs.text[:80]}")
    assert checked > 40, checked  # the walk really covers the surface
    assert not leaks, "A salesperson reached someone else's record:\n" + "\n".join(leaks)
    assert skipped <= {"row_id", "work_order_id", "signatory_id", "report_id"}, skipped  # cannot be built here


def test_a_missing_id_and_someone_elses_id_answer_identically(client, two_sales):
    _switch(client, two_sales["director"])
    hidden = client.get(f"/clients/{two_sales['wa']['client_id']}", headers=two_sales["b"])
    missing = client.get(f"/clients/{uuid.uuid4()}", headers=two_sales["b"])
    assert hidden.status_code == missing.status_code == 404 and hidden.json() == missing.json()


def test_the_owner_still_reaches_their_own_records(client, two_sales):
    _switch(client, two_sales["director"])
    a, wa = two_sales["a"], two_sales["wa"]
    for url in (f"/clients/{wa['client_id']}", f"/projects/{wa['project_id']}", f"/opportunities/{wa['opportunity_id']}",
                f"/quotations/{wa['quotation_id']}", f"/projects/{wa['project_id']}/quotations"):
        assert client.get(url, headers=a).status_code == 200, url


def test_every_id_a_salesperson_can_send_is_covered_by_the_rule():
    """A new route with a new kind of id must be added to the own-records rule, on purpose."""
    used = {p for _m, path in _sales_routes() for p in re.findall(r"\{([^}]+)\}", path)}
    assert used <= (COVERED_PATH_PARAMS | UNSCOPED_PATH_PARAMS), used - (COVERED_PATH_PARAMS | UNSCOPED_PATH_PARAMS)


def test_attachments_and_messages_by_document_follow_the_project(client, two_sales):
    _switch(client, two_sales["director"])
    wa = two_sales["wa"]
    # an estimate: a document type a salesperson may use, so it is the ownership rule that answers, not a role rule
    params = {"doc_type": "estimate", "doc_id": wa["estimate_id"]}
    assert client.get("/attachments", params=params, headers=two_sales["a"]).status_code == 200
    assert client.get("/attachments", params=params, headers=two_sales["b"]).status_code == 404
    assert client.get("/messages", params=params, headers=two_sales["b"]).status_code == 404
    up = _upload(client, two_sales["b"], "estimate", wa["estimate_id"], "soil_report")
    assert up.status_code == 404
    assert client.get("/attachments", params=params, headers=two_sales["director"]).status_code == 200


# --- creating: who owns what ----------------------------------------------------------------------------------


def test_a_new_client_belongs_to_whoever_creates_it_and_its_project_follows(client, two_sales):
    _switch(client, two_sales["director"])
    a = two_sales["a"]
    mine = client.post("/clients", json={"name": "Gamma School", "type": "school", "phone": "9000011111"}, headers=a).json()
    assert mine["owner_id"] == two_sales["ids"]["a"]
    project = client.post(
        "/projects",
        json={"client_id": mine["id"], "city": "Pune", "site_condition": "level", "soil_type": "normal", "building_status": "open_air",
              "site_access": "good", "power_available": "yes", "water_available": True, "package": "standard"},
        headers=a,
    )
    assert project.status_code == 201 and project.json()["owner_id"] == two_sales["ids"]["a"]


def test_a_salesperson_cannot_start_a_project_on_someone_elses_client(client, two_sales):
    _switch(client, two_sales["director"])
    res = client.post(
        "/projects",
        json={"client_id": two_sales["wb"]["client_id"], "city": "Pune", "site_condition": "level", "soil_type": "normal",
              "building_status": "open_air", "site_access": "good", "power_available": "yes", "water_available": True, "package": "standard"},
        headers=two_sales["a"],
    )
    assert res.status_code == 404 and res.json()["detail"] == "Not found"


def test_a_pm_can_create_a_project_for_a_named_salesperson(client, two_sales):
    pm = two_sales["pm"]
    made = client.post("/clients", json={"name": "Delta School", "type": "school"}, headers=pm).json()
    assert made["owner_id"] != two_sales["ids"]["a"]  # the PM's
    project = client.post(
        "/projects",
        json={"client_id": made["id"], "owner_id": two_sales["ids"]["a"], "city": "Pune", "site_condition": "level", "soil_type": "normal",
              "building_status": "open_air", "site_access": "good", "power_available": "yes", "water_available": True, "package": "standard"},
        headers=pm,
    )
    assert project.status_code == 201 and project.json()["owner_id"] == two_sales["ids"]["a"]
    bad = client.post(
        "/projects",
        json={"client_id": made["id"], "owner_id": str(uuid.uuid4()), "city": "Pune", "site_condition": "level", "soil_type": "normal",
              "building_status": "open_air", "site_access": "good", "power_available": "yes", "water_available": True, "package": "standard"},
        headers=pm,
    )
    assert bad.status_code == 422


def test_an_enquiry_belongs_to_its_creator_and_linking_gives_an_unowned_client_its_owner(client, two_sales, db_session):
    a = two_sales["a"]
    opp = client.post("/opportunities", json={"lead_name": "New lead", "next_follow_up_date": str(date.today() + timedelta(days=2))}, headers=a).json()
    assert opp["owner_id"] == two_sales["ids"]["a"]
    from app.models.client import Client, ClientType

    orphan = Client(name="Orphan School", type=ClientType.SCHOOL)  # no owner: a client from before the change
    db_session.add(orphan)
    db_session.commit()
    linked = client.patch(f"/opportunities/{opp['id']}/link-client", json={"client_id": str(orphan.id)}, headers=two_sales["pm"])
    assert linked.status_code == 200, linked.text
    db_session.refresh(orphan)
    assert orphan.owner_id is not None and str(orphan.owner_id) == two_sales["ids"]["a"]


def test_a_duplicate_of_anothers_client_is_refused_without_revealing_it(client, two_sales, db_session):
    from app.models.client import Client

    _switch(client, two_sales["director"])
    beta = db_session.get(Client, uuid.UUID(two_sales["wb"]["client_id"]))
    beta.phone, beta.email = "+91 98765-43210", "beta@school.in"
    db_session.commit()
    for payload in (
        {"name": "Another name", "type": "school", "phone": "098765 43210"},
        {"name": "Another name", "type": "school", "email": "BETA@school.in"},
    ):
        res = client.post("/clients", json=payload, headers=two_sales["a"])
        assert res.status_code == 409, payload
        assert res.json()["detail"] == "This client already exists under another salesperson -- ask a PM"
        assert "Beta" not in res.text and "98765" not in res.text and "beta@" not in res.text.lower()
    # a PM is not stopped, and a salesperson's own duplicate is theirs to make
    assert client.post("/clients", json={"name": "Dup by PM", "type": "school", "phone": "98765 43210"}, headers=two_sales["pm"]).status_code == 201


# --- the dashboard --------------------------------------------------------------------------------------------


def test_a_salespersons_dashboard_is_their_own_and_the_pms_is_the_companys_plus_a_table(client, two_sales):
    _switch(client, two_sales["director"])
    mine = client.get("/dashboard", headers=two_sales["a"]).json()
    assert mine["summary"]["open_projects_count"] == 1 and len(mine["recent_projects"]) == 1
    assert mine["recent_projects"][0]["id"] == two_sales["wa"]["project_id"]
    assert mine["sales_performance"] is None and mine["scope"] == "own"
    company = client.get("/dashboard", headers=two_sales["pm"]).json()
    assert company["scope"] == "company"
    assert company["summary"]["open_projects_count"] >= 2
    table = {row["name"]: row for row in company["sales_performance"]}
    a_name = client.get("/auth/me", headers=two_sales["a"]).json()["name"]
    assert table[a_name]["open_projects_count"] == mine["summary"]["open_projects_count"]
    assert table[a_name]["open_opportunities_count"] == mine["summary"]["open_opportunities_count"]
    assert table[a_name]["won_this_month_total"] == mine["summary"]["won_this_month_total"]


def test_with_the_switch_off_the_salespersons_dashboard_is_the_companys_as_before(client, two_sales):
    assert client.get("/dashboard", headers=two_sales["a"]).json()["summary"]["open_projects_count"] >= 2


def test_with_the_switch_off_a_salespersons_followups_due_count_is_still_only_their_own(client, two_sales):
    """Dashboard fix (2026-09-29 correction plan): followups_due_count is scoped to the Sales user's own id
    unconditionally -- unlike open_projects_count above (company-wide with the switch off), this one field
    matches GET /follow-ups' own unconditional Sales narrowing (follow_ups.py's list_follow_ups), not the
    Amendment 60 switch. Before this fix, with the switch off, this count was company-wide too -- so the
    tile said e.g. "2" while clicking through (narrowed to just the Sales user's own, regardless of the
    switch) showed a different, smaller number."""
    today = str(date.today())
    opp_a = client.post(
        "/opportunities", json={"lead_name": "Due for A", "next_follow_up_date": today}, headers=two_sales["director"]
    ).json()["id"]
    opp_b = client.post(
        "/opportunities", json={"lead_name": "Due for B", "next_follow_up_date": today}, headers=two_sales["director"]
    ).json()["id"]
    _give(client, two_sales["director"], "opportunity", opp_a, two_sales["ids"]["a"])
    _give(client, two_sales["director"], "opportunity", opp_b, two_sales["ids"]["b"])

    mine = client.get("/dashboard", headers=two_sales["a"]).json()
    assert mine["scope"] == "company"  # the switch is off -- everything else here is company-wide
    assert mine["summary"]["followups_due_count"] == 1  # but this field is still just A's own, not A's + B's


# --- reassignment now carries inherited open follow-ups with it (correction plan, 2026-09-29 --------------
# ownership-mismatch fix). Previously reproduced and left deliberately unresolved (draft PR #273); fixed in
# app/api/ownership.py's _set_owner via _cascade_inherited_follow_ups / _flag_specialist_access_mismatches.
# Each of the agreed rule's five points gets its own test below, run with the own-records switch both off and
# on where the switch is relevant (isolated per test -- db_session is fresh per test, and each test that turns
# the switch on turns it back off before returning, matching this file's existing convention).


@pytest.mark.parametrize("switch_on", [False, True], ids=["switch-off", "switch-on"])
def test_reassignment_moves_an_inherited_open_followup_to_the_new_owner(client, two_sales, switch_on):
    """Rule 1: on parent reassignment, open follow-ups with inherited ownership move to the new owner. Rule 4:
    dashboard counts and the destination list end up reading the same owner, the same access, status and
    due-date rules either way -- checked here via both GET /follow-ups (owner_id itself) and GET /dashboard
    (which must now agree, for both the old and the new owner)."""
    if switch_on:
        _switch(client, two_sales["director"])
    today = str(date.today())
    opp = client.post(
        "/opportunities", json={"lead_name": "Reassigned mid-flight", "next_follow_up_date": today}, headers=two_sales["a"]
    ).json()
    follow_up_id = next(f["id"] for f in client.get("/follow-ups", headers=two_sales["a"]).json() if f["entity_id"] == opp["id"])
    assert client.get("/follow-ups", headers=two_sales["a"]).json()[0]["owner_explicitly_assigned"] is False

    a_before = client.get("/dashboard", headers=two_sales["a"]).json()["summary"]["followups_due_count"]
    b_before = client.get("/dashboard", headers=two_sales["b"]).json()["summary"]["followups_due_count"]

    _give(client, two_sales["director"], "opportunity", opp["id"], two_sales["ids"]["b"])  # A -> B

    moved_owner = next(
        f["owner_id"] for f in client.get("/follow-ups", headers=two_sales["director"]).json() if f["id"] == follow_up_id
    )
    assert moved_owner == two_sales["ids"]["b"]  # the fix: no longer stale

    a_after = client.get("/dashboard", headers=two_sales["a"]).json()["summary"]["followups_due_count"]
    b_after = client.get("/dashboard", headers=two_sales["b"]).json()["summary"]["followups_due_count"]
    assert a_after == a_before - 1
    assert b_after == b_before + 1

    a_sees_it = any(f["id"] == follow_up_id for f in client.get("/follow-ups", headers=two_sales["a"]).json())
    b_sees_it = any(f["id"] == follow_up_id for f in client.get("/follow-ups", headers=two_sales["b"]).json())
    assert a_sees_it is False and b_sees_it is True  # tile and destination now agree for both

    if switch_on:
        _switch(client, two_sales["director"], on=False)


def test_reassignment_never_moves_an_explicitly_assigned_specialists_followup(client, two_sales):
    """Rule 2: explicit specialist assignments remain unchanged. Uses PATCH /follow-ups/{id} with an owner_id
    -- the real path that sets owner_explicitly_assigned True -- rather than constructing the row directly, so
    this exercises the same flag the reassignment cascade itself checks."""
    _switch(client, two_sales["director"])
    today = str(date.today())
    opp = client.post(
        "/opportunities", json={"lead_name": "Specialist assigned", "next_follow_up_date": today}, headers=two_sales["a"]
    ).json()
    follow_up_id = next(f["id"] for f in client.get("/follow-ups", headers=two_sales["a"]).json() if f["entity_id"] == opp["id"])

    specialist_id = client.get("/auth/me", headers=two_sales["pm"]).json()["id"]
    assigned = client.patch(f"/follow-ups/{follow_up_id}", json={"owner_id": specialist_id}, headers=two_sales["director"])
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["owner_explicitly_assigned"] is True

    _give(client, two_sales["director"], "opportunity", opp["id"], two_sales["ids"]["b"])  # A -> B, parent moves

    still = client.get("/follow-ups", headers=two_sales["director"]).json()
    row = next(f for f in still if f["id"] == follow_up_id)
    assert row["owner_id"] == specialist_id  # untouched by the parent's reassignment
    assert row["owner_explicitly_assigned"] is True

    _switch(client, two_sales["director"], on=False)


def test_reassignment_does_not_touch_completed_history_or_creator_attribution(client, two_sales):
    """Rule 3: completed history and original creator attribution are preserved. A completed/cancelled
    FollowUp is historical record -- reassigning its parent must not rewrite who it says did what."""
    today = str(date.today())
    opp = client.post(
        "/opportunities", json={"lead_name": "History preserved", "next_follow_up_date": today}, headers=two_sales["a"]
    ).json()
    rows_before = client.get("/follow-ups", headers=two_sales["a"]).json()
    follow_up_id = next(f["id"] for f in rows_before if f["entity_id"] == opp["id"])

    future = str(date.today() + timedelta(days=7))
    completed = client.patch(
        f"/follow-ups/{follow_up_id}",
        json={"status": "completed", "replacement": {"due_date": future, "next_action": "Follow up again"}},
        headers=two_sales["a"],
    )
    assert completed.status_code == 200, completed.text
    completed_owner_before = completed.json()["owner_id"]
    assert completed_owner_before == two_sales["ids"]["a"]

    _give(client, two_sales["director"], "opportunity", opp["id"], two_sales["ids"]["b"])  # A -> B

    all_rows = client.get("/follow-ups", headers=two_sales["director"]).json()
    completed_row = next(f for f in all_rows if f["id"] == follow_up_id)
    assert completed_row["status"] == "completed"
    assert completed_row["owner_id"] == two_sales["ids"]["a"]  # historical -- not moved to B
    assert completed_row["created_by_id"] == two_sales["ids"]["a"]  # creator attribution untouched

    replacement_row = next(f for f in all_rows if f["entity_id"] == opp["id"] and f["id"] != follow_up_id)
    assert replacement_row["status"] == "open"
    assert replacement_row["owner_id"] == two_sales["ids"]["b"]  # this one WAS open and inherited -- moves
    assert replacement_row["created_by_id"] == two_sales["ids"]["a"]  # still credited to whoever created it


def test_reassignment_flags_a_specialist_who_loses_access_immediately(client, two_sales, db_session):
    """Rule 5: a specialist who can no longer access the parent stays visibly flagged for resolution --
    immediately, at reassignment time, not only at the next scheduled reminder run (which only looks at
    follow-ups already due or overdue). Reuses reminders.py's own ACCESS_MISMATCH_ESCALATION notification
    kind and its idempotent creation helper rather than inventing a second escalation path.

    Amendment 60 scoping for a Sales user is binary on the PARENT's current owner, regardless of follow-up
    assignment history -- a Sales specialist explicitly assigned to a record they never owned has no access
    from the moment they're assigned (that's the pre-existing WP5 gap test_reminders.py already covers), not
    something a later reassignment newly breaks. The case this fix actually adds is the specialist who has
    real access at assignment time (because the parent happens to be theirs then) and only loses it once the
    parent later moves to someone else -- built here with two reassignments: the first hands the parent to B
    (who by then already holds an explicit assignment made while they still had no access, and gains real
    access purely by the parent catching up to it); the second takes the parent away from B again, which is
    the transition actually being tested."""
    _switch(client, two_sales["director"])
    future = str(date.today() + timedelta(days=10))  # deliberately not due yet -- the daily job wouldn't catch this
    opp = client.post(
        "/opportunities", json={"lead_name": "Specialist stranded", "next_follow_up_date": future}, headers=two_sales["a"]
    ).json()
    follow_up_id = next(f["id"] for f in client.get("/follow-ups", headers=two_sales["a"]).json() if f["entity_id"] == opp["id"])
    b_id = two_sales["ids"]["b"]

    assigned = client.patch(f"/follow-ups/{follow_up_id}", json={"owner_id": b_id}, headers=two_sales["director"])
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["owner_explicitly_assigned"] is True  # genuinely different from A -- a real explicit assignment

    _give(client, two_sales["director"], "opportunity", opp["id"], two_sales["ids"]["b"])  # parent A -> B: B now matches
    assert client.get("/follow-ups", headers=two_sales["b"]).json() != []  # B can open it right now

    before = db_session.query(Notification).filter(Notification.kind == NotificationKind.ACCESS_MISMATCH_ESCALATION).count()

    # Reassign the parent away from B again, back to A. B's FollowUp row stays explicitly B's (rule 2) -- but
    # B (Sales, switch on) now fails check_follow_up_access on an opportunity they no longer own.
    _give(client, two_sales["director"], "opportunity", opp["id"], two_sales["ids"]["a"])

    # B still has their own unrelated follow-ups (from two_sales' own world-building) -- check this
    # specific one is gone from B's list, not that B's list is empty.
    assert not any(f["id"] == follow_up_id for f in client.get("/follow-ups", headers=two_sales["b"]).json())  # B genuinely can't see it anymore

    to_director = (
        db_session.query(Notification)
        .filter(Notification.kind == NotificationKind.ACCESS_MISMATCH_ESCALATION, Notification.follow_up_id == follow_up_id)
        .first()
    )
    assert to_director is not None  # flagged immediately, without waiting for run_daily_reminders
    assert "cannot open their own follow-up" in to_director.title

    after = db_session.query(Notification).filter(Notification.kind == NotificationKind.ACCESS_MISMATCH_ESCALATION).count()
    assert after == before + 1

    _switch(client, two_sales["director"], on=False)


# --- the same rule, extended to Project (correction plan, 2026-09-29 follow-up review: Project ------------
# follows the same inherited-vs-explicit rule as Client/Opportunity, per create_follow_up's own uniform
# owner-defaulting logic in app/api/follow_ups.py -- verified before extending the cascade to it).


@pytest.mark.parametrize("switch_on", [False, True], ids=["switch-off", "switch-on"])
def test_reassignment_moves_an_inherited_open_followup_to_the_new_owner_for_project(client, two_sales, switch_on):
    """Rule 1 and rule 4, for Project. two_sales["wa"]["project_id"] is already owned by A (the world-building
    client reassignment cascades ownership onto its project)."""
    if switch_on:
        _switch(client, two_sales["director"])
    project_id = two_sales["wa"]["project_id"]
    today = str(date.today())
    created = client.post(
        "/follow-ups",
        json={"entity_type": "project", "entity_id": project_id, "next_action": "Site check-in", "due_date": today},
        headers=two_sales["a"],
    )
    assert created.status_code == 201, created.text
    follow_up_id = created.json()["id"]
    assert created.json()["owner_explicitly_assigned"] is False

    a_before = client.get("/dashboard", headers=two_sales["a"]).json()["summary"]["followups_due_count"]
    b_before = client.get("/dashboard", headers=two_sales["b"]).json()["summary"]["followups_due_count"]

    _give(client, two_sales["director"], "project", project_id, two_sales["ids"]["b"])  # A -> B

    moved_owner = next(
        f["owner_id"] for f in client.get("/follow-ups", headers=two_sales["director"]).json() if f["id"] == follow_up_id
    )
    assert moved_owner == two_sales["ids"]["b"]  # the fix, extended to Project

    a_after = client.get("/dashboard", headers=two_sales["a"]).json()["summary"]["followups_due_count"]
    b_after = client.get("/dashboard", headers=two_sales["b"]).json()["summary"]["followups_due_count"]
    assert a_after == a_before - 1
    assert b_after == b_before + 1

    a_sees_it = any(f["id"] == follow_up_id for f in client.get("/follow-ups", headers=two_sales["a"]).json())
    b_sees_it = any(f["id"] == follow_up_id for f in client.get("/follow-ups", headers=two_sales["b"]).json())
    assert a_sees_it is False and b_sees_it is True

    if switch_on:
        _switch(client, two_sales["director"], on=False)


def test_reassignment_never_moves_an_explicitly_assigned_specialists_followup_for_project(client, two_sales):
    """Rule 2, for Project. The assignee here is a PM, deliberately not a Site Engineer -- this proves
    preservation is governed by the stored owner_explicitly_assigned flag itself, not by any role-based
    special-casing of who counts as a "Project specialist"."""
    _switch(client, two_sales["director"])
    project_id = two_sales["wa"]["project_id"]
    today = str(date.today())
    created = client.post(
        "/follow-ups",
        json={"entity_type": "project", "entity_id": project_id, "next_action": "Specialist assigned", "due_date": today},
        headers=two_sales["a"],
    )
    assert created.status_code == 201, created.text
    follow_up_id = created.json()["id"]

    specialist_id = client.get("/auth/me", headers=two_sales["pm"]).json()["id"]
    assigned = client.patch(f"/follow-ups/{follow_up_id}", json={"owner_id": specialist_id}, headers=two_sales["director"])
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["owner_explicitly_assigned"] is True

    _give(client, two_sales["director"], "project", project_id, two_sales["ids"]["b"])  # parent A -> B

    still = client.get("/follow-ups", headers=two_sales["director"]).json()
    row = next(f for f in still if f["id"] == follow_up_id)
    assert row["owner_id"] == specialist_id  # untouched -- not moved to B, and not moved to the PM's own role's default
    assert row["owner_explicitly_assigned"] is True

    _switch(client, two_sales["director"], on=False)


def test_all_three_reassignment_paths_share_the_same_cascade(client, two_sales):
    """The direct PATCH endpoint, reassign-all, and accept-suggestions all call the single, shared
    _set_owner() in app/api/ownership.py -- confirmed by reading that file, which is what actually
    guarantees the three paths can never independently drift (rather than re-deriving the cascade
    logic three times and hoping they stay in sync). Exercised here via reassign-all, the path
    structurally most different from the direct PATCH already covered above: a bulk move of
    everything one person owns, across both an Opportunity and a Project in the same call."""
    today = str(date.today())
    opp = client.post(
        "/opportunities", json={"lead_name": "Bulk moved opportunity", "next_follow_up_date": today}, headers=two_sales["a"]
    ).json()
    opp_followup_id = next(
        f["id"] for f in client.get("/follow-ups", headers=two_sales["a"]).json() if f["entity_id"] == opp["id"]
    )

    project_id = two_sales["wa"]["project_id"]
    proj_followup = client.post(
        "/follow-ups",
        json={"entity_type": "project", "entity_id": project_id, "next_action": "Bulk moved project follow-up", "due_date": today},
        headers=two_sales["a"],
    )
    assert proj_followup.status_code == 201, proj_followup.text
    proj_followup_id = proj_followup.json()["id"]

    res = client.post(
        "/ownership/reassign-all",
        json={"from_user_id": two_sales["ids"]["a"], "to_user_id": two_sales["ids"]["b"]},
        headers=two_sales["director"],
    )
    assert res.status_code == 200, res.text

    rows = client.get("/follow-ups", headers=two_sales["director"]).json()
    assert next(f for f in rows if f["id"] == opp_followup_id)["owner_id"] == two_sales["ids"]["b"]
    assert next(f for f in rows if f["id"] == proj_followup_id)["owner_id"] == two_sales["ids"]["b"]


def test_dashboard_followups_due_count_always_equals_the_destinations_own_total(client, two_sales):
    """General parity check, independent of any specific reassignment scenario: whatever GET
    /follow-ups' own no-filter listing returns as due (open/in_progress/waiting, due today or
    earlier) for a given viewer, GET /dashboard's followups_due_count must equal exactly that --
    checked here for every role this fixture has handy, with the switch both off and on, so the
    two can never merely happen to agree on the specific cases the tests above already cover."""
    today = str(date.today())
    client.post(
        "/follow-ups",
        json={"entity_type": "project", "entity_id": two_sales["wa"]["project_id"], "next_action": "Parity check", "due_date": today},
        headers=two_sales["a"],
    )
    client.post(
        "/opportunities", json={"lead_name": "Parity opportunity", "next_follow_up_date": today}, headers=two_sales["a"]
    )

    def _assert_parity(headers):
        due = client.get("/dashboard", headers=headers).json()["summary"]["followups_due_count"]
        destination = [
            f
            for f in client.get("/follow-ups", headers=headers).json()
            if f["status"] not in ("completed", "cancelled") and f["due_date"] <= today
        ]
        assert due == len(destination), (due, len(destination))

    for headers in (two_sales["a"], two_sales["b"], two_sales["pm"], two_sales["director"]):
        _assert_parity(headers)

    _switch(client, two_sales["director"])
    for headers in (two_sales["a"], two_sales["b"], two_sales["pm"], two_sales["director"]):
        _assert_parity(headers)
    _switch(client, two_sales["director"], on=False)


# --- reports --------------------------------------------------------------------------------------------------


def test_a_salespersons_pipeline_report_covers_only_their_own_and_they_see_only_their_own_reports(client, two_sales):
    _switch(client, two_sales["director"])
    body = {"report_type": "pipeline", "period_from": str(date.today() - timedelta(days=30)), "period_to": str(date.today() + timedelta(days=1))}
    mine = client.post("/reports/generate", json=body, headers=two_sales["a"])
    assert mine.status_code == 201, mine.text
    company = client.post("/reports/generate", json=body, headers=two_sales["pm"]).json()
    assert mine.json()["content"]["estimates"]["created"] == 1
    assert company["content"]["estimates"]["created"] >= 2
    listed_for_b = {r["id"] for r in client.get("/reports", headers=two_sales["b"]).json()}
    assert mine.json()["id"] not in listed_for_b and company["id"] not in listed_for_b
    assert client.get(f"/reports/{mine.json()['id']}", headers=two_sales["b"]).status_code == 404
    assert client.get(f"/reports/{mine.json()['id']}", headers=two_sales["a"]).status_code == 200


# --- reviewing and reassigning --------------------------------------------------------------------------------


def test_only_a_pm_or_the_director_can_review_and_reassign(client, two_sales):
    for headers in (two_sales["a"], two_sales["b"]):
        assert client.get("/ownership/overview", headers=headers).status_code == 403
        assert client.get("/ownership/unassigned", params={"kind": "client"}, headers=headers).status_code == 403
        assert client.post("/ownership/reassign-all", json={"from_user_id": str(uuid.uuid4()), "to_user_id": str(uuid.uuid4())}, headers=headers).status_code == 403
    assert client.get("/ownership/overview", headers=two_sales["pm"]).status_code == 200


def test_reassigning_a_client_moves_it_and_its_project_and_is_audited(client, two_sales, db_session):
    _switch(client, two_sales["director"])
    wa = two_sales["wa"]
    _give(client, two_sales["pm"], "client", wa["client_id"], two_sales["ids"]["b"])
    assert wa["project_id"] in {p["id"] for p in client.get("/projects", headers=two_sales["b"]).json()}
    assert wa["project_id"] not in {p["id"] for p in client.get("/projects", headers=two_sales["a"]).json()}
    assert client.get(f"/clients/{wa['client_id']}", headers=two_sales["a"]).status_code == 404
    entries = db_session.query(AuditLogEntry).filter(AuditLogEntry.field == "owner").all()
    assert {e.document_type for e in entries} >= {"client", "project"}


def test_an_owner_must_be_an_active_sales_pm_or_director(client, two_sales, db_session):
    admin = _role_headers(client, db_session, UserRole.ADMIN, "admin@own.test")
    admin_id = _me(client, admin)
    res = client.patch(f"/ownership/client/{two_sales['wa']['client_id']}", json={"owner_id": admin_id}, headers=two_sales["pm"])
    assert res.status_code == 422 and "active Sales, PM or Director" in res.json()["detail"]
    assert client.patch(f"/ownership/client/{two_sales['wa']['client_id']}", json={"owner_id": str(uuid.uuid4())}, headers=two_sales["pm"]).status_code == 422


def test_reassign_all_moves_everything_one_person_owns(client, two_sales):
    _switch(client, two_sales["director"])
    res = client.post("/ownership/reassign-all", json={"from_user_id": two_sales["ids"]["a"], "to_user_id": two_sales["ids"]["b"]}, headers=two_sales["pm"])
    assert res.status_code == 200
    assert res.json()["clients"] >= 1 and res.json()["projects"] >= 1 and res.json()["opportunities"] >= 1
    assert client.get("/clients", headers=two_sales["a"]).json() == []
    assert {c["name"] for c in client.get("/clients", headers=two_sales["b"]).json()} == {"Alpha School A", "Beta School B"}
    assert client.post("/ownership/reassign-all", json={"from_user_id": two_sales["ids"]["a"], "to_user_id": two_sales["ids"]["a"]}, headers=two_sales["pm"]).status_code == 422


def test_unassigned_records_are_visible_to_a_pm_only_and_get_a_suggestion(client, two_sales, db_session):
    from app.models.client import Client
    from app.models.project import Project

    _switch(client, two_sales["director"])
    wa = two_sales["wa"]
    project = db_session.get(Project, uuid.UUID(wa["project_id"]))
    project.owner_id = None  # a project from before the change: no owner
    db_session.commit()
    assert wa["project_id"] not in {p["id"] for p in client.get("/projects", headers=two_sales["a"]).json()}  # nobody's
    assert client.get(f"/projects/{wa['project_id']}", headers=two_sales["a"]).status_code == 404
    assert wa["project_id"] in {p["id"] for p in client.get("/projects", headers=two_sales["pm"]).json()}
    rows = client.get("/ownership/unassigned", params={"kind": "project"}, headers=two_sales["pm"]).json()
    row = next(r for r in rows if r["id"] == wa["project_id"])
    assert row["suggested_owner_id"] is None or row["evidence"]  # a suggestion, when the data points to one
    overview = client.get("/ownership/overview", headers=two_sales["pm"]).json()
    assert overview["totals"]["project"]["unassigned"] >= 1
    assert client.post("/ownership/accept-suggestions", json={"kind": "project"}, headers=two_sales["pm"]).status_code == 200
    _give(client, two_sales["pm"], "project", wa["project_id"], two_sales["ids"]["a"], cascade=False)
    assert client.get(f"/projects/{wa['project_id']}", headers=two_sales["a"]).status_code == 200
    assert db_session.get(Client, uuid.UUID(wa["client_id"])).owner_id is not None


def test_turning_it_off_gives_everyone_their_old_view_back(client, two_sales):
    _switch(client, two_sales["director"], True)
    assert len(client.get("/clients", headers=two_sales["b"]).json()) == 1
    _switch(client, two_sales["director"], False)
    assert len(client.get("/clients", headers=two_sales["b"]).json()) >= 2
