"""WP7 (correction plan, 2026-09-28): readiness checks before document issuance.

A non-waivable client-identity check (linked Client, a name, a contact-person name, and a
phone or email -- GSTIN stays optional) and three waivable checks (Site Survey completed,
Scope confirmed, a sport selected), enforced only at the moment an Estimate is sent or a
Quotation/Tender is released -- never at draft creation/editing, and never touching the
pre-existing, separate Cost Sheet skip/approval-evidence-waiver gates."""
from tests.test_quotations_admin import (
    _add_project_sport,
    _approve_option,
    _create_client_record,
    _create_project,
    _director_headers,
    _role_headers,
    _satisfy_project_readiness,
    _verified_cost_sheet,
)
from app.models.user import UserRole


def _bare_client(client, headers, name="Bare Client"):
    """A Client with none of WP7's identity fields -- no contact_name, no phone, no
    email -- the state that must hard-block send/release."""
    res = client.post("/clients", json={"name": name, "type": "school"}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _pm_headers(client, db_session):
    return _role_headers(client, db_session, UserRole.PM, "pm-readiness@test.local")


def _sales_headers(client, db_session):
    return _role_headers(client, db_session, UserRole.SALES, "sales-readiness@test.local")


def _draft_estimate(client, headers, project_id, project_sport_id, cost_for_option=850000):
    res = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": cost_for_option}]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def _draft_quotation(client, headers, project_id, estimate_id, option_id):
    res = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate_id, "included_option_ids": [option_id]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------------------
# Client identity -- non-waivable
# ---------------------------------------------------------------------------


def test_missing_client_identity_blocks_sending_an_estimate(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _bare_client(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    _satisfy_project_readiness(client, headers, project_id)
    estimate = _draft_estimate(client, headers, project_id, project_sport_id)

    res = client.post(f"/estimates/{estimate['id']}/send", headers=headers)
    assert res.status_code == 422, res.text
    assert "Contact person name" in res.json()["detail"]
    assert "phone or email" in res.json()["detail"]
    # No partial change: still Draft.
    assert client.get(f"/estimates/{estimate['id']}", headers=headers).json()["status"] == "draft"


def test_missing_client_identity_blocks_releasing_a_quotation(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _bare_client(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    _satisfy_project_readiness(client, headers, project_id)
    estimate = _draft_estimate(client, headers, project_id, project_sport_id)
    option_id = estimate["options"][0]["id"]
    _approve_option(client, headers, estimate["id"], option_id)
    quotation = _draft_quotation(client, headers, project_id, estimate["id"], option_id)

    res = client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    assert res.status_code == 422, res.text
    assert "Contact person name" in res.json()["detail"]
    assert client.get(f"/quotations/{quotation['id']}", headers=headers).json()["status"] == "draft"


def test_missing_client_identity_blocks_releasing_a_tender_mode_quotation(client, director_user):
    """Tender release has no separate endpoint -- it is release_quotation on a Quotation
    whose Project has tender_mode set, so the same client-identity block must apply to it
    without any extra wiring."""
    headers = _director_headers(client, director_user)
    res = client.post(
        "/clients", json={"name": "Tender Body", "type": "government"}, headers=headers
    )
    assert res.status_code == 201, res.text
    client_id = res.json()["id"]
    project_id = _create_project(client, headers, client_id)
    assert client.get(f"/projects/{project_id}", headers=headers).json()["tender_mode"] is True
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    _satisfy_project_readiness(client, headers, project_id)
    estimate = _draft_estimate(client, headers, project_id, project_sport_id)
    option_id = estimate["options"][0]["id"]
    _approve_option(client, headers, estimate["id"], option_id)
    quotation = _draft_quotation(client, headers, project_id, estimate["id"], option_id)

    res = client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    assert res.status_code == 422, res.text


def test_client_identity_does_not_require_gstin(client, director_user):
    """GSTIN stays the existing informational-only field -- a client with everything WP7
    asks for but no gstin must pass identity cleanly."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "GSTIN-less Client")
    project_id = _create_project(client, headers, client_id)
    res = client.get(f"/projects/{project_id}/readiness", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["client_identity_passed"] is True


def test_incomplete_client_can_still_be_saved_and_documents_drafted_and_edited(client, director_user):
    """WP7 never blocks drafting -- only the send/release action itself."""
    headers = _director_headers(client, director_user)
    client_id = _bare_client(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate = _draft_estimate(client, headers, project_id, project_sport_id)
    option_id = estimate["options"][0]["id"]
    # Editing option client-status (a draft-stage action) is unaffected.
    _approve_option(client, headers, estimate["id"], option_id)
    quotation = _draft_quotation(client, headers, project_id, estimate["id"], option_id)
    assert quotation["status"] == "draft"
    # The bare client itself can still be edited/saved with more info later.
    res = client.patch(f"/clients/{client_id}", json={"contact_name": "Filled In Later"}, headers=headers)
    assert res.status_code == 200, res.text


# ---------------------------------------------------------------------------
# Waivable checks: computed readiness + confirm-empty-scope
# ---------------------------------------------------------------------------


def test_computed_readiness_reports_all_three_waivable_checks_as_blocking_by_default(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "Fresh Project Client")
    project_id = _create_project(client, headers, client_id)

    res = client.get(f"/projects/{project_id}/readiness", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    keys = {c["key"]: c for c in body["checks"]}
    assert set(keys) == {"site_survey", "scope", "sport"}
    for c in keys.values():
        assert c["passed"] is False
        assert c["waivable"] is True
        assert c["exception"] is None


def test_confirm_empty_scope_satisfies_the_scope_check(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "Empty Scope Client")
    project_id = _create_project(client, headers, client_id)

    res = client.post(f"/projects/{project_id}/scope-items/confirm-empty", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["scope_confirmed_empty_at"] is not None
    assert res.json()["scope_confirmed_empty_by_id"] == str(director_user.id)

    readiness = client.get(f"/projects/{project_id}/readiness", headers=headers).json()
    scope_check = next(c for c in readiness["checks"] if c["key"] == "scope")
    assert scope_check["passed"] is True


def test_a_real_scope_item_also_satisfies_the_scope_check_without_confirming_empty(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "Real Scope Client")
    project_id = _create_project(client, headers, client_id)
    scope_item_id = next(s["id"] for s in client.get("/scope-items", headers=headers).json())
    res = client.post(
        f"/projects/{project_id}/scope-items", json={"scope_item_id": scope_item_id}, headers=headers
    )
    assert res.status_code == 201, res.text

    readiness = client.get(f"/projects/{project_id}/readiness", headers=headers).json()
    scope_check = next(c for c in readiness["checks"] if c["key"] == "scope")
    assert scope_check["passed"] is True


def test_adding_a_sport_satisfies_the_sport_check(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "Sport Check Client")
    project_id = _create_project(client, headers, client_id)
    _add_project_sport(client, headers, project_id)

    readiness = client.get(f"/projects/{project_id}/readiness", headers=headers).json()
    sport_check = next(c for c in readiness["checks"] if c["key"] == "sport")
    assert sport_check["passed"] is True


# ---------------------------------------------------------------------------
# Readiness exceptions: PM requests, Director approves/rejects; Director direct-records
# ---------------------------------------------------------------------------


def test_pm_requests_an_exception_and_it_blocks_until_a_director_approves_it(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    pm_headers = _pm_headers(client, db_session)
    client_id = _create_client_record(client, director_headers, "PM Request Client")
    project_id = _create_project(client, director_headers, client_id)
    project_sport_id = _add_project_sport(client, director_headers, project_id)
    _verified_cost_sheet(client, director_headers, project_id)
    client.post(f"/projects/{project_id}/scope-items/confirm-empty", headers=director_headers)
    estimate = _draft_estimate(client, director_headers, project_id, project_sport_id)

    blocked = client.post(f"/estimates/{estimate['id']}/send", headers=director_headers)
    assert blocked.status_code == 422, blocked.text
    assert "Site Survey" in blocked.json()["detail"]

    req = client.post(
        "/readiness-exceptions",
        json={
            "document_type": "estimate", "document_id": estimate["id"],
            "check_key": "site_survey", "reason": "Client site inaccessible this week",
        },
        headers=pm_headers,
    )
    assert req.status_code == 201, req.text
    assert req.json()["status"] == "requested"
    exception_id = req.json()["id"]

    # Still pending -- a PM's own request does not itself satisfy the check.
    still_blocked = client.post(f"/estimates/{estimate['id']}/send", headers=director_headers)
    assert still_blocked.status_code == 422, still_blocked.text
    assert "pending Director approval" in still_blocked.json()["detail"]

    approved = client.post(f"/readiness-exceptions/{exception_id}/approve", headers=director_headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by_id"] == str(director_user.id)

    ok = client.post(f"/estimates/{estimate['id']}/send", headers=director_headers)
    assert ok.status_code == 200, ok.text


def test_a_director_rejected_exception_leaves_the_check_blocking(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    pm_headers = _pm_headers(client, db_session)
    client_id = _create_client_record(client, director_headers, "Rejected Exception Client")
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

    rejected = client.post(
        f"/readiness-exceptions/{req['id']}/reject", json={"reason": "Not a valid excuse"}, headers=director_headers
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"

    still_blocked = client.post(f"/estimates/{estimate['id']}/send", headers=director_headers)
    assert still_blocked.status_code == 422, still_blocked.text

    # A rejected exception does not block a fresh request for the same check.
    second = client.post(
        "/readiness-exceptions",
        json={"document_type": "estimate", "document_id": estimate["id"], "check_key": "site_survey", "reason": "Try again"},
        headers=pm_headers,
    )
    assert second.status_code == 201, second.text
    assert second.json()["id"] != req["id"]
    assert second.json()["status"] == "requested"


def test_a_director_recording_an_exception_is_auto_approved(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "Director Direct Client")
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    client.post(f"/projects/{project_id}/scope-items/confirm-empty", headers=headers)
    estimate = _draft_estimate(client, headers, project_id, project_sport_id)

    res = client.post(
        "/readiness-exceptions",
        json={"document_type": "estimate", "document_id": estimate["id"], "check_key": "site_survey", "reason": "Director waives"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "approved"
    assert res.json()["approved_by_id"] == str(director_user.id)

    ok = client.post(f"/estimates/{estimate['id']}/send", headers=headers)
    assert ok.status_code == 200, ok.text


def test_requesting_the_same_check_twice_is_idempotent(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    pm_headers = _pm_headers(client, db_session)
    client_id = _create_client_record(client, headers, "Idempotent Request Client")
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate = _draft_estimate(client, headers, project_id, project_sport_id)

    first = client.post(
        "/readiness-exceptions",
        json={"document_type": "estimate", "document_id": estimate["id"], "check_key": "scope", "reason": "test"},
        headers=pm_headers,
    ).json()
    second = client.post(
        "/readiness-exceptions",
        json={"document_type": "estimate", "document_id": estimate["id"], "check_key": "scope", "reason": "test again"},
        headers=pm_headers,
    ).json()
    assert second["id"] == first["id"]


def test_sales_can_neither_request_nor_approve_a_readiness_exception(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    sales_headers = _sales_headers(client, db_session)
    client_id = _create_client_record(client, director_headers, "Sales Blocked Client")
    project_id = _create_project(client, director_headers, client_id)
    project_sport_id = _add_project_sport(client, director_headers, project_id)
    _verified_cost_sheet(client, director_headers, project_id)
    estimate = _draft_estimate(client, director_headers, project_id, project_sport_id)

    res = client.post(
        "/readiness-exceptions",
        json={"document_type": "estimate", "document_id": estimate["id"], "check_key": "scope", "reason": "test"},
        headers=sales_headers,
    )
    assert res.status_code == 403, res.text

    req = client.post(
        "/readiness-exceptions",
        json={"document_type": "estimate", "document_id": estimate["id"], "check_key": "scope", "reason": "test"},
        headers=director_headers,
    ).json()
    approve = client.post(f"/readiness-exceptions/{req['id']}/approve", headers=sales_headers)
    assert approve.status_code == 403, approve.text


# ---------------------------------------------------------------------------
# A new revision does not inherit an earlier revision's exception
# ---------------------------------------------------------------------------


def test_a_new_quotation_revision_does_not_inherit_the_prior_revisions_exception(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "Revision Exception Client")
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    client.post(f"/projects/{project_id}/scope-items/confirm-empty", headers=headers)
    estimate = _draft_estimate(client, headers, project_id, project_sport_id)
    option_id = estimate["options"][0]["id"]
    _approve_option(client, headers, estimate["id"], option_id)
    quotation = _draft_quotation(client, headers, project_id, estimate["id"], option_id)

    client.post(
        "/readiness-exceptions",
        json={"document_type": "quotation", "document_id": quotation["id"], "check_key": "site_survey", "reason": "waived"},
        headers=headers,
    )
    released = client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    assert released.status_code == 200, released.text
    sent = client.post(f"/quotations/{quotation['id']}/send", headers=headers)
    assert sent.status_code == 200, sent.text

    # A major edit on a Sent quotation creates a brand-new row (new id) -- see
    # revise_quotation's own docstring (app/api/documents.py).
    revised = client.post(
        f"/quotations/{quotation['id']}/revise",
        json={"included_option_ids": [option_id]},
        headers=headers,
    )
    assert revised.status_code == 200, revised.text
    new_quotation_id = revised.json()["id"]
    assert new_quotation_id != quotation["id"]
    assert revised.json()["status"] == "draft"

    still_blocked = client.post(f"/quotations/{new_quotation_id}/release", headers=headers)
    assert still_blocked.status_code == 422, still_blocked.text
    assert "Site Survey" in still_blocked.json()["detail"]


# ---------------------------------------------------------------------------
# Interaction with the pre-existing, separate Cost Sheet skip / approval-evidence flow
# ---------------------------------------------------------------------------


def test_the_authorised_cost_sheet_skip_flow_still_works_alongside_readiness(client, director_user):
    """WP7 adds no new gate to Cost Sheet skipping (skip_requests.py) or to the
    approval-evidence waiver on an Estimate option (_enforce_approval_evidence) --
    both are untouched, separate mechanisms this file never calls into."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "Skip Flow Client")
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _satisfy_project_readiness(client, headers, project_id)

    # The pre-existing, two-step Cost Sheet skip flow (SkipRequest): PM/Director requests,
    # PM/Director approves with a ballpark cost_total, producing an auto-generated,
    # Unverified Cost Sheet that still needs its own /verify call.
    req = client.post(
        f"/projects/{project_id}/skip-requests",
        json={"stage_skipped": "cost_sheet", "reason": "Fast-track"},
        headers=headers,
    )
    assert req.status_code == 201, req.text
    approved = client.post(
        f"/skip-requests/{req.json()['id']}/approve", json={"cost_total": 850000}, headers=headers
    )
    assert approved.status_code == 200, approved.text
    cost_sheet_id = approved.json()["resulting_cost_sheet_id"]
    verify = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert verify.status_code == 200, verify.text

    estimate = _draft_estimate(client, headers, project_id, project_sport_id)
    option_id = estimate["options"][0]["id"]
    _approve_option(client, headers, estimate["id"], option_id)

    sent = client.post(f"/estimates/{estimate['id']}/send", headers=headers)
    assert sent.status_code == 200, sent.text
