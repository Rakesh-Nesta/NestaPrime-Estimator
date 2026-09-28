"""Project Overview (correction plan Part 4, 2026-09-28): one screen per Project. Read-only
aggregation of state that already exists elsewhere -- phase/owner, pending work with a
waiting-on-us/client/vendor classification, readiness gaps (WP7), payment blockers (Amendment
50) and latest activity (WP3) -- each section gated to exactly the role list its own existing
source endpoint already uses, so nothing here shows a viewer something they couldn't already
reach on the record's own screen."""
from datetime import date, timedelta

from app.core.security import hash_password
from app.models.user import User, UserRole
from tests.test_payments import _milestone, _won_work_order
from tests.test_quotations_admin import (
    _add_project_sport,
    _approve_option,
    _create_client_record,
    _create_project,
    _director_headers,
    _released_quotation,
    _role_headers,
    _satisfy_project_readiness,
    _sent_estimate,
    _verified_cost_sheet,
)


def _pm_headers(client, db_session):
    return _role_headers(client, db_session, UserRole.PM, "pm-overview@test.local")


def _sales_headers(client, db_session):
    return _role_headers(client, db_session, UserRole.SALES, "sales-overview@test.local")


def _procurement_headers(client, db_session):
    return _role_headers(client, db_session, UserRole.PROCUREMENT, "procurement-overview@test.local")


def _site_engineer_headers(client, db_session):
    return _role_headers(client, db_session, UserRole.SITE_ENGINEER, "site-engineer-overview@test.local")


def _ca_tax_headers(client, db_session):
    return _role_headers(client, db_session, UserRole.CA_TAX, "ca-tax-overview@test.local")


def _draft_estimate(client, headers, project_id, project_sport_id, cost_for_option=850000):
    res = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": cost_for_option}]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def _overview(client, headers, project_id):
    res = client.get(f"/projects/{project_id}/overview", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


# ---------------------------------------------------------------------------
# Basic fields
# ---------------------------------------------------------------------------


def test_overview_shows_phase_owner_and_client(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "Overview Basics Client")
    project_id = _create_project(client, headers, client_id)

    body = _overview(client, headers, project_id)
    assert body["phase"] == "presales"
    assert body["client_name"] == "Overview Basics Client"
    # create_project defaults owner_id to the creating user (projects.py) when no client/
    # opportunity owner exists yet -- the Director who created it here, not unassigned.
    assert body["owner_id"] == str(director_user.id)
    assert body["owner_name"] == director_user.name
    assert body["opportunity_id"] is None


def test_overview_404_for_unknown_project(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.get("/projects/00000000-0000-0000-0000-000000000000/overview", headers=headers)
    assert res.status_code == 404, res.text


# ---------------------------------------------------------------------------
# Document-chain pending items and their waiting-on classification
# ---------------------------------------------------------------------------


def test_overview_pending_item_when_no_cost_sheet_yet(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "No Cost Sheet Client")
    project_id = _create_project(client, headers, client_id)

    body = _overview(client, headers, project_id)
    items = {i["source"]: i for i in body["pending_items"]}
    assert items["cost_sheet"]["waiting_on"] == "us"
    assert "Cost Sheet" in items["cost_sheet"]["label"]


def test_overview_pending_item_estimate_sent_is_waiting_on_client(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "Sent Estimate Client")
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    _satisfy_project_readiness(client, headers, project_id)
    _sent_estimate(client, headers, project_id, project_sport_id)

    body = _overview(client, headers, project_id)
    items = {i["source"]: i for i in body["pending_items"]}
    assert items["estimate"]["waiting_on"] == "client"
    assert "estimate" not in items or items["estimate"]["label"]
    assert "cost_sheet" not in items  # verified, resolved -- not a blocker any more


def test_overview_pending_item_quotation_sent_is_waiting_on_client(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "Sent Quotation Client")
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    _satisfy_project_readiness(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)
    option_id = estimate["options"][0]["id"]
    _approve_option(client, headers, estimate["id"], option_id)
    quotation = _released_quotation(client, headers, project_id, estimate["id"], option_id)
    res = client.post(f"/quotations/{quotation['id']}/send", headers=headers)
    assert res.status_code == 200, res.text

    body = _overview(client, headers, project_id)
    items = {i["source"]: i for i in body["pending_items"]}
    assert items["quotation"]["waiting_on"] == "client"


def test_overview_quotation_draft_below_floor_label_hides_below_floor_wording_from_sales(client, director_user, db_session):
    """K.3: below_floor is stripped from a Sales user's own QuotationOut -- the Overview
    pending-item label must not leak the word back in as plain text either."""
    director_headers = _director_headers(client, director_user)
    sales_headers = _sales_headers(client, db_session)
    client_id = _create_client_record(client, director_headers, "Below Floor Client")
    project_id = _create_project(client, director_headers, client_id)
    project_sport_id = _add_project_sport(client, director_headers, project_id)
    _verified_cost_sheet(client, director_headers, project_id, cost_total=850000)
    _satisfy_project_readiness(client, director_headers, project_id)
    estimate = _sent_estimate(client, director_headers, project_id, project_sport_id)
    option_id = estimate["options"][0]["id"]
    _approve_option(client, director_headers, estimate["id"], option_id)
    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id], "discount_type": "percent", "discount_value": 90},
        headers=director_headers,
    ).json()
    assert quotation["below_floor"] is True

    director_body = _overview(client, director_headers, project_id)
    director_items = {i["source"]: i for i in director_body["pending_items"]}
    assert "below floor" in director_items["quotation"]["label"].lower()

    sales_body = _overview(client, sales_headers, project_id)
    sales_items = {i["source"]: i for i in sales_body["pending_items"]}
    assert "below floor" not in sales_items["quotation"]["label"].lower()
    assert "Director release" in sales_items["quotation"]["label"]


