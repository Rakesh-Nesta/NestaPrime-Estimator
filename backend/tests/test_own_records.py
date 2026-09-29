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


def test_known_gap_reassigning_a_record_leaves_its_followup_owner_stale(client, two_sales):
    """KNOWN GAP, reproduced deliberately -- NOT fixed here (correction plan, 2026-09-29 dashboard-fix
    follow-up review): reassigning a Client's or Opportunity's owner (PATCH /ownership/{kind}/{id}, a real
    Amendment 60 workflow) updates that record's own owner_id but does not update the owner_id already on its
    open FollowUp row (no call anywhere in app/api/ownership.py touches the follow_ups table). The dashboard
    tile above (Opportunity.owner_id-based, fixed) and GET /follow-ups' own unconditional Sales narrowing
    (FollowUp.owner_id-based, unchanged) can then read two different owners for the same record -- the same
    tile/destination mismatch shape the dashboard fix above closes for the switch-off case, reopened here by a
    different, unrelated cause.

    Left unresolved deliberately: this record's owner_explicitly_assigned is False (inherited from the parent
    at creation, not an explicit specialist assignment) -- a real fix must reconcile only that case and must
    never silently overwrite a FollowUp an explicit assignment intentionally left pointing elsewhere. It must
    also narrow the dashboard to match GET /follow-ups' own visibility rules, never loosen GET /follow-ups to
    match the dashboard. If this test starts failing, it means someone changed that behaviour -- update or
    remove it as part of that fix, not by chance."""
    today = str(date.today())
    opp = client.post("/opportunities", json={"lead_name": "Reassigned mid-flight", "next_follow_up_date": today}, headers=two_sales["a"]).json()
    follow_up_id = next(f["id"] for f in client.get("/follow-ups", headers=two_sales["a"]).json() if f["entity_id"] == opp["id"])
    assert client.get("/follow-ups", headers=two_sales["a"]).json()[0]["owner_explicitly_assigned"] is False

    _give(client, two_sales["director"], "opportunity", opp["id"], two_sales["ids"]["b"])  # A -> B

    reassigned = client.get(f"/opportunities", headers=two_sales["director"]).json()
    assert next(o for o in reassigned if o["id"] == opp["id"])["owner_id"] == two_sales["ids"]["b"]

    stale_owner = next(f["owner_id"] for f in client.get("/follow-ups", headers=two_sales["director"]).json() if f["id"] == follow_up_id)
    assert stale_owner == two_sales["ids"]["a"]  # unchanged -- this is the gap

    a_sees_it = any(f["id"] == follow_up_id for f in client.get("/follow-ups", headers=two_sales["a"]).json())
    b_sees_it = any(f["id"] == follow_up_id for f in client.get("/follow-ups", headers=two_sales["b"]).json())
    assert a_sees_it is True and b_sees_it is False  # A's destination still shows it; B's tile now counts it but B's destination does not


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
