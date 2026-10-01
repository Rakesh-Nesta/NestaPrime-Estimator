"""P5 contract revision 7 -- the concurrency acceptance cases (AC-13..15, 17..20, 28, 29, retry limit).

Every race is run against the contract's single total lock order using the deterministic harness in
p5_concurrency.py (gated commits + observed lock waits, no sleeps-and-hope). Assertions are on the
RESULTING STATE and on serialization -- never on a required 'loser' where both requests may legitimately
succeed (contract AC-14/15)."""

import asyncio
import io
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select

from app.api import attachments as attachments_api
from app.api import users as users_api
from app.api import work_orders as work_orders_api
from app.core import p5
from app.core import p5_agreements
from app.models.attachment import Attachment
from app.models.audit_log import AuditLogEntry
from app.models.p5 import (
    Agreement,
    AgreementStatus,
    AuthorizationStatus,
    ProjectExecutionAuthorization,
    ProjectTeamMember,
)
from app.models.user import User
from app.models.work_order import WorkOrder, WorkOrderStatus
from tests.p5_concurrency import Session, blocked_pair, run_to_completion
from tests.p5_helpers import (
    add_signatory,
    authorize,
    client_sign,
    draft_agreement,
    execute_agreement,
    make_execution_ready,
    make_user,
    quotation_project,
    staff_site_engineer,
    upload_agreement_document,
)
from tests.test_work_orders import _create_client_record, _create_project, _director_headers, _won_quotation


# ------------------------------------------------------------------ fixtures / builders