# ---------------------------------------------------------------------------
# Readiness gaps
# ---------------------------------------------------------------------------


def test_overview_readiness_gaps_reflect_missing_requirements(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post("/clients", json={"name": "Bare Overview Client", "type": "school"}, headers=headers)
    client_id = res.json()["id"]
    project_id = _create_project(client, headers, client_id)

    body = _overview(client, headers, project_id)
    assert body["readiness_visible"] is True
    assert body["readiness"]["client_identity_passed"] is False
    assert "Contact person name" in body["readiness"]["client_identity_missing"]
    checks = {c["key"]: c for c in body["readiness"]["checks"]}
    assert set(checks) == {"site_survey", "scope", "sport"}
    assert all(not c["passed"] for c in checks.values())


def test_overview_readiness_hidden_for_procurement_and_site_engineer(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, director_headers, "Readiness Hidden Client")
    project_id = _create_project(client, director_headers, client_id)

    for headers_fn in (_procurement_headers, _site_engineer_headers):
        headers = headers_fn(client, db_session)
        body = _overview(client, headers, project_id)
        assert body["readiness_visible"] is False
        assert body["readiness"] is None


def test_overview_document_chain_items_hidden_for_procurement(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    procurement_headers = _procurement_headers(client, db_session)
    client_id = _create_client_record(client, director_headers, "Doc Chain Hidden Client")
    project_id = _create_project(client, director_headers, client_id)

    body = _overview(client, procurement_headers, project_id)
    sources = {i["source"] for i in body["pending_items"]}
    assert "cost_sheet" not in sources
    assert "estimate" not in sources
    assert "quotation" not in sources


# ---------------------------------------------------------------------------
# Readiness exception requests
# ---------------------------------------------------------------------------


def test_overview_shows_pending_readiness_exception_and_excludes_decided_ones(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    pm_headers = _pm_headers(client, db_session)
    client_id = _create_client_record(client, director_headers, "Exception Overview Client")
    project_id = _create_project(client, director_headers, client_id)
    project_sport_id = _add_project_sport(client, director_headers, project_id)
    _verified_cost_sheet(client, director_headers, project_id)
    client.post(f"/projects/{project_id}/scope-items/confirm-empty", headers=director_headers)
    estimate = _draft_estimate(client, director_headers, project_id, project_sport_id)

    req = client.post(
        "/readiness-exceptions",
        json={"document_type": "estimate", "document_id": estimate["id"], "check_key": "site_survey", "reason": "test"},
        headers=pm_headers,
    ).json()

    body = _overview(client, director_headers, project_id)
    exception_items = [i for i in body["pending_items"] if i["source"] == "readiness_exception"]
    assert len(exception_items) == 1
    assert exception_items[0]["waiting_on"] == "us"

    client.post(f"/readiness-exceptions/{req['id']}/approve", headers=director_headers)
    body = _overview(client, director_headers, project_id)
    assert not [i for i in body["pending_items"] if i["source"] == "readiness_exception"]


# ---------------------------------------------------------------------------
# Follow-ups: waiting-on classification and per-entity role visibility
# ---------------------------------------------------------------------------


def test_overview_follow_up_item_carries_waiting_party(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "Follow Up Client")
    project_id = _create_project(client, headers, client_id)

    created = client.post(
        "/follow-ups",
        json={
            "entity_type": "project", "entity_id": project_id,
            "next_action": "Chase vendor for structure quote", "due_date": str(date.today() + timedelta(days=2)),
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    patched = client.patch(
        f"/follow-ups/{created.json()['id']}", json={"status": "waiting", "waiting_party": "vendor"}, headers=headers,
    )
    assert patched.status_code == 200, patched.text

    body = _overview(client, headers, project_id)
    follow_up_items = [i for i in body["pending_items"] if i["source"] == "follow_up"]
    assert len(follow_up_items) == 1
    assert follow_up_items[0]["waiting_on"] == "vendor"
    assert follow_up_items[0]["label"] == "Chase vendor for structure quote"


def test_overview_follow_up_visibility_matches_entity_role_gate(client, director_user, db_session):
    """A site_engineer can reach Overview (Project's own read_roles include it) but must not
    see the linked Opportunity's follow-ups -- opportunities.py never grants that role read
    access to Opportunities at all."""
    director_headers = _director_headers(client, director_user)
    site_engineer_headers = _site_engineer_headers(client, db_session)
    client_id = _create_client_record(client, director_headers, "FollowUp Visibility Client")
    opp = client.post(
        "/opportunities", json={"lead_name": "Overview FollowUp Lead", "next_follow_up_date": "2099-01-01"},
        headers=director_headers,
    ).json()
    client.patch(
        f"/opportunities/{opp['id']}/stage", json={"stage": "qualified", "next_follow_up_date": "2099-01-01"},
        headers=director_headers,
    )
    client.patch(f"/opportunities/{opp['id']}/link-client", json={"client_id": client_id}, headers=director_headers)
    project_id = _create_project(client, director_headers, client_id, opportunity_id=opp["id"])

    res = client.post(
        "/follow-ups",
        json={
            "entity_type": "opportunity", "entity_id": opp["id"],
            "next_action": "Opportunity-only follow-up", "due_date": str(date.today() + timedelta(days=1)),
        },
        headers=director_headers,
    )
    assert res.status_code == 201, res.text

    director_body = _overview(client, director_headers, project_id)
    assert any(i["label"] == "Opportunity-only follow-up" for i in director_body["pending_items"])

    site_engineer_body = _overview(client, site_engineer_headers, project_id)
    assert not any(i["label"] == "Opportunity-only follow-up" for i in site_engineer_body["pending_items"])


def test_overview_specialist_assignment_matches_current_follow_ups_access_behaviour(client, director_user, db_session):
    """Documents CURRENT access behaviour verified directly against the real, already-merged
    /follow-ups API -- this is NOT a claim that the behaviour is the intended design, and it
    is NOT proof specialist assignment "works" in the sense the correction plan's own
    decisions log describes. It only establishes that Overview introduces no NEW gap: it
    reuses the exact same resolve_entity + check_follow_up_access ownership condition
    /follow-ups itself already applies, so Overview cannot be stricter (or looser) than the
    real system, whatever that system's own behaviour turns out to be.

    Reconciling an earlier WP5 live-UI walkthrough's "specialist reassignment" claim against
    this probe (see the paired test right below, which reproduces both states side by side):
    with Amendment 60's sales_own_records_only switch ON, a Sales specialist explicitly
    assigned a FollowUp.owner_id on a Project/Opportunity they do NOT own gets NOTHING back
    from entity-scoped (404), owner_id=me, or the org-wide /follow-ups queries -- confirmed
    for both entity_type=project and entity_type=opportunity, so the entity type is not what
    explains the earlier claim. With the switch OFF, the SAME specialist's owner_id=me query
    DOES return their row -- ownership.scoping_applies() only ever restricts a Sales user
    while that switch is on. This shows the two findings CAN coexist without contradiction
    (they describe different preconditions), which is different from proving they DO: which
    switch state the earlier WP5 walkthrough actually used was never recorded and is NOT
    confirmed either way -- do not assert it was run with the switch off, only that if it was,
    there is no conflict with this probe's switch-on result.

    Net: with the switch ON, an explicitly-assigned specialist who does not own the parent
    record currently CANNOT see their own assignment anywhere in the real system --
    owner_explicitly_assigned has no read-access effect anywhere in this codebase; it exists
    only to stop silent reassignment on the FollowUp row itself when the parent's owner
    changes (app/models/follow_up.py's own docstring), never to grant extra visibility. This
    is a real, narrow access-behaviour gap worth its own tracked correction outside Project
    Overview's scope -- Overview does not attempt to fix it, must not silently grant this
    specialist broader parent-record access on its own initiative either, and this gap must be
    called out explicitly in the PR/completion report, not left in test comments/memory only."""
    director_headers = _director_headers(client, director_user)
    sales_owner = _role_headers(client, db_session, UserRole.SALES, "overview-specialist-owner@test.local")
    sales_specialist = _role_headers(client, db_session, UserRole.SALES, "overview-specialist@test.local")
    specialist_id = client.get("/auth/me", headers=sales_specialist).json()["id"]

    switch = client.put("/ownership/switch", json={"on": True}, headers=director_headers)
    assert switch.status_code == 200, switch.text

    client_id = _create_client_record(client, sales_owner, "Specialist Assignment Client")
    project_id = _create_project(client, sales_owner, client_id)

    assigned = client.post(
        "/follow-ups",
        json={
            "entity_type": "project", "entity_id": project_id,
            "next_action": "Specialist task", "due_date": "2099-01-01", "owner_id": specialist_id,
        },
        headers=director_headers,
    )
    assert assigned.status_code == 201, assigned.text
    assert assigned.json()["owner_explicitly_assigned"] is True

    # Current /follow-ups behaviour with the switch ON: none of its three query shapes
    # surface this specialist's own assignment.
    assert client.get(f"/follow-ups?entity_type=project&entity_id={project_id}", headers=sales_specialist).status_code == 404
    assert client.get(f"/follow-ups?owner_id={specialist_id}", headers=sales_specialist).json() == []
    assert client.get("/follow-ups", headers=sales_specialist).json() == []

    # Overview matches it exactly, introducing no new gap: the specialist cannot open this
    # project's Overview at all (blocked by enforce_own_records on the project_id path param,
    # same as any other non-owning Sales user, independent of anything follow-up-specific).
    res = client.get(f"/projects/{project_id}/overview", headers=sales_specialist)
    assert res.status_code == 404, res.text

    client.put("/ownership/switch", json={"on": False}, headers=director_headers)


def test_reconcile_specialist_visibility_depends_on_the_own_records_switch(client, director_user, db_session):
    """The reconciliation itself, as a reproducible test rather than a one-off manual probe:
    the exact same specialist-assignment setup produces DIFFERENT, both-genuine outcomes
    depending only on whether Amendment 60's sales_own_records_only switch is on or off --
    concrete evidence that the earlier WP5 walkthrough's "specialist reassignment ... visible"
    claim and this session's own switch-ON probe COULD both be true without conflict, since
    they'd describe different preconditions. This test does NOT establish which state the
    earlier walkthrough actually used -- that was never recorded and stays unconfirmed; only
    that switch state is a sufficient, non-contradictory explanation. Not part of Project
    Overview's own behaviour (Overview is unaffected either way, since it always requires the
    viewer to already have entity-level access) -- kept here because it documents the exact
    real-system condition a separate, tracked correction for the switch-ON gap would need to
    address, and because it must be surfaced in the PR/completion report as an open gap, not
    resolved into a false certainty here."""
    director_headers = _director_headers(client, director_user)
    sales_owner = _role_headers(client, db_session, UserRole.SALES, "reconcile-owner@test.local")
    sales_specialist = _role_headers(client, db_session, UserRole.SALES, "reconcile-specialist@test.local")
    specialist_id = client.get("/auth/me", headers=sales_specialist).json()["id"]

    client_id = _create_client_record(client, sales_owner, "Reconcile Client")
    project_id = _create_project(client, sales_owner, client_id)
    assigned = client.post(
        "/follow-ups",
        json={
            "entity_type": "project", "entity_id": project_id,
            "next_action": "Reconcile task", "due_date": "2099-01-01", "owner_id": specialist_id,
        },
        headers=director_headers,
    )
    assert assigned.status_code == 201, assigned.text

    # Switch OFF (the default): the specialist's own "my follow-ups" query sees it.
    off_result = client.get(f"/follow-ups?owner_id={specialist_id}", headers=sales_specialist)
    assert off_result.status_code == 200, off_result.text
    assert len(off_result.json()) == 1

    # Switch ON: the same query, same row, same specialist -- now empty.
    client.put("/ownership/switch", json={"on": True}, headers=director_headers)
    on_result = client.get(f"/follow-ups?owner_id={specialist_id}", headers=sales_specialist)
    assert on_result.status_code == 200, on_result.text
    assert on_result.json() == []

    client.put("/ownership/switch", json={"on": False}, headers=director_headers)


# ---------------------------------------------------------------------------
# Payment blockers
# ---------------------------------------------------------------------------


def test_overview_payment_blocker_visible_only_to_pm_director_ca_tax(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    work_order_id, project_id, order_value = _won_work_order(client, director_headers, name="Overview Payments Client")
    _milestone(client, director_headers, work_order_id, order_value, date.today() - timedelta(days=10))

    for headers_fn in (_pm_headers, _ca_tax_headers):
        headers = headers_fn(client, db_session)
        body = _overview(client, headers, project_id)
        assert body["payment_visible"] is True
        assert body["payment_blocker"] is not None
        assert body["payment_blocker"]["overdue"] is True

    for headers_fn in (_sales_headers, _procurement_headers, _site_engineer_headers):
        headers = headers_fn(client, db_session)
        body = _overview(client, headers, project_id)
        assert body["payment_visible"] is False
        assert body["payment_blocker"] is None


def test_overview_no_payment_blocker_when_nothing_overdue(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "No Blocker Client")
    project_id = _create_project(client, headers, client_id)

    body = _overview(client, headers, project_id)
    assert body["payment_visible"] is True
    assert body["payment_blocker"] is None


# ---------------------------------------------------------------------------
# Vendor / price-request blockers: explicitly unavailable, not zero
# ---------------------------------------------------------------------------


def test_overview_vendor_price_requests_marked_explicitly_unavailable(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "Vendor Blocker Client")
    project_id = _create_project(client, headers, client_id)

    body = _overview(client, headers, project_id)
    assert body["vendor_price_requests"]["available"] is False
    assert body["vendor_price_requests"]["items"] == []
    assert body["vendor_price_requests"]["reason"] is not None


# ---------------------------------------------------------------------------
# Latest activity: Director/Admin only, matching audit_log.py's own ROLES
# ---------------------------------------------------------------------------


def test_overview_latest_activity_visible_only_to_director(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, director_headers, "Activity Client")
    project_id = _create_project(client, director_headers, client_id)  # create_project itself is audit-logged (WP3)

    director_body = _overview(client, director_headers, project_id)
    assert director_body["activity_visible"] is True
    assert len(director_body["latest_activity"]) >= 1
    assert director_body["latest_activity"][0]["document_type"] == "project"

    pm_body = _overview(client, _pm_headers(client, db_session), project_id)
    assert pm_body["activity_visible"] is False
    assert pm_body["latest_activity"] == []


# ---------------------------------------------------------------------------
# Amendment 60 ownership scoping -- automatic via enforce_own_records on project_id
# ---------------------------------------------------------------------------


def test_overview_sales_ownership_scoping_blocks_a_project_owned_by_another_sales_user(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    sales_a = _role_headers(client, db_session, UserRole.SALES, "overview-sales-a@test.local")
    sales_b = _role_headers(client, db_session, UserRole.SALES, "overview-sales-b@test.local")

    switch = client.put("/ownership/switch", json={"on": True}, headers=director_headers)
    assert switch.status_code == 200, switch.text

    client_id = _create_client_record(client, sales_a, "Ownership Scoped Client")
    project_id = _create_project(client, sales_a, client_id)

    own_body = _overview(client, sales_a, project_id)
    assert own_body["project_id"] == project_id

    res = client.get(f"/projects/{project_id}/overview", headers=sales_b)
    assert res.status_code == 404, res.text

    client.put("/ownership/switch", json={"on": False}, headers=director_headers)
