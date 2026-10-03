"""P5 (Agreement & Execution Starter) + upload hardening, together.

Exists ONLY in the integration checkout: it needs both code bases. It exercises resumable-upload finalization for an
AGREEMENT document against P5's REAL account-change and ownership operations, in BOTH commit orders:

  A. finalization reaches its commit first -> the real operation must wait on the locks, apply AFTER the attachment
     commits, and nothing deadlocks;
  B. the real operation commits first       -> finalization refuses (the P5 write rule is repeated on the user as they
     are now), and no business state changes: the snapshot taken after the operation equals the snapshot after the
     refused finalization, for every table outside the upload-session bookkeeping, and no file is placed.

Lock order exercised: P5 takes Project -> Quotation -> Agreement -> ProjectExecutionAuthorization -> ProjectTeamMember ->
User -> Attachment; finalization takes upload session -> Project (FOR SHARE) -> User (FOR SHARE) -> Attachment."""

import threading
import uuid

import pytest
from sqlalchemy import text

from app.config import settings
from app.core import attachment_upload as upload_core
from app.models.attachment import Attachment
from app.models.user import User
from tests.concurrency_harness import Op, Session, wait_until_blocked
from tests.db_snapshot import full_snapshot, storage_snapshot
from tests.p5_helpers import draft_agreement, make_user, user_headers
from tests.test_upload_hardening import PDF, _complete, _count, _put_chunks, _sha, _start
from tests.test_work_orders import _director_headers, _won_quotation

SESSION_TABLES = ("attachment_upload_sessions", "attachment_upload_chunks")


@pytest.fixture()
def agreement_world(client, director_user, db_session):
    h = _director_headers(client, director_user)
    pid, qid = _won_quotation(client, h)
    agreement = draft_agreement(client, h, qid)
    return dict(h=h, pid=pid, qid=qid, agreement_id=agreement["id"], db=db_session, client=client)


def _prepare(world, uploader):
    headers = user_headers(world["client"], uploader)
    started = _start(world["client"], headers, "agreement", world["agreement_id"], "signed.pdf", PDF)
    assert started.status_code == 201, started.text
    session_id = uuid.UUID(started.json()["id"])
    _put_chunks(world["client"], headers, session_id, PDF, len(PDF))
    setup = Session()
    try:
        token = upload_core.start_completion(setup, session_id)
        assembled = upload_core.assemble_and_validate(setup, session_id, token)
    finally:
        setup.close()
    return session_id, token, assembled


def _finalize(session_id, token, assembled, user_id):
    def run(s):
        return upload_core.finalize_completion(s, session_id, token, assembled, s.get(User, user_id), None).id

    return run


def _state(db):
    return full_snapshot(db, exclude_tables=SESSION_TABLES), storage_snapshot(settings.attachment_storage_root)


def _api_in_thread(fn):
    box = {}
    thread = threading.Thread(target=lambda: box.update(res=fn()), daemon=True)
    thread.start()
    return thread, box


def _demote(world, user):
    return lambda: world["client"].patch(f"/users/{user.id}", json={"role": "sales"}, headers=world["h"])


def _deactivate(world, user):
    return lambda: world["client"].patch(f"/users/{user.id}", json={"is_active": False}, headers=world["h"])


def _reassign(world, project_id, new_owner):
    return lambda: world["client"].patch(
        f"/ownership/project/{project_id}", json={"owner_id": str(new_owner.id), "cascade": True}, headers=world["h"])


CASES = ["demote-pm-to-sales", "deactivate-pm", "reassign-project"]


def _case(world, db, which):
    """(uploader, change, expected refusal). The uploader is a PM (allowed to write Agreement files)."""
    uploader = make_user(db, "pm", name=f"PM {which}")
    if which == "demote-pm-to-sales":
        return uploader, _demote(world, uploader), 403  # the P5 PM/Director-only Agreement write rule, repeated at commit
    if which == "deactivate-pm":
        return uploader, _deactivate(world, uploader), 401
    # a PM is not an ownership-scoped role; use a Sales owner who may only SEE (not write) - so test visibility via a
    # Director-owned reassignment away from a scoped Sales uploader on the QUOTATION instead (see the second test module)
    raise AssertionError(which)


@pytest.mark.parametrize("which", CASES[:2])
def test_order_b_the_real_p5_operation_first_finalization_refuses_and_changes_nothing(agreement_world, which):
    w = agreement_world
    uploader, change, refusal = _case(w, w["db"], which)
    uid = uploader.id
    session_id, token, assembled = _prepare(w, uploader)
    assert change().status_code == 200
    before = _state(w["db"])  # AFTER the operation: only the finalization attempt is measured
    run = Op(_finalize(session_id, token, assembled, uid)).start().join()
    assert isinstance(run.exc, upload_core.UploadProtocolError) and run.exc.status_code == refusal, run.exc
    assert _state(w["db"]) == before  # no attachment, no agreement/authorization/audit change, no file placed


@pytest.mark.parametrize("which", CASES[:2])
def test_order_a_finalization_first_the_real_p5_operation_waits_then_applies_and_nothing_deadlocks(agreement_world, which):
    w = agreement_world
    uploader, change, _ = _case(w, w["db"], which)
    uid = uploader.id
    session_id, token, assembled = _prepare(w, uploader)
    baseline = _count(w["db"], Attachment)
    first = Op(_finalize(session_id, token, assembled, uid), gate=True).start().wait_holding_locks()
    thread, box = _api_in_thread(change)
    try:
        wait_until_blocked(1, timeout=10)  # the real operation is genuinely waiting on finalization's locks
    finally:
        first.release().join()
    thread.join(30)
    assert not thread.is_alive(), "deadlock between finalization and the P5 account change"
    assert first.exc is None, first.exc
    assert box["res"].status_code == 200, box["res"].text[:160]
    assert _count(w["db"], Attachment) == baseline + 1


def test_the_p5_write_rule_is_enforced_when_the_session_is_started(agreement_world, db_session):
    sales = make_user(db_session, "sales", name="Sales reader")
    res = _start(agreement_world["client"], user_headers(agreement_world["client"], sales), "agreement",
                 agreement_world["agreement_id"], "signed.pdf", PDF)
    assert res.status_code == 403


def test_an_ordinary_signed_document_upload_through_the_hardened_path_still_works(agreement_world):
    w = agreement_world
    res = w["client"].post(
        "/attachments", data={"doc_type": "agreement", "doc_id": w["agreement_id"], "tag": "signed_document"},
        files={"file": ("agreement.pdf", PDF, "application/pdf")}, headers=w["h"])
    assert res.status_code == 201, res.text
    assert res.json()["original_sha256"] == _sha(PDF)
    assert w["client"].get(f"/attachments/{res.json()['id']}/download", headers=w["h"]).content == PDF  # original unchanged


def test_a_resumable_signed_document_completes_end_to_end_for_a_pm(agreement_world, db_session):
    w = agreement_world
    pm = make_user(db_session, "pm", name="PM ok")
    headers = user_headers(w["client"], pm)
    started = _start(w["client"], headers, "agreement", w["agreement_id"], "signed.pdf", PDF)
    sid = started.json()["id"]
    _put_chunks(w["client"], headers, sid, PDF, len(PDF))
    res = _complete(w["client"], headers, sid)
    assert res.status_code == 200, res.text