@pytest.fixture()
def world(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    project_id, quotation_id = _won_quotation(client, headers)
    _, client_id = quotation_project(client, headers, quotation_id)
    return SimpleNamespace(
        client=client, headers=headers, db=db_session, director_id=director_user.id,
        project_id=project_id, quotation_id=quotation_id, client_id=client_id,
    )


def _ready(w, *, engineers=1, authorized=True):
    """Executed Agreement + `engineers` real, active Site Engineers (+ an authorization)."""
    agreement = execute_agreement(w.client, w.headers, w.quotation_id, w.client_id)
    users, members = [], []
    for _ in range(engineers):
        user = make_user(w.db, "site_engineer")
        _, member = staff_site_engineer(w.client, w.headers, w.project_id, user={"id": str(user.id)})
        users.append(user)
        members.append(member)
    auth = authorize(w.client, w.headers, w.quotation_id).json() if authorized else None
    return SimpleNamespace(agreement=agreement, users=users, members=members, auth=auth)


def _fresh_state(quotation_id):
    s = Session()
    try:
        agreements = s.execute(select(Agreement).where(Agreement.quotation_id == quotation_id).order_by(Agreement.created_at)).scalars().all()
        auths = s.execute(select(ProjectExecutionAuthorization).where(ProjectExecutionAuthorization.quotation_id == quotation_id)).scalars().all()
        return SimpleNamespace(
            agreements=[(a.id, a.status) for a in agreements],
            auths=[(a.id, a.status, a.invalidated_reason) for a in auths],
        )
    finally:
        s.close()


def _assert_consistent(quotation_id, project_id):
    """The one invariant every race must preserve: a VALID authorization always points at the quotation's
    current executed Agreement and the project always still has an eligible Site Engineer."""
    s = Session()
    try:
        valid = p5.valid_authorization(s, quotation_id)
        if valid is not None:
            current = p5.current_agreement(s, quotation_id)
            assert current is not None and current.id == valid.agreement_id and current.status == AgreementStatus.EXECUTED
            assert len(p5.eligible_site_engineers(s, project_id)) >= 1
    finally:
        s.close()


def _work_orders(quotation_id):
    s = Session()
    try:
        return s.execute(select(WorkOrder).where(WorkOrder.quotation_id == quotation_id)).scalars().all()
    finally:
        s.close()


# --- operation builders (each returns fn(session)); every fn commits through session.commit ----------


def authorize_op(qid, actor_id):
    def fn(s):
        row, _ = p5.authorize_execution(s, qid, s.get(User, actor_id), None)
        s.commit()
        return row.id
    return fn


def void_op(agreement_id, actor_id):
    def fn(s):
        p5_agreements.void(s, agreement_id, "withdrawn", s.get(User, actor_id), None)
        s.commit()
    return fn


def supersede_op(agreement_id, actor_id):
    def fn(s):
        replacement = p5_agreements.supersede(s, agreement_id, "correction", s.get(User, actor_id), None)
        s.commit()
        return replacement.id
    return fn


def remove_op(project_id, member_id, actor_id):
    def fn(s):
        p5.remove_member(s, project_id, member_id, s.get(User, actor_id), None)
        s.commit()
    return fn


def assign_op(project_id, user_id, role, actor_id):
    def fn(s):
        member, created = p5.assign_member(s, project_id, user_id, role, s.get(User, actor_id), None)
        s.commit()
        return member.id, created
    return fn


def work_order_op(qid, actor_id):
    def fn(s):
        return work_orders_api.create_work_order(quotation_id=qid, db=s, current_user=s.get(User, actor_id)).id
    return fn


def user_update_op(user_id, actor_id, **fields):
    def fn(s):
        return users_api.update_user(
            user_id=user_id, payload=users_api.UserUpdate(**fields), request=None, db=s, current_user=s.get(User, actor_id)
        ).id
    return fn


def sign_op(agreement_id, signatory_id, attachment_id, actor_id):
    def fn(s):
        from datetime import date

        p5_agreements.record_client_signature(
            s, agreement_id, signatory_id, date.today(), attachment_id, s.get(User, actor_id), None
        )
        s.commit()
    return fn


def attachment_supersede_op(attachment_id, actor_id):
    def fn(s):
        file = UploadFile(file=io.BytesIO(b"a second version"), filename="v2.pdf")
        return asyncio.run(
            attachments_api.supersede_attachment(
                attachment_id=attachment_id, request=SimpleNamespace(client=None), tag=None, approval_strength=None,
                signatory_name=None, signatory_designation=None, captured_at=None, captured_at_source=None,
                file=file, db=s, current_user=s.get(User, actor_id),
            )
        ).id
    return fn


def _status_code(exc):
    assert isinstance(exc, HTTPException), repr(exc)
    return exc.status_code


# ------------------------------------------------------------------ AC-13: branched correction


def test_ac13_two_concurrent_corrections_of_one_agreement_make_a_chain_never_a_branch(world):
    ready = _ready(world, authorized=False)
    aid = ready.agreement["id"]
    first, second = blocked_pair(supersede_op(aid, world.director_id), supersede_op(aid, world.director_id))
    assert first.exc is None
    assert _status_code(second.exc) == 409  # the loser found the row already superseded
    s = Session()
    try:
        rows = s.execute(select(Agreement).where(Agreement.quotation_id == world.quotation_id)).scalars().all()
        assert sorted(r.status for r in rows) == [AgreementStatus.DRAFTED, AgreementStatus.SUPERSEDED]
        children = [r for r in rows if str(r.supersedes_id) == aid]
        assert len(children) == 1  # exactly one child of the corrected parent
    finally:
        s.close()


# ------------------------------------------------------------------ AC-14: authorize vs void, both orders


def test_ac14_void_commits_first_then_the_concurrent_authorize_is_refused(world):
    ready = _ready(world, authorized=False)
    first, second = blocked_pair(
        void_op(ready.agreement["id"], world.director_id), authorize_op(world.quotation_id, world.director_id)
    )
    assert first.exc is None
    assert _status_code(second.exc) == 409  # its own live recheck, under the Agreement lock, saw a voided Agreement
    state = _fresh_state(world.quotation_id)
    assert [st for _, st in state.agreements] == [AgreementStatus.VOIDED] and state.auths == []
    _assert_consistent(world.quotation_id, world.project_id)


def test_ac14_authorize_commits_first_then_void_still_succeeds_and_invalidates_it(world):
    ready = _ready(world, authorized=False)
    first, second = blocked_pair(
        authorize_op(world.quotation_id, world.director_id), void_op(ready.agreement["id"], world.director_id)
    )
    assert first.exc is None and second.exc is None  # BOTH legitimately succeed
    state = _fresh_state(world.quotation_id)
    assert [st for _, st in state.agreements] == [AgreementStatus.VOIDED]
    assert len(state.auths) == 1 and state.auths[0][1] == AuthorizationStatus.INVALIDATED
    assert state.auths[0][2] == "Agreement voided"
    _assert_consistent(world.quotation_id, world.project_id)


# ------------------------------------------------------------------ AC-15: authorize vs last-engineer removal


def test_ac15_removal_commits_first_then_the_concurrent_authorize_is_refused(world):
    ready = _ready(world, authorized=False)
    first, second = blocked_pair(
        remove_op(world.project_id, ready.members[0]["id"], world.director_id),
        authorize_op(world.quotation_id, world.director_id),
    )
    assert first.exc is None
    assert _status_code(second.exc) == 409
    assert _fresh_state(world.quotation_id).auths == []
    _assert_consistent(world.quotation_id, world.project_id)


def test_ac15_authorize_commits_first_then_removal_succeeds_and_invalidates_it(world):
    ready = _ready(world, authorized=False)
    first, second = blocked_pair(
        authorize_op(world.quotation_id, world.director_id),
        remove_op(world.project_id, ready.members[0]["id"], world.director_id),
    )
    assert first.exc is None and second.exc is None  # both succeed
    state = _fresh_state(world.quotation_id)
    assert len(state.auths) == 1 and state.auths[0][1] == AuthorizationStatus.INVALIDATED
    assert state.auths[0][2] == "Last eligible Site Engineer removed from the team"
    _assert_consistent(world.quotation_id, world.project_id)


# ------------------------------------------------------------------ AC-17: signature recording vs generic attachment supersede


def _drafted_with_attachment(w):
    draft = draft_agreement(w.client, w.headers, w.quotation_id)
    attachment = upload_agreement_document(w.client, w.headers, draft["id"], b"contract v1")
    signatory = add_signatory(w.client, w.headers, w.client_id)
    return draft, attachment, signatory


def test_ac17_signing_first_then_the_direct_supersede_is_refused_by_the_evidence_lock(world):
    draft, attachment, signatory = _drafted_with_attachment(world)
    first, second = blocked_pair(
        sign_op(draft["id"], signatory["id"], attachment["id"], world.director_id),
        attachment_supersede_op(attachment["id"], world.director_id),
    )
    assert first.exc is None
    assert _status_code(second.exc) == 409 and "Signed evidence" in second.exc.detail
    s = Session()
    try:
        agreement = s.get(Agreement, draft["id"])
        assert agreement.status == AgreementStatus.CLIENT_SIGNED and agreement.evidence_locked_at is not None
        assert s.get(Attachment, attachment["id"]).superseded_by_id is None  # the evidence was never replaced
    finally:
        s.close()


def test_ac17_supersede_first_then_signing_refuses_the_now_stale_attachment(world):
    draft, attachment, signatory = _drafted_with_attachment(world)
    first, second = blocked_pair(
        attachment_supersede_op(attachment["id"], world.director_id),
        sign_op(draft["id"], signatory["id"], attachment["id"], world.director_id),
    )
    assert first.exc is None, first.exc
    assert _status_code(second.exc) == 409 and "superseded" in second.exc.detail
    s = Session()
    try:
        agreement = s.get(Agreement, draft["id"])
        assert agreement.status == AgreementStatus.DRAFTED and agreement.evidence_locked_at is None
        assert s.get(Attachment, attachment["id"]).superseded_by_id is not None
    finally:
        s.close()


# ------------------------------------------------------------------ AC-18 / AC-20: Work Order creation vs each invalidating mutation, both orders


def _mutation(name, w, ready):
    if name == "void":
        return void_op(ready.agreement["id"], w.director_id)
    if name == "supersede":
        return supersede_op(ready.agreement["id"], w.director_id)
    if name == "remove_last_engineer":
        return remove_op(w.project_id, ready.members[0]["id"], w.director_id)
    if name == "deactivate_last_engineer":
        return user_update_op(ready.users[0].id, w.director_id, is_active=False)
    raise AssertionError(name)


MUTATIONS = ["void", "supersede", "remove_last_engineer", "deactivate_last_engineer"]


@pytest.mark.parametrize("mutation", MUTATIONS)
def test_ac20_invalidating_mutation_commits_first_then_work_order_creation_refuses(world, mutation):
    ready = _ready(world)
    first, second = blocked_pair(_mutation(mutation, world, ready), work_order_op(world.quotation_id, world.director_id))
    assert first.exc is None, first.exc
    assert _status_code(second.exc) == 409  # its live recheck under the shared locks saw the invalidation
    assert _work_orders(world.quotation_id) == []
    state = _fresh_state(world.quotation_id)
    assert state.auths and state.auths[0][1] == AuthorizationStatus.INVALIDATED
    _assert_consistent(world.quotation_id, world.project_id)


@pytest.mark.parametrize("mutation", MUTATIONS)
def test_ac20_work_order_commits_first_then_it_is_preserved_untouched(world, mutation):
    ready = _ready(world)
    first, second = blocked_pair(work_order_op(world.quotation_id, world.director_id), _mutation(mutation, world, ready))
    assert first.exc is None and second.exc is None, (first.exc, second.exc)  # the mutation still succeeds on its own
    orders = _work_orders(world.quotation_id)
    assert len(orders) == 1 and orders[0].status == WorkOrderStatus.AWARDED  # preserved, not retroactively undone
    # ...and its own lifecycle continues exactly as before P5
    for status in ("in_progress", "completed"):
        res = world.client.patch(f"/work-orders/{orders[0].id}", json={"status": status}, headers=world.headers)
        assert res.status_code == 200, res.text
    # the mutation's invalidation applied to the (now moot) authorization, consistently
    state = _fresh_state(world.quotation_id)
    assert state.auths and state.auths[0][1] == AuthorizationStatus.INVALIDATED
    _assert_consistent(world.quotation_id, world.project_id)


# ------------------------------------------------------------------ AC-28: concurrent deactivations of two eligible engineers


@pytest.mark.parametrize("deactivate_first", [0, 1])
def test_ac28_two_eligible_engineers_deactivated_concurrently_still_invalidate(world, deactivate_first):
    ready = _ready(world, engineers=2)
    a, b = ready.users[deactivate_first], ready.users[1 - deactivate_first]
    first, second = blocked_pair(
        user_update_op(a.id, world.director_id, is_active=False),
        user_update_op(b.id, world.director_id, is_active=False),
    )
    assert first.exc is None and second.exc is None
    s = Session()
    try:
        assert p5.eligible_site_engineers(s, world.project_id) == []
    finally:
        s.close()
    state = _fresh_state(world.quotation_id)
    assert state.auths[0][1] == AuthorizationStatus.INVALIDATED  # no valid authorization left with zero engineers
    _assert_consistent(world.quotation_id, world.project_id)


# ------------------------------------------------------------------ AC-29: deactivation vs team assignment


def test_ac29a_assignment_first_keeps_the_existing_authorization_valid(world):
    ready = _ready(world)
    replacement = make_user(world.db, "site_engineer")
    first, second = blocked_pair(
        assign_op(world.project_id, replacement.id, "site_engineer", world.director_id),
        user_update_op(ready.users[0].id, world.director_id, is_active=False),
    )
    assert first.exc is None and second.exc is None
    state = _fresh_state(world.quotation_id)
    assert state.auths[0][1] == AuthorizationStatus.AUTHORIZED  # an eligible replacement remained
    _assert_consistent(world.quotation_id, world.project_id)
    world.db.expire_all()
    assert world.client.post(f"/quotations/{world.quotation_id}/work-order", headers=world.headers).status_code == 201


def test_ac29a_deactivation_first_invalidates_and_later_assignment_or_reactivation_needs_a_fresh_authorization(world):
    ready = _ready(world)
    replacement = make_user(world.db, "site_engineer")
    first, second = blocked_pair(
        user_update_op(ready.users[0].id, world.director_id, is_active=False),
        assign_op(world.project_id, replacement.id, "site_engineer", world.director_id),
    )
    assert first.exc is None and second.exc is None
    old_auth_id = ready.auth["id"]
    state = _fresh_state(world.quotation_id)
    assert state.auths[0][1] == AuthorizationStatus.INVALIDATED  # NOT revived by the later assignment
    # reactivating the original engineer also revives nothing
    assert run_to_completion(user_update_op(ready.users[0].id, world.director_id, is_active=True)).exc is None
    assert _fresh_state(world.quotation_id).auths[0][1] == AuthorizationStatus.INVALIDATED
    world.db.expire_all()
    assert world.client.post(f"/quotations/{world.quotation_id}/work-order", headers=world.headers).status_code == 409
    fresh = authorize(world.client, world.headers, world.quotation_id)
    assert fresh.status_code == 200 and fresh.json()["id"] != old_auth_id  # a NEW row
    assert world.client.post(f"/quotations/{world.quotation_id}/work-order", headers=world.headers).status_code == 201


def _member_count(project_id, user_id):
    s = Session()
    try:
        return s.execute(
            select(func.count()).select_from(ProjectTeamMember).where(
                ProjectTeamMember.project_id == project_id, ProjectTeamMember.user_id == user_id,
                ProjectTeamMember.removed_at.is_(None),
            )
        ).scalar()
    finally:
        s.close()


def test_ac29b_reassigning_the_user_being_deactivated_assignment_first_is_idempotent(world):
    ready = _ready(world)
    engineer = ready.users[0]
    first, second = blocked_pair(
        assign_op(world.project_id, engineer.id, "site_engineer", world.director_id),
        user_update_op(engineer.id, world.director_id, is_active=False),
    )
    assert first.exc is None and second.exc is None
    member_id, created = first.result
    assert created is False and str(member_id) == ready.members[0]["id"]  # existing membership returned
    assert _member_count(world.project_id, engineer.id) == 1  # no additional membership row
    assert _fresh_state(world.quotation_id).auths[0][1] == AuthorizationStatus.INVALIDATED
    _assert_consistent(world.quotation_id, world.project_id)


def test_ac29b_reassigning_the_user_being_deactivated_deactivation_first_refuses_the_assignment(world):
    ready = _ready(world)
    engineer = ready.users[0]
    first, second = blocked_pair(
        user_update_op(engineer.id, world.director_id, is_active=False),
        assign_op(world.project_id, engineer.id, "site_engineer", world.director_id),
    )
    assert first.exc is None
    assert _status_code(second.exc) == 422  # recheck under the User lock found the user inactive
    assert _member_count(world.project_id, engineer.id) == 1  # still exactly the pre-existing row
    assert _fresh_state(world.quotation_id).auths[0][1] == AuthorizationStatus.INVALIDATED


def _second_won_project(w):
    """Another Won project with its own authorized quotation and engineer -- the 'previously undiscovered project'."""
    project_id, quotation_id = _won_quotation(w.client, w.headers)
    _, client_id = quotation_project(w.client, w.headers, quotation_id)
    execute_agreement(w.client, w.headers, quotation_id, client_id)
    other_engineer = make_user(w.db, "site_engineer")
    staff_site_engineer(w.client, w.headers, project_id, user={"id": str(other_engineer.id)})
    assert authorize(w.client, w.headers, quotation_id).status_code == 200
    return project_id, quotation_id


def test_ac29c_assignment_to_an_undiscovered_project_commits_first_forces_a_rediscovery(world, monkeypatch):
    ready = _ready(world)
    engineer = ready.users[0]
    p2, q2 = _second_won_project(world)
    attempts = []

    def hook():
        attempts.append(1)
        if len(attempts) == 1:  # a concurrent assignment commits between discovery and locking
            assert run_to_completion(assign_op(p2, engineer.id, "site_engineer", world.director_id)).exc is None

    monkeypatch.setattr(p5, "_after_discovery_hook", hook)
    op = run_to_completion(user_update_op(engineer.id, world.director_id, is_active=False))
    assert op.exc is None, op.exc
    assert len(attempts) == 2  # attempt 1 revalidated, saw the extra project, rolled back, retried
    assert _member_count(p2, engineer.id) == 1
    s = Session()
    try:
        assert s.get(User, engineer.id).is_active is False
    finally:
        s.close()
    # project 1 lost its only engineer; project 2 still has its own, so its authorization stays valid
    assert _fresh_state(world.quotation_id).auths[0][1] == AuthorizationStatus.INVALIDATED
    assert _fresh_state(q2).auths[0][1] == AuthorizationStatus.AUTHORIZED
    _assert_consistent(world.quotation_id, world.project_id)
    _assert_consistent(q2, p2)


def test_ac29c_deactivation_first_then_assignment_to_the_other_project_is_refused(world):
    ready = _ready(world)
    engineer = ready.users[0]
    p2, _q2 = _second_won_project(world)
    first, second = blocked_pair(
        user_update_op(engineer.id, world.director_id, is_active=False),
        assign_op(p2, engineer.id, "site_engineer", world.director_id),
    )
    assert first.exc is None
    assert _status_code(second.exc) == 422
    assert _member_count(p2, engineer.id) == 0  # no membership is created for an inactive user


def test_retry_limit_exhaustion_leaves_the_account_change_and_all_related_records_uncommitted(world, client, monkeypatch):
    ready = _ready(world)
    engineer = ready.users[0]
    extra_projects = [_create_project(client, world.headers, _create_client_record(client, world.headers, name=f"Drift {i}")) for i in range(4)]
    attempts = []

    def hook():
        index = len(attempts)
        attempts.append(1)
        # drift on EVERY attempt: a fresh qualifying membership commits before the revalidation
        assert run_to_completion(assign_op(extra_projects[index], engineer.id, "site_engineer", world.director_id)).exc is None

    monkeypatch.setattr(p5, "_after_discovery_hook", hook)
    s = Session()
    try:
        before_audit = s.execute(select(func.count()).select_from(AuditLogEntry).where(AuditLogEntry.document_type == "user")).scalar()
    finally:
        s.close()

    op = run_to_completion(user_update_op(engineer.id, world.director_id, is_active=False, ))
    assert _status_code(op.exc) == 503 and op.exc.headers.get("Retry-After") == "1"
    assert len(attempts) == p5.RETRY_LIMIT == 3

    s = Session()
    try:
        user = s.get(User, engineer.id)
        assert user.is_active is True and user.role.value == "site_engineer"  # the account change was NOT committed
        after_audit = s.execute(select(func.count()).select_from(AuditLogEntry).where(AuditLogEntry.document_type == "user")).scalar()
        assert after_audit == before_audit  # no audit entry from the aborted attempts
        valid = p5.valid_authorization(s, world.quotation_id)
        assert valid is not None  # no authorization was invalidated
    finally:
        s.close()
    assert _fresh_state(world.quotation_id).auths[0][1] == AuthorizationStatus.AUTHORIZED
    _assert_consistent(world.quotation_id, world.project_id)
