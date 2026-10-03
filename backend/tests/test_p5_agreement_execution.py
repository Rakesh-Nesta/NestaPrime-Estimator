"""P5 contract revision 7 -- HTTP-level acceptance cases (the concurrency cases live in
test_p5_concurrency.py; migration/adoption/rollback in test_p5_adoption_and_migration.py).

AC numbers in test names/docstrings are the contract's own."""

from datetime import date, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.audit_log import AuditLogEntry
from app.models.p5 import (
    Agreement,
    AuthorizationStatus,
    AuthorizationTransitionError,
    ProjectExecutionAuthorization,
    ProjectTask,
    ProjectTeamMember,
)
from tests.p5_helpers import (
    add_signatory,
    authorize,
    client_sign,
    create_user_via_api,
    draft_agreement,
    execute_agreement,
    make_execution_ready,
    make_user,
    quotation_project,
    staff_site_engineer,
    upload_agreement_document,
    user_headers,
)
from tests.test_work_orders import _director_headers, _won_quotation
from tests.valid_files import valid_pdf


@pytest.fixture()
def won(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, quotation_id = _won_quotation(client, headers)
    _, client_id = quotation_project(client, headers, quotation_id)
    return {"headers": headers, "project_id": project_id, "quotation_id": quotation_id, "client_id": client_id}


def _wo(client, w):
    return client.post(f"/quotations/{w['quotation_id']}/work-order", headers=w["headers"])


def _audit_count(db_session, document_type, document_id=None):
    db_session.expire_all()
    q = db_session.query(AuditLogEntry).filter(AuditLogEntry.document_type == document_type)
    if document_id is not None:
        q = q.filter(AuditLogEntry.document_id == document_id)
    return q.count()


# ---------------------------------------------------------------- AC-1 .. AC-4: the blocked starts and the start


def test_ac01_a_won_quotation_with_no_agreement_cannot_start(client, won):
    res = _wo(client, won)
    assert res.status_code == 409
    assert "No Agreement exists" in res.json()["detail"]


def test_ac02_a_drafted_agreement_blocks_a_work_order_even_with_a_full_team(client, won):
    draft_agreement(client, won["headers"], won["quotation_id"])
    staff_site_engineer(client, won["headers"], won["project_id"])
    res = _wo(client, won)
    assert res.status_code == 409
    assert "not executed (status: drafted)" in res.json()["detail"]
    ready = client.get(f"/quotations/{won['quotation_id']}/execution-readiness", headers=won["headers"]).json()
    assert ready["agreement_executed"] is False and ready["active_delivery_team"] is True


def test_ac03_an_executed_agreement_without_an_eligible_site_engineer_cannot_start(client, won):
    execute_agreement(client, won["headers"], won["quotation_id"], won["client_id"])
    res = _wo(client, won)
    assert res.status_code == 409
    ready = client.get(f"/quotations/{won['quotation_id']}/execution-readiness", headers=won["headers"]).json()
    assert ready["agreement_executed"] is True and ready["active_delivery_team"] is False
    assert authorize(client, won["headers"], won["quotation_id"]).status_code == 409


def test_ac04_all_checks_pass_authorize_then_the_work_order_is_created(client, won):
    execute_agreement(client, won["headers"], won["quotation_id"], won["client_id"])
    staff_site_engineer(client, won["headers"], won["project_id"])
    # ready but not yet authorized: still refused, naming the missing authorization
    res = _wo(client, won)
    assert res.status_code == 409 and "authorization" in res.json()["detail"]
    auth = authorize(client, won["headers"], won["quotation_id"])
    assert auth.status_code == 200 and auth.json()["status"] == "authorized"
    res = _wo(client, won)
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "awarded"


# ---------------------------------------------------------------- AC-5 / AC-6: happy path and planning-before-authorization


def test_ac05_happy_path_end_to_end_every_step_audited(client, won, db_session):
    h = won["headers"]
    engineer = make_user(db_session, "site_engineer")
    info = make_execution_ready(client, h, won["quotation_id"], engineer={"id": str(engineer.id)})
    wo = _wo(client, won)
    assert wo.status_code == 201
    work_order_id = wo.json()["id"]

    milestone = client.post(
        f"/projects/{won['project_id']}/milestones",
        json={"name": "Flooring complete", "target_date": str(date.today() + timedelta(days=30)), "work_order_id": work_order_id},
        headers=h,
    )
    assert milestone.status_code == 201, milestone.text
    task = client.post(
        f"/projects/{won['project_id']}/tasks",
        json={"title": "Lay the base", "assigned_to_id": info["member"]["id"], "milestone_id": milestone.json()["id"]},
        headers=h,
    )
    assert task.status_code == 201, task.text

    eng_user = engineer
    eh = user_headers(client, eng_user)
    started = client.patch(f"/tasks/{task.json()['id']}", json={"status": "in_progress"}, headers=eh)
    assert started.status_code == 200, started.text
    done = client.patch(f"/tasks/{task.json()['id']}", json={"status": "done"}, headers=eh)
    assert done.status_code == 200 and done.json()["status"] == "done"

    issue = client.post(
        f"/projects/{won['project_id']}/site-issues", json={"title": "Drainage pooling", "severity": "high"}, headers=eh
    )
    assert issue.status_code == 201, issue.text
    resolved = client.patch(
        f"/site-issues/{issue.json()['id']}", json={"status": "resolved", "resolution_reason": "Re-graded the slope"}, headers=h
    )
    assert resolved.status_code == 200 and resolved.json()["resolution_reason"] == "Re-graded the slope"

    # every mutation wrote its own audit entry
    assert _audit_count(db_session, "agreement", info["agreement"]["id"]) >= 3  # drafted, client_signed, executed
    assert _audit_count(db_session, "execution_authorization", info["authorization"]["id"]) == 1
    assert _audit_count(db_session, "project_team_member", info["member"]["id"]) == 1
    assert _audit_count(db_session, "project_milestone", milestone.json()["id"]) == 1
    assert _audit_count(db_session, "project_task", task.json()["id"]) == 3  # created, in_progress, done
    assert _audit_count(db_session, "project_site_issue", issue.json()["id"]) == 2  # raised, resolved


def test_ac06_planning_work_can_start_before_the_agreement_or_any_team_exists(client, won):
    h = won["headers"]
    draft_agreement(client, h, won["quotation_id"])  # only drafted, nothing signed, no team at all
    task = client.post(f"/projects/{won['project_id']}/tasks", json={"title": "Collect the client signature"}, headers=h)
    assert task.status_code == 201, task.text
    assert task.json()["assigned_to_id"] is None
    assert client.patch(f"/tasks/{task.json()['id']}", json={"status": "in_progress"}, headers=h).status_code == 200
    assert client.patch(f"/tasks/{task.json()['id']}", json={"status": "done"}, headers=h).status_code == 200
    milestone = client.post(f"/projects/{won['project_id']}/milestones", json={"name": "Agreement executed"}, headers=h)
    assert milestone.status_code == 201
    # ...but the Work Order is still blocked
    assert _wo(client, won).status_code == 409


def test_planning_requires_a_won_quotation(client, director_user):
    from tests.test_work_orders import _create_client_record, _create_project

    h = _director_headers(client, director_user)
    project_id = _create_project(client, h, _create_client_record(client, h))
    res = client.post(f"/projects/{project_id}/tasks", json={"title": "Too early"}, headers=h)
    assert res.status_code == 409


# ---------------------------------------------------------------- AC-7: signature / evidence validation


def test_ac07_signature_and_evidence_mismatches_are_rejected_distinctly(client, won):
    h = won["headers"]
    agreement = draft_agreement(client, h, won["quotation_id"])
    attachment = upload_agreement_document(client, h, agreement["id"])

    # a signatory that belongs to a different client
    other_client = client.post(
        "/clients", json={"name": "Other Client", "type": "school", "contact_name": "X", "phone": "9876543211"}, headers=h
    ).json()["id"]
    foreign = add_signatory(client, h, other_client)
    res = client_sign(client, h, agreement["id"], foreign["id"], attachment["id"])
    assert res.status_code == 422 and "does not belong" in res.json()["detail"]

    # signing before the signatory's authorization date
    own = add_signatory(client, h, won["client_id"], authorized_on=date.today() - timedelta(days=5))
    res = client_sign(client, h, agreement["id"], own["id"], attachment["id"], signed_on=date.today() - timedelta(days=10))
    assert res.status_code == 422 and "not authorized on the recorded signing date" in res.json()["detail"]

    # signing after the authorization expired
    expired = add_signatory(
        client, h, won["client_id"], authorized_on=date.today() - timedelta(days=60), expiry=date.today() - timedelta(days=20),
        name="Expired Signer",
    )
    res = client_sign(client, h, agreement["id"], expired["id"], attachment["id"], signed_on=date.today() - timedelta(days=1))
    assert res.status_code == 422 and "not authorized on the recorded signing date" in res.json()["detail"]

    # a signing date in the future
    res = client_sign(client, h, agreement["id"], own["id"], attachment["id"], signed_on=date.today() + timedelta(days=2))
    assert res.status_code == 422 and "future" in res.json()["detail"]

    # a document that is not an attachment of THIS agreement
    res = client_sign(client, h, agreement["id"], own["id"], "00000000-0000-0000-0000-000000000000")
    assert res.status_code == 422 and "attachment on this Agreement" in res.json()["detail"]

    # none of the failed attempts changed anything
    fresh = client.get(f"/agreements/{agreement['id']}", headers=h).json()
    assert fresh["status"] == "drafted" and fresh["evidence_locked_at"] is None

    # the valid signature records the frozen snapshot, hash and lock
    res = client_sign(client, h, agreement["id"], own["id"], attachment["id"], signed_on=date.today())
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "client_signed"
    assert body["client_signatory_name_snapshot"] == own["name"]
    assert body["client_signatory_designation_snapshot"] == own["designation"]
    assert body["signed_document_sha256"] and body["evidence_locked_at"] and body["evidence_intact"] is True


def test_only_the_director_signs_for_nesta_and_a_pm_cannot(client, won, db_session):
    h = won["headers"]
    agreement = draft_agreement(client, h, won["quotation_id"])
    attachment = upload_agreement_document(client, h, agreement["id"])
    signatory = add_signatory(client, h, won["client_id"])
    assert client_sign(client, h, agreement["id"], signatory["id"], attachment["id"]).status_code == 200
    pm = make_user(db_session, "pm")
    pmh = user_headers(client, pm)
    assert client.post(f"/agreements/{agreement['id']}/execute", headers=pmh).status_code == 403
    assert client.post(f"/agreements/{agreement['id']}/void", json={"reason": "no way"}, headers=pmh).status_code == 403
    assert client.post(f"/agreements/{agreement['id']}/supersede", json={"reason": "no way"}, headers=pmh).status_code == 403
    ok = client.post(f"/agreements/{agreement['id']}/execute", headers=h)
    assert ok.status_code == 200
    assert ok.json()["nesta_signed_by_id"] and ok.json()["status"] == "executed"
    # an executed agreement cannot be executed or client-signed again
    assert client.post(f"/agreements/{agreement['id']}/execute", headers=h).status_code == 409
    assert client_sign(client, h, agreement["id"], signatory["id"], attachment["id"]).status_code == 409


# ---------------------------------------------------------------- AC-8 / AC-9: nested parents, removal


def test_ac08_cross_project_ids_are_rejected_by_nested_parent_validation(client, won, director_user):
    h = won["headers"]
    _, other_quotation = _won_quotation(client, h)
    other_project, _ = quotation_project(client, h, other_quotation)
    _, other_member = staff_site_engineer(client, h, other_project)
    other_milestone = client.post(f"/projects/{other_project}/milestones", json={"name": "Elsewhere"}, headers=h).json()

    here = won["project_id"]
    res = client.post(f"/projects/{here}/tasks", json={"title": "x", "assigned_to_id": other_member["id"]}, headers=h)
    assert res.status_code == 422 and "not an active member of this project" in res.json()["detail"]
    res = client.post(f"/projects/{here}/tasks", json={"title": "x", "milestone_id": other_milestone["id"]}, headers=h)
    assert res.status_code == 422 and "does not belong to this project" in res.json()["detail"]
    # a Work Order from another project cannot hang a milestone here
    make_execution_ready(client, h, other_quotation)
    other_wo = client.post(f"/quotations/{other_quotation}/work-order", headers=h).json()
    res = client.post(f"/projects/{here}/milestones", json={"name": "m", "work_order_id": other_wo["id"]}, headers=h)
    assert res.status_code == 422 and "does not belong to this project" in res.json()["detail"]
    # and re-pointing an existing task at another project's member is rejected too
    ok = client.post(f"/projects/{here}/tasks", json={"title": "ok"}, headers=h).json()
    res = client.patch(f"/tasks/{ok['id']}", json={"assigned_to_id": other_member["id"]}, headers=h)
    assert res.status_code == 422


def test_ac09_removal_unassigns_and_flags_open_tasks_without_blocking_and_history_is_kept(client, won, db_session):
    h = won["headers"]
    pid = won["project_id"]
    engineer = make_user(db_session, "site_engineer")
    _, member = staff_site_engineer(client, h, pid, user={"id": str(engineer.id)})
    open_a = client.post(f"/projects/{pid}/tasks", json={"title": "A", "assigned_to_id": member["id"]}, headers=h).json()
    open_b = client.post(f"/projects/{pid}/tasks", json={"title": "B", "assigned_to_id": member["id"]}, headers=h).json()
    done = client.post(f"/projects/{pid}/tasks", json={"title": "Done one", "assigned_to_id": member["id"]}, headers=h).json()
    client.patch(f"/tasks/{done['id']}", json={"status": "in_progress"}, headers=h)
    client.patch(f"/tasks/{done['id']}", json={"status": "done"}, headers=h)

    # the engineer is deactivated first: removing an INACTIVE member must still be permitted
    from app.models.user import User

    db_session.get(User, engineer.id).is_active = False
    db_session.commit()
    res = client.delete(f"/projects/{pid}/team/{member['id']}", headers=h)
    assert res.status_code == 200, res.text
    assert res.json()["removed_at"] is not None

    db_session.expire_all()
    for task_json in (open_a, open_b):
        task = db_session.get(ProjectTask, task_json["id"])
        assert task.assigned_to_id is None and task.needs_reassignment is True
        assert _audit_count(db_session, "project_task", task.id) == 2  # created + the removal's un-assign
    kept = db_session.get(ProjectTask, done["id"])
    assert kept.assigned_to_id is not None and kept.needs_reassignment is False  # finished work keeps its history

    # history: the removed row stays; a user can be re-added as a NEW row
    engineer2 = make_user(db_session, "site_engineer")
    first = client.post(
        f"/projects/{pid}/team", json={"user_id": str(engineer2.id), "project_role": "site_engineer"}, headers=h
    ).json()
    assert client.delete(f"/projects/{pid}/team/{first['id']}", headers=h).status_code == 200
    second = client.post(f"/projects/{pid}/team", json={"user_id": str(engineer2.id), "project_role": "site_engineer"}, headers=h).json()
    assert second["id"] != first["id"]
    everyone = client.get(f"/projects/{pid}/team?include_removed=true", headers=h).json()
    assert len([m for m in everyone if m["user_id"] == str(engineer2.id)]) == 2
    # removing the same membership twice is a clean 409, not a crash
    assert client.delete(f"/projects/{pid}/team/{first['id']}", headers=h).status_code == 409


# ---------------------------------------------------------------- AC-10 / AC-11 / AC-12: replacement, authorization constraint, correction


def test_ac10_replacement_after_voiding_keeps_the_voided_history(client, won, db_session):
    h = won["headers"]
    q = won["quotation_id"]
    info = make_execution_ready(client, h, q)
    old_id = info["agreement"]["id"]
    voided = client.post(f"/agreements/{old_id}/void", json={"reason": "Wrong party named"}, headers=h)
    assert voided.status_code == 200 and voided.json()["status"] == "voided"
    # the authorization bound to it is invalidated in the SAME transaction as the void
    db_session.expire_all()
    auth = db_session.get(ProjectExecutionAuthorization, info["authorization"]["id"])
    assert auth.status == AuthorizationStatus.INVALIDATED and auth.invalidated_reason == "Agreement voided"
    assert _wo(client, won).status_code == 409

    # a brand-new draft is allowed immediately -- the partial index no longer counts the voided row
    fresh = client.post(f"/quotations/{q}/agreement", headers=h)
    assert fresh.status_code == 201, fresh.text
    assert fresh.json()["status"] == "drafted" and fresh.json()["supersedes_id"] == old_id  # lineage only
    # the voided row is untouched
    old = client.get(f"/agreements/{old_id}", headers=h).json()
    assert old["status"] == "voided" and old["void_reason"] == "Wrong party named" and old["voided_at"]
    revisions = client.get(f"/quotations/{q}/agreements", headers=h).json()
    assert [r["status"] for r in revisions] == ["voided", "drafted"]
    # a second concurrent-looking draft is refused while a current one exists
    assert client.post(f"/quotations/{q}/agreement", headers=h).status_code == 409

    # execute the replacement and authorize it: a Work Order is possible again
    att = upload_agreement_document(client, h, fresh.json()["id"], b"second")
    sig = add_signatory(client, h, won["client_id"], name="Second Signer")
    assert client_sign(client, h, fresh.json()["id"], sig["id"], att["id"]).status_code == 200
    assert client.post(f"/agreements/{fresh.json()['id']}/execute", headers=h).status_code == 200
    assert authorize(client, h, q).status_code == 200
    assert _wo(client, won).status_code == 201


def test_ac11_one_current_authorization_per_quotation_at_the_database_and_idempotent_in_the_api(client, won, db_session):
    h = won["headers"]
    info = make_execution_ready(client, h, won["quotation_id"])
    again = authorize(client, h, won["quotation_id"])
    assert again.status_code == 200 and again.json()["id"] == info["authorization"]["id"]  # idempotent: same row back
    rows = client.get(f"/quotations/{won['quotation_id']}/execution-authorizations", headers=h).json()
    assert len(rows) == 1

    # the database itself refuses a second 'authorized' row for the quotation
    db_session.add(
        ProjectExecutionAuthorization(
            quotation_id=won["quotation_id"], agreement_id=info["agreement"]["id"], project_id=won["project_id"],
            authorized_by_id=db_session.get(Agreement, info["agreement"]["id"]).created_by_id,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_ac12_correcting_an_executed_agreement_supersedes_it_and_needs_fresh_authorization(client, won, db_session):
    h = won["headers"]
    q = won["quotation_id"]
    info = make_execution_ready(client, h, q)
    old_id = info["agreement"]["id"]
    res = client.post(f"/agreements/{old_id}/supersede", json={"reason": "Typo in the contract value"}, headers=h)
    assert res.status_code == 201, res.text
    new = res.json()
    assert new["status"] == "drafted" and new["supersedes_id"] == old_id
    old = client.get(f"/agreements/{old_id}", headers=h).json()
    assert old["status"] == "superseded" and old["evidence_locked_at"] is not None  # lock survives
    db_session.expire_all()
    assert db_session.get(ProjectExecutionAuthorization, info["authorization"]["id"]).status == AuthorizationStatus.INVALIDATED
    assert _wo(client, won).status_code == 409
    # a superseded row can neither be superseded nor voided again (linear chain, never a branch)
    assert client.post(f"/agreements/{old_id}/supersede", json={"reason": "again"}, headers=h).status_code == 409
    assert client.post(f"/agreements/{old_id}/void", json={"reason": "again"}, headers=h).status_code == 409
    # a still-drafted agreement is not "correctable": nothing signed yet to protect
    assert client.post(f"/agreements/{new['id']}/supersede", json={"reason": "draft"}, headers=h).status_code == 409
    # finish the replacement; the OLD authorization (bound to the old agreement id) can never be reused
    att = upload_agreement_document(client, h, new["id"], b"corrected")
    sig = add_signatory(client, h, won["client_id"], name="Third Signer")
    assert client_sign(client, h, new["id"], sig["id"], att["id"]).status_code == 200
    assert client.post(f"/agreements/{new['id']}/execute", headers=h).status_code == 200
    assert _wo(client, won).status_code == 409  # still needs a fresh authorization
    fresh = authorize(client, h, q)
    assert fresh.status_code == 200 and fresh.json()["id"] != info["authorization"]["id"]
    assert fresh.json()["agreement_id"] == new["id"]
    assert _wo(client, won).status_code == 201


# ---------------------------------------------------------------- AC-16: evidence lock (sequential half)


def test_ac16_signed_evidence_cannot_be_superseded_through_the_generic_route_even_after_supersede_or_void(client, won):
    h = won["headers"]
    q = won["quotation_id"]
    info = make_execution_ready(client, h, q)
    ev_id = info["agreement"]["signed_document_attachment_id"]

    def generic_supersede(attachment_id):
        return client.post(
            f"/attachments/{attachment_id}/supersede", data={"tag": "signed_document"},
            files={"file": ("tamper.pdf", valid_pdf("tampered"), "application/pdf")}, headers=h,
        )

    res = generic_supersede(ev_id)
    assert res.status_code == 409 and "Signed evidence cannot be superseded" in res.json()["detail"]
    # supersede the Agreement itself: the OLD evidence stays protected, because the guard keys off
    # evidence_locked_at, not off the row's current status
    corrected = client.post(f"/agreements/{info['agreement']['id']}/supersede", json={"reason": "fix"}, headers=h)
    assert corrected.status_code == 201
    assert generic_supersede(ev_id).status_code == 409
    # the same after a void (on a second quotation)
    _, q2 = _won_quotation(client, h)
    info2 = make_execution_ready(client, h, q2)
    assert client.post(f"/agreements/{info2['agreement']['id']}/void", json={"reason": "withdrawn"}, headers=h).status_code == 200
    assert generic_supersede(info2["agreement"]["signed_document_attachment_id"]).status_code == 409
    # evidence integrity still reports intact
    assert client.get(f"/agreements/{info['agreement']['id']}", headers=h).json()["evidence_intact"] is True
    # a still-unsigned draft's file CAN be superseded (nothing is locked yet)
    draft = corrected.json()  # the replacement draft the correction created
    att = upload_agreement_document(client, h, draft["id"], b"first")
    assert generic_supersede(att["id"]).status_code == 201
    # and the signed document is never marketing material
    assert client.post(f"/attachments/{ev_id}/marketing-reuse/approve", headers=h).status_code == 409


# ---------------------------------------------------------------- AC-18 / AC-19 (sequential): account changes


def test_ac18_ac19_deactivating_the_only_engineer_invalidates_authorization_and_reactivation_never_revives_it(
    client, won, db_session
):
    h = won["headers"]
    q = won["quotation_id"]
    engineer = make_user(db_session, "site_engineer")
    execute_agreement(client, h, q, won["client_id"])
    staff_site_engineer(client, h, won["project_id"], user={"id": str(engineer.id)})
    first = authorize(client, h, q).json()

    res = client.patch(f"/users/{engineer.id}", json={"is_active": False}, headers=h)
    assert res.status_code == 200, res.text
    db_session.expire_all()
    row = db_session.get(ProjectExecutionAuthorization, first["id"])
    assert row.status == AuthorizationStatus.INVALIDATED and row.invalidated_reason == "Site Engineer account deactivated"
    assert _wo(client, won).status_code == 409

    res = client.patch(f"/users/{engineer.id}", json={"is_active": True}, headers=h)
    assert res.status_code == 200
    db_session.expire_all()
    assert db_session.get(ProjectExecutionAuthorization, first["id"]).status == AuthorizationStatus.INVALIDATED  # NOT revived
    ready = client.get(f"/quotations/{q}/execution-readiness", headers=h).json()
    assert ready["active_delivery_team"] is True and ready["authorization_valid"] is False
    assert _wo(client, won).status_code == 409  # a fresh decision is still required
    second = authorize(client, h, q)
    assert second.status_code == 200 and second.json()["id"] != first["id"]
    assert _wo(client, won).status_code == 201


def test_a_role_change_away_from_site_engineer_also_invalidates(client, won, db_session):
    h = won["headers"]
    q = won["quotation_id"]
    engineer = make_user(db_session, "site_engineer")
    execute_agreement(client, h, q, won["client_id"])
    staff_site_engineer(client, h, won["project_id"], user={"id": str(engineer.id)})
    auth = authorize(client, h, q).json()
    res = client.patch(f"/users/{engineer.id}", json={"role": "procurement"}, headers=h)
    assert res.status_code == 200, res.text
    db_session.expire_all()
    row = db_session.get(ProjectExecutionAuthorization, auth["id"])
    assert row.status == AuthorizationStatus.INVALIDATED and row.invalidated_reason == "Site Engineer role changed"


def test_a_second_engineer_keeps_the_authorization_valid_when_one_is_deactivated(client, won, db_session):
    h = won["headers"]
    q = won["quotation_id"]
    e1, e2 = make_user(db_session, "site_engineer"), make_user(db_session, "site_engineer")
    execute_agreement(client, h, q, won["client_id"])
    staff_site_engineer(client, h, won["project_id"], user={"id": str(e1.id)})
    staff_site_engineer(client, h, won["project_id"], user={"id": str(e2.id)})
    auth = authorize(client, h, q).json()
    assert client.patch(f"/users/{e1.id}", json={"is_active": False}, headers=h).status_code == 200
    db_session.expire_all()
    assert db_session.get(ProjectExecutionAuthorization, auth["id"]).status == AuthorizationStatus.AUTHORIZED
    assert _wo(client, won).status_code == 201


# ---------------------------------------------------------------- AC-21 / AC-22 / AC-23: eligibility and permissions


def test_ac21_ineligible_staffing_is_rejected_and_never_satisfies_readiness(client, won, db_session):
    h = won["headers"]
    pid = won["project_id"]
    procurement = make_user(db_session, "procurement")
    res = client.post(f"/projects/{pid}/team", json={"user_id": str(procurement.id), "project_role": "site_engineer"}, headers=h)
    assert res.status_code == 422 and "does not match the project role" in res.json()["detail"]
    inactive = make_user(db_session, "site_engineer", active=False)
    res = client.post(f"/projects/{pid}/team", json={"user_id": str(inactive.id), "project_role": "site_engineer"}, headers=h)
    assert res.status_code == 422 and "active user" in res.json()["detail"]
    res = client.post(f"/projects/{pid}/team", json={"user_id": str(procurement.id), "project_role": "sales"}, headers=h)
    assert res.status_code == 422  # sales is not an assignable project role
    # a procurement member on the team does not satisfy the Site Engineer requirement
    assert client.post(f"/projects/{pid}/team", json={"user_id": str(procurement.id), "project_role": "procurement"}, headers=h).status_code == 200
    execute_agreement(client, h, won["quotation_id"], won["client_id"])
    ready = client.get(f"/quotations/{won['quotation_id']}/execution-readiness", headers=h).json()
    assert ready["active_delivery_team"] is False and ready["eligible_site_engineers"] == 0
    # assigning an already-active member is idempotent: same row, no second membership
    again = client.post(f"/projects/{pid}/team", json={"user_id": str(procurement.id), "project_role": "procurement"}, headers=h)
    assert again.status_code == 200
    members = client.get(f"/projects/{pid}/team", headers=h).json()
    assert len([m for m in members if m["user_id"] == str(procurement.id)]) == 1


def test_ac22_task_permissions_follow_the_current_assignment_not_team_membership(client, won, db_session):
    h = won["headers"]
    pid = won["project_id"]
    e1, e2 = make_user(db_session, "site_engineer"), make_user(db_session, "site_engineer")
    _, m1 = staff_site_engineer(client, h, pid, user={"id": str(e1.id)})
    _, m2 = staff_site_engineer(client, h, pid, user={"id": str(e2.id)})
    mine = client.post(f"/projects/{pid}/tasks", json={"title": "Mine", "assigned_to_id": m1["id"]}, headers=h).json()
    theirs = client.post(f"/projects/{pid}/tasks", json={"title": "Theirs", "assigned_to_id": m2["id"]}, headers=h).json()
    unassigned = client.post(f"/projects/{pid}/tasks", json={"title": "Prep"}, headers=h).json()
    h1 = user_headers(client, e1)

    assert client.patch(f"/tasks/{mine['id']}", json={"status": "in_progress"}, headers=h1).status_code == 200
    assert client.patch(f"/tasks/{theirs['id']}", json={"status": "in_progress"}, headers=h1).status_code == 403
    assert client.patch(f"/tasks/{unassigned['id']}", json={"status": "in_progress"}, headers=h1).status_code == 403
    # an assignee changes status only -- not the title, assignee or due date
    assert client.patch(f"/tasks/{mine['id']}", json={"title": "renamed"}, headers=h1).status_code == 403
    assert client.patch(f"/tasks/{mine['id']}", json={"assigned_to_id": m2["id"]}, headers=h1).status_code == 403
    # illegal transition
    assert client.patch(f"/tasks/{mine['id']}", json={"status": "not_started"}, headers=h1).status_code == 409
    # PM/Director may work any task, including the unassigned prep task
    assert client.patch(f"/tasks/{unassigned['id']}", json={"status": "in_progress"}, headers=h).status_code == 200
    # an assignee may reopen their own finished task; a procurement team member may not touch a task assigned to someone else
    assert client.patch(f"/tasks/{mine['id']}", json={"status": "done"}, headers=h1).status_code == 200
    assert client.patch(f"/tasks/{mine['id']}", json={"status": "in_progress"}, headers=h1).status_code == 200
    procurement = make_user(db_session, "procurement")
    assert client.post(f"/projects/{pid}/team", json={"user_id": str(procurement.id), "project_role": "procurement"}, headers=h).status_code == 200
    hp = user_headers(client, procurement)
    assert client.patch(f"/tasks/{mine['id']}", json={"status": "done"}, headers=hp).status_code == 403
    assert len(client.get(f"/projects/{pid}/tasks", headers=hp).json()) == 3  # members see the project's tasks


def test_ac23_a_site_engineer_off_the_team_cannot_reach_p5_resources(client, won, db_session):
    h = won["headers"]
    pid = won["project_id"]
    outsider = make_user(db_session, "site_engineer")
    ho = user_headers(client, outsider)
    assert client.post(f"/projects/{pid}/site-issues", json={"title": "x"}, headers=ho).status_code == 403
    assert client.get(f"/projects/{pid}/site-issues", headers=ho).status_code == 403
    assert client.get(f"/projects/{pid}/tasks", headers=ho).status_code == 403
    assert client.get(f"/projects/{pid}/team", headers=ho).status_code == 403
    assert client.get(f"/projects/{pid}/milestones", headers=ho).status_code == 403
    draft = draft_agreement(client, h, won["quotation_id"])
    assert client.get(f"/agreements/{draft['id']}", headers=ho).status_code == 403
    assert client.get(f"/quotations/{won['quotation_id']}/agreement", headers=ho).status_code == 403
    # once on the team, the same engineer reaches them -- membership is the only difference
    staff_site_engineer(client, h, pid, user={"id": str(outsider.id)})
    assert client.get(f"/projects/{pid}/tasks", headers=ho).status_code == 200
    issue = client.post(f"/projects/{pid}/site-issues", json={"title": "Real issue"}, headers=ho)
    assert issue.status_code == 201
    assert client.get(f"/agreements/{draft['id']}", headers=ho).status_code == 200  # status metadata: yes
    # ...but never the signed document itself
    att = upload_agreement_document(client, h, draft["id"])
    assert client.get(f"/attachments/{att['id']}/download", headers=ho).status_code == 403


def test_roles_with_no_p5_access_are_refused_everywhere(client, won, db_session):
    h = won["headers"]
    pid, q = won["project_id"], won["quotation_id"]
    draft_agreement(client, h, q)
    for role in ("admin", "marketing", "ca_tax"):
        rh = user_headers(client, make_user(db_session, role))
        assert client.get(f"/projects/{pid}/team", headers=rh).status_code == 403, role
        assert client.get(f"/projects/{pid}/tasks", headers=rh).status_code == 403, role
        assert client.get(f"/quotations/{q}/agreement", headers=rh).status_code == 403, role
        assert client.post(f"/quotations/{q}/execution-authorization", headers=rh).status_code == 403, role
        assert client.get(f"/quotations/{q}/execution-readiness", headers=rh).status_code == 403, role
        assert client.post(f"/projects/{pid}/site-issues", json={"title": "x"}, headers=rh).status_code == 403, role
    # Sales is read-only: may read, may not write
    sh = user_headers(client, make_user(db_session, "sales"))
    assert client.get(f"/quotations/{q}/agreement", headers=sh).status_code == 200
    assert client.get(f"/projects/{pid}/tasks", headers=sh).status_code == 200
    assert client.post(f"/quotations/{q}/agreement", headers=sh).status_code == 403
    assert client.post(f"/projects/{pid}/tasks", json={"title": "x"}, headers=sh).status_code == 403
    assert client.post(f"/projects/{pid}/team", json={"user_id": str(make_user(db_session, 'site_engineer').id), "project_role": "site_engineer"}, headers=sh).status_code == 403
    # Sales cannot upload or supersede files on an Agreement either (PM/Director only)
    ag = client.get(f"/quotations/{q}/agreement", headers=h).json()
    up = client.post(
        "/attachments", data={"doc_type": "agreement", "doc_id": ag["id"], "tag": "signed_document"},
        files={"file": ("x.pdf", b"x", "application/pdf")}, headers=sh,
    )
    assert up.status_code == 403


# ---------------------------------------------------------------- AC-24: Amendment 60


def test_ac24_sales_visibility_follows_the_own_records_switch(client, won, db_session, director_user):
    h = won["headers"]
    pid, q = won["project_id"], won["quotation_id"]
    draft = draft_agreement(client, h, q)
    sales_a = make_user(db_session, "sales", name="Sales A")
    sales_b = make_user(db_session, "sales", name="Sales B")
    ha, hb = user_headers(client, sales_a), user_headers(client, sales_b)

    # switch OFF: every Sales user reads exactly what PM/Director reads
    for hh in (ha, hb):
        assert client.get(f"/quotations/{q}/agreement", headers=hh).status_code == 200
        assert client.get(f"/agreements/{draft['id']}", headers=hh).status_code == 200
        assert client.get(f"/projects/{pid}/tasks", headers=hh).status_code == 200
        assert client.get(f"/projects/{pid}/team", headers=hh).status_code == 200

    # switch ON, project owned by A
    assert client.put("/ownership/switch", json={"on": True}, headers=h).status_code == 200
    res = client.patch(f"/ownership/project/{pid}", json={"owner_id": str(sales_a.id), "cascade": True}, headers=h)
    assert res.status_code == 200, res.text
    assert client.get(f"/quotations/{q}/agreement", headers=ha).status_code == 200
    assert client.get(f"/agreements/{draft['id']}", headers=ha).status_code == 200
    assert client.get(f"/projects/{pid}/tasks", headers=ha).status_code == 200
    # B gets the same 404 every other covered path parameter already returns
    assert client.get(f"/quotations/{q}/agreement", headers=hb).status_code == 404
    assert client.get(f"/agreements/{draft['id']}", headers=hb).status_code == 404
    assert client.get(f"/projects/{pid}/tasks", headers=hb).status_code == 404
    assert client.get(f"/projects/{pid}/team", headers=hb).status_code == 404
    # PM/Director are unchanged
    assert client.get(f"/projects/{pid}/tasks", headers=h).status_code == 200


# ---------------------------------------------------------------- AC-30: one-way invalidation


def test_ac30_an_invalidated_authorization_can_never_be_moved_back_to_authorized(client, won, db_session):
    h = won["headers"]
    info = make_execution_ready(client, h, won["quotation_id"])
    assert client.post(f"/agreements/{info['agreement']['id']}/void", json={"reason": "withdrawn"}, headers=h).status_code == 200
    db_session.expire_all()
    row = db_session.get(ProjectExecutionAuthorization, info["authorization"]["id"])
    assert row.status == AuthorizationStatus.INVALIDATED
    row.status = AuthorizationStatus.AUTHORIZED
    with pytest.raises(AuthorizationTransitionError):
        db_session.flush()
    db_session.rollback()
    db_session.expire_all()
    assert db_session.get(ProjectExecutionAuthorization, info["authorization"]["id"]).status == AuthorizationStatus.INVALIDATED
    # the only way to a valid authorization is a NEW row (and only against a new executed agreement)
    assert authorize(client, h, won["quotation_id"]).status_code == 409


# ---------------------------------------------------------------- Project Overview: assignee work shows in the existing workspace


def test_assigned_tasks_appear_in_the_existing_project_overview_pending_list(client, won, db_session):
    h = won["headers"]
    pid = won["project_id"]
    engineer = make_user(db_session, "site_engineer")
    _, member = staff_site_engineer(client, h, pid, user={"id": str(engineer.id)})
    task = client.post(
        f"/projects/{pid}/tasks", json={"title": "Pour the base slab", "assigned_to_id": member["id"]}, headers=h
    ).json()
    eh = user_headers(client, engineer)
    overview = client.get(f"/projects/{pid}/overview", headers=eh).json()
    items = [i for i in overview["pending_items"] if i["source"] == "task"]
    assert [i["label"] for i in items] == ["Pour the base slab"] and items[0]["document_id"] == task["id"]
    assert items[0]["screen"] == "execution"
    # the Director does not see someone else's task as their own pending work...
    assert [i for i in client.get(f"/projects/{pid}/overview", headers=h).json()["pending_items"] if i["source"] == "task"] == []
    # ...until a removal leaves it un-assigned, when it needs a PM/Director's attention
    client.delete(f"/projects/{pid}/team/{member['id']}", headers=h)
    items = [i for i in client.get(f"/projects/{pid}/overview", headers=h).json()["pending_items"] if i["source"] == "task"]
    assert [i["label"] for i in items] == ["Needs reassignment: Pour the base slab"]


def test_execution_context_lets_team_members_find_the_won_quotation_without_seeing_quotations(client, won, db_session):
    """The Execution screen needs the Won quotation, but Site Engineers cannot list a project's quotations."""
    h = won["headers"]
    pid = won["project_id"]
    engineer = make_user(db_session, "site_engineer")
    eh = user_headers(client, engineer)
    assert client.get(f"/projects/{pid}/quotations", headers=eh).status_code == 403  # the gap this endpoint closes
    assert client.get(f"/projects/{pid}/execution-context", headers=eh).status_code == 403  # off the team: refused
    staff_site_engineer(client, h, pid, user={"id": str(engineer.id)})
    ctx = client.get(f"/projects/{pid}/execution-context", headers=eh)
    assert ctx.status_code == 200, ctx.text
    body = ctx.json()
    assert body["quotation_id"] == won["quotation_id"] and body["quotation_no"].startswith("NPQ-")
    assert body["work_order_exists"] is False and body["work_order_id"] is None
    assert "total" not in str(body).lower()  # no commercial figures
    execute_agreement(client, h, won["quotation_id"], won["client_id"])
    assert authorize(client, h, won["quotation_id"]).status_code == 200
    assert _wo(client, won).status_code == 201
    member_view = client.get(f"/projects/{pid}/execution-context", headers=eh).json()
    assert member_view["work_order_exists"] is True and member_view["work_order_id"] is None  # id/status: managers only
    manager_view = client.get(f"/projects/{pid}/execution-context", headers=h).json()
    assert manager_view["work_order_id"] and manager_view["work_order_status"] == "awarded"
    for role in ("admin", "marketing", "ca_tax"):
        assert client.get(f"/projects/{pid}/execution-context", headers=user_headers(client, make_user(db_session, role))).status_code == 403


# ---------------------------------------------------------------- AC-27 (part): role-permissions lists every P5 route with no manual registration


def test_role_permissions_lists_every_p5_route_under_its_real_gate_with_no_registration(client, director_user):
    from tests.test_role_permissions import _fetch, _gated_lookup

    lookup = _gated_lookup(_fetch(client, director_user))
    view = ["sales", "pm", "director", "procurement", "site_engineer"]
    manage = ["pm", "director"]
    expected = {
        ("POST", "/quotations/{quotation_id}/agreement"): manage,
        ("GET", "/quotations/{quotation_id}/agreement"): view,
        ("GET", "/quotations/{quotation_id}/agreements"): view,
        ("GET", "/agreements/{agreement_id}"): view,
        ("POST", "/agreements/{agreement_id}/client-sign"): manage,
        ("POST", "/agreements/{agreement_id}/execute"): ["director"],
        ("POST", "/agreements/{agreement_id}/void"): ["director"],
        ("POST", "/agreements/{agreement_id}/supersede"): ["director"],
        ("GET", "/quotations/{quotation_id}/execution-readiness"): manage,
        ("POST", "/quotations/{quotation_id}/execution-authorization"): manage,
        ("GET", "/quotations/{quotation_id}/execution-authorizations"): manage,
        ("GET", "/projects/{project_id}/execution-context"): view,
        ("GET", "/projects/{project_id}/team"): view,
        ("POST", "/projects/{project_id}/team"): manage,
        ("DELETE", "/projects/{project_id}/team/{team_member_id}"): manage,
        ("GET", "/projects/{project_id}/milestones"): view,
        ("POST", "/projects/{project_id}/milestones"): manage,
        ("PATCH", "/milestones/{milestone_id}"): manage,
        ("GET", "/projects/{project_id}/tasks"): view,
        ("POST", "/projects/{project_id}/tasks"): manage,
        ("PATCH", "/tasks/{task_id}"): ["pm", "director", "procurement", "site_engineer"],
        ("GET", "/projects/{project_id}/site-issues"): view,
        ("POST", "/projects/{project_id}/site-issues"): ["pm", "director", "site_engineer"],
        ("PATCH", "/site-issues/{site_issue_id}"): manage,
    }
    for key, roles in expected.items():
        assert key in lookup, f"{key} is not listed"
        assert lookup[key][0] == roles, f"{key}: {lookup[key][0]} != {roles}"
        assert not {"admin", "marketing", "ca_tax"} & set(lookup[key][0]), key  # none of these roles reach P5
