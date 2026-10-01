"""P4 contract v7, Section 4: reliable mobile uploads -- concurrency and crash-recovery tests.

These are the acceptance cases that matter most: the ones proving the fencing token, the
session-then-chunk lock order, and the deterministic final-path reconciliation actually hold
under contention and under a simulated crash, not just in the documented happy path. Where a
real process crash can't be literally reproduced in-process, the test drives the same core
functions (app.core.attachment_upload) out of the normal request order to reproduce the exact
state a crash would leave -- matching this codebase's own established "force via a test hook"
convention (e.g. test_attachments.py's own DB-level forcing technique)."""

import hashlib
import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.core import attachment_upload as core
from app.core.security import hash_password
from app.models.attachment import Attachment
from app.models.attachment_upload_session import AttachmentUploadChunk, AttachmentUploadSession
from app.models.user import User, UserRole
from tests.conftest import TestingSessionLocal


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _create_client_record(client, headers):
    res = client.post("/clients", json={"name": "P4 Upload Client", "type": "school"}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_project(client, headers, client_id):
    fields = {
        "client_id": client_id, "city": "Mumbai", "site_condition": "level", "soil_type": "normal",
        "building_status": "open_air", "site_access": "good", "power_available": "yes",
        "water_available": True, "package": "standard",
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _draft_cost_sheet(client, headers):
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    res = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": 100000}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


CONTENT = b"A" * 30 + b"B" * 30 + b"C" * 10  # 3 chunks of size 30/30/10 against chunk_size=30
DECLARED_SHA256 = hashlib.sha256(CONTENT).hexdigest()


def _start_session(db_session, current_user, doc_type="cost_sheet", doc_id=None, declared_size=70, chunk_size=30, sha=None):
    return core.start_session(
        db_session, current_user, doc_type, doc_id, "evidence.bin", declared_size, sha or DECLARED_SHA256, chunk_size,
    )


def _upload_all_chunks(db_session, session, content=CONTENT, chunk_size=30):
    for index in range(session.total_chunks):
        chunk_bytes = content[index * chunk_size: (index + 1) * chunk_size]
        attempt = core.claim_chunk(db_session, session.id, index)
        result = core.write_and_promote_chunk(db_session, session.id, index, attempt, chunk_bytes)
        assert result["promoted"], result


def _director(db_session):
    user = db_session.query(User).filter(User.email == "director@test.local").first()
    assert user is not None
    return user


# ---------------------------------------------------------------------------
# Happy path: proves the plumbing works before testing the edge cases
# ---------------------------------------------------------------------------


def test_full_chunked_upload_happy_path(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    current_user = _director(db_session)

    session = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))
    assert session.total_chunks == 3
    _upload_all_chunks(db_session, session)

    attempt_token = core.start_completion(db_session, session.id)
    assembled = core.assemble_and_validate(db_session, session.id, attempt_token)
    attachment = core.finalize_completion(db_session, session.id, attempt_token, assembled, current_user)

    db_session.refresh(session)
    assert session.status == "completed"
    assert session.resulting_attachment_id == attachment.id
    assert attachment.original_sha256 == DECLARED_SHA256
    from pathlib import Path

    assert Path(attachment.storage_path).read_bytes() == CONTENT
    # step 5 already ran inside finalize_completion -- temp files are gone
    assert session.temp_files_purged_at is not None
    temp_dir = core._session_temp_dir(session.id)
    assert list(temp_dir.iterdir()) == []


# ---------------------------------------------------------------------------
# Chunk integrity
# ---------------------------------------------------------------------------


def test_chunk_byte_count_mismatch_refused_immediately(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    current_user = _director(db_session)
    session = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))

    attempt = core.claim_chunk(db_session, session.id, 0)
    try:
        core.write_and_promote_chunk(db_session, session.id, 0, attempt, b"too short")
        assert False, "expected a size-mismatch refusal"
    except core.UploadProtocolError as exc:
        assert exc.status_code == 422

    chunk = db_session.get(AttachmentUploadChunk, (session.id, 0))
    assert chunk.status == "pending_write"  # never promoted


def test_chunk_writes_frozen_during_completion(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    current_user = _director(db_session)
    session = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))
    _upload_all_chunks(db_session, session)
    core.start_completion(db_session, session.id)  # status is now 'completing'

    try:
        core.claim_chunk(db_session, session.id, 0)
        assert False, "expected a refusal while completing"
    except core.UploadProtocolError as exc:
        assert exc.status_code == 409


# ---------------------------------------------------------------------------
# The fencing token -- revision 5/6/7's central guarantee
# ---------------------------------------------------------------------------


def test_recovered_worker_never_clobbers_a_real_completion_that_already_won(client, director_user, db_session):
    """A second attempt completes successfully after recovery; the ORIGINAL (token-N) worker
    then tries its own late final commit. Expected: refused, no orphaned Attachment row."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    current_user = _director(db_session)
    session = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))
    _upload_all_chunks(db_session, session)

    token_n = core.start_completion(db_session, session.id)  # token N, status='completing'
    assembled_n = core.assemble_and_validate(db_session, session.id, token_n)

    # Recovery fires (simulate the 5-minute timeout having passed) -- bumps the token atomically.
    past = datetime.now(UTC) - timedelta(minutes=10)
    db_session.query(AttachmentUploadSession).filter(AttachmentUploadSession.id == session.id).update(
        {"last_activity_at": past}
    )
    db_session.commit()
    recovered = core.recover_stuck_sessions(db_session, now=datetime.now(UTC))
    assert recovered == 1
    db_session.refresh(session)
    assert session.status == "uploading"
    assert session.completion_attempt == token_n + 1  # bumped in the SAME statement as the reset

    # A second attempt begins and completes successfully (token N+2).
    token_n2 = core.start_completion(db_session, session.id)
    assert token_n2 == token_n + 2
    assembled_n2 = core.assemble_and_validate(db_session, session.id, token_n2)
    real_attachment = core.finalize_completion(db_session, session.id, token_n2, assembled_n2, current_user)

    # The original (token-N) worker, having merely been slow, now tries its own late commit.
    before_count = db_session.query(Attachment).count()
    try:
        core.finalize_completion(db_session, session.id, token_n, assembled_n, current_user)
        assert False, "expected the stale attempt's commit to be refused"
    except core.UploadProtocolError as exc:
        assert exc.status_code == 409

    db_session.refresh(session)
    assert session.status == "completed"
    assert session.resulting_attachment_id == real_attachment.id  # untouched
    assert db_session.query(Attachment).count() == before_count  # no orphaned row from the stale attempt


def test_recovered_worker_refused_before_any_new_completion_attempt_begins(client, director_user, db_session):
    """The exact gap revision 6 left open, closed in revision 7: the old worker finishes AFTER
    recovery but BEFORE any new completion attempt starts."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    current_user = _director(db_session)
    session = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))
    _upload_all_chunks(db_session, session)

    token_n = core.start_completion(db_session, session.id)
    assembled_n = core.assemble_and_validate(db_session, session.id, token_n)

    past = datetime.now(UTC) - timedelta(minutes=10)
    db_session.query(AttachmentUploadSession).filter(AttachmentUploadSession.id == session.id).update(
        {"last_activity_at": past}
    )
    db_session.commit()
    core.recover_stuck_sessions(db_session, now=datetime.now(UTC))
    db_session.refresh(session)
    assert session.status == "uploading"
    assert session.completion_attempt == token_n + 1

    # Nothing else in flight. The stale worker tries its final commit now.
    try:
        core.finalize_completion(db_session, session.id, token_n, assembled_n, current_user)
        assert False, "expected refusal -- status is 'uploading', not 'completing', and the token no longer matches"
    except core.UploadProtocolError as exc:
        assert exc.status_code == 409

    db_session.refresh(session)
    assert session.status == "uploading"
    assert session.resulting_attachment_id is None
    assert db_session.query(Attachment).count() == 0


def test_concurrent_completion_requests_never_both_proceed(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    current_user = _director(db_session)
    session = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))
    _upload_all_chunks(db_session, session)

    token_a = core.start_completion(db_session, session.id)
    assert token_a == 1
    try:
        core.start_completion(db_session, session.id)  # a second request, same session, right after
        assert False, "expected the second completion start to be refused"
    except core.UploadProtocolError as exc:
        assert exc.status_code == 409


# ---------------------------------------------------------------------------
# Crash tests, before and after the commit (revision 6/7)
# ---------------------------------------------------------------------------


def test_crash_between_file_placement_and_commit_leaves_an_orphan_file_never_an_orphan_receipt(
    client, director_user, db_session,
):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    current_user = _director(db_session)
    session = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))
    _upload_all_chunks(db_session, session)

    token = core.start_completion(db_session, session.id)
    assembled = core.assemble_and_validate(db_session, session.id, token)

    # Simulate the crash: place the file (step 3) but never reach the commit (step 4) --
    # reproduce exactly what finalize_completion's own rename does, then stop.
    import os

    final_path = core.final_attachment_path(session.doc_type, session.doc_id, session.filename, session.id, token)
    os.replace(assembled, final_path)
    assert final_path.exists()

    # Immediately after the "crash": no Attachment row, receipt still empty.
    assert db_session.query(Attachment).filter(Attachment.storage_path == str(final_path)).first() is None
    db_session.refresh(session)
    assert session.status == "completing"
    assert session.resulting_attachment_id is None

    # Too early: the attempt is not yet superseded (completion_attempt hasn't moved past `token`)
    # -- cleanup must NOT remove the file yet.
    removed_too_early = core.sweep_orphaned_final_path_files(db_session)
    assert removed_too_early == 0
    assert final_path.exists()

    # Recovery supersedes this attempt (token moves past it).
    past = datetime.now(UTC) - timedelta(minutes=10)
    db_session.query(AttachmentUploadSession).filter(AttachmentUploadSession.id == session.id).update(
        {"last_activity_at": past}
    )
    db_session.commit()
    core.recover_stuck_sessions(db_session, now=datetime.now(UTC))
    db_session.refresh(session)
    assert session.completion_attempt == token + 1

    # Now cleanup (a fresh query, no reference to anything held in memory by the "crashed" call
    # above) recomputes the same deterministic path purely from the session row and removes it.
    removed = core.sweep_orphaned_final_path_files(db_session)
    assert removed == 1
    assert not final_path.exists()


def test_crash_after_commit_before_temp_cleanup_leaves_receipt_and_file_both_intact(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    current_user = _director(db_session)
    session = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))
    _upload_all_chunks(db_session, session)

    token = core.start_completion(db_session, session.id)
    assembled = core.assemble_and_validate(db_session, session.id, token)

    # Reproduce finalize_completion's steps 2-4 manually, stopping right after the commit --
    # simulating a crash between step 4 and step 5 (temp cleanup).
    import os
    from app.models.setting import DocumentType
    from app.api.attachments import _safe_filename

    final_path = core.final_attachment_path(session.doc_type, session.doc_id, session.filename, session.id, token)
    os.replace(assembled, final_path)
    new_attachment = Attachment(
        id=uuid.uuid4(), doc_type=DocumentType(session.doc_type), doc_id=session.doc_id,
        original_filename=_safe_filename(session.filename), original_size=session.declared_size,
        original_sha256=session.declared_sha256, storage_path=str(final_path),
        tag=core._default_tag_for_doc_type(session.doc_type), uploaded_by_id=current_user.id, version=1,
    )
    db_session.add(new_attachment)
    db_session.flush()  # autoflush=False -- the UPDATE below needs new_attachment.id to exist first
    db_session.query(AttachmentUploadSession).filter(AttachmentUploadSession.id == session.id).update(
        {"status": "completed", "resulting_attachment_id": new_attachment.id}
    )
    db_session.commit()
    # (finalize_completion would now call purge_session_temp_files -- we deliberately don't,
    # simulating the crash right here.)

    db_session.refresh(session)
    assert session.status == "completed"
    assert session.resulting_attachment_id == new_attachment.id
    assert final_path.read_bytes() == CONTENT
    assert session.temp_files_purged_at is None
    temp_dir = core._session_temp_dir(session.id)
    assert any(temp_dir.iterdir())  # accepted chunk files are still there

    # Retryable cleanup (sweep 2) picks it up.
    purged = core.purge_completed_session_temp_files(db_session)
    assert purged == 1
    db_session.refresh(session)
    assert session.temp_files_purged_at is not None
    assert list(temp_dir.iterdir()) == []
    # the receipt and the real file are completely untouched
    assert final_path.exists()
    assert db_session.get(Attachment, new_attachment.id) is not None


def test_completed_session_cleanup_is_retryable_and_a_safe_no_op_on_repetition(client, director_user, db_session):
    """Section 8 case 23's own wording, as its own dedicated test rather than folded into the
    crash test above: a completed session's temp files are removed, temp_files_purged_at is set,
    the receipt (Attachment row) and the real final file are both preserved throughout, and
    running cleanup again afterward changes nothing further -- the second call finds zero
    eligible sessions (temp_files_purged_at is no longer NULL) and purges nothing, not merely
    'doesn't error'."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    current_user = _director(db_session)
    session = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))
    _upload_all_chunks(db_session, session)
    token = core.start_completion(db_session, session.id)
    assembled = core.assemble_and_validate(db_session, session.id, token)
    attachment = core.finalize_completion(db_session, session.id, token, assembled, current_user)
    db_session.commit()

    db_session.refresh(session)
    assert session.status == "completed"
    assert session.resulting_attachment_id == attachment.id
    final_path = Path(attachment.storage_path)
    original_mtime = final_path.stat().st_mtime
    # finalize_completion already purges its own session's temp files as its last step (Section
    # 4) -- force temp_files_purged_at back to NULL with real leftover files on disk, so this
    # test genuinely exercises the retryable cleanup sweep itself, not finalize_completion's own
    # synchronous purge.
    temp_dir = core._session_temp_dir(session.id)
    (temp_dir / "leftover.part").write_bytes(b"stray bytes a real interrupted purge could leave")
    db_session.query(AttachmentUploadSession).filter(AttachmentUploadSession.id == session.id).update(
        {"temp_files_purged_at": None}
    )
    db_session.commit()

    first = core.purge_completed_session_temp_files(db_session)
    assert first == 1
    db_session.refresh(session)
    assert session.temp_files_purged_at is not None
    first_purged_at = session.temp_files_purged_at
    assert list(temp_dir.iterdir()) == []  # the leftover file, and everything else, is gone
    assert final_path.exists() and final_path.stat().st_mtime == original_mtime  # untouched
    assert db_session.get(Attachment, attachment.id) is not None

    # Repetition: a safe no-op, not merely error-free -- zero sessions match this time.
    second = core.purge_completed_session_temp_files(db_session)
    assert second == 0
    db_session.refresh(session)
    assert session.temp_files_purged_at == first_purged_at  # unchanged by the no-op second call
    assert final_path.exists() and final_path.stat().st_mtime == original_mtime
    assert db_session.get(Attachment, attachment.id) is not None


def test_cleanup_reconstructs_an_orphan_using_a_fresh_session_object(
    client, director_user, db_session,
):
    """A fresh Session object (its own identity map, its own connection) -- no Python-level
    reference to anything the 'crashed' call above held, only a bare id -- must still find and
    safely remove the orphan using only what the database durably recorded. This proves the
    reconstruction logic itself is correct; it does NOT prove cross-process independence (same
    Python process, same module-level state) -- see the dedicated subprocess test below for that
    literal claim."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    current_user = _director(db_session)
    session = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))
    _upload_all_chunks(db_session, session)
    token = core.start_completion(db_session, session.id)
    assembled = core.assemble_and_validate(db_session, session.id, token)
    import os

    final_path = core.final_attachment_path(session.doc_type, session.doc_id, session.filename, session.id, token)
    os.replace(assembled, final_path)
    session_id = session.id  # the only thing carried across -- a bare id, exactly as a DB row provides

    past = datetime.now(UTC) - timedelta(minutes=10)
    db_session.query(AttachmentUploadSession).filter(AttachmentUploadSession.id == session_id).update(
        {"last_activity_at": past}
    )
    db_session.commit()
    core.recover_stuck_sessions(db_session, now=datetime.now(UTC))

    fresh = TestingSessionLocal()
    try:
        removed = core.sweep_orphaned_final_path_files(fresh)
        assert removed == 1
    finally:
        fresh.close()
    assert not final_path.exists()

    # Negative variant: a normally-completed attempt's file is never touched by the same sweep.
    session2 = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))
    _upload_all_chunks(db_session, session2)
    token2 = core.start_completion(db_session, session2.id)
    assembled2 = core.assemble_and_validate(db_session, session2.id, token2)
    real = core.finalize_completion(db_session, session2.id, token2, assembled2, current_user)
    fresh2 = TestingSessionLocal()
    try:
        removed2 = core.sweep_orphaned_final_path_files(fresh2)
        assert removed2 == 0
    finally:
        fresh2.close()
    from pathlib import Path

    assert Path(real.storage_path).exists()


def test_cleanup_reconstructs_an_orphan_across_a_real_separate_process(client, director_user, db_session):
    """The literal claim: a genuinely separate OS process -- no shared Python interpreter, no
    shared module state, no shared identity map, started fresh -- invoking the real, deployable
    cleanup script (scripts/cleanup_attachment_upload_sessions.py), pointed at the test database
    only via DATABASE_URL, must find and safely remove the orphan using nothing but what the
    database durably recorded."""
    import os
    import subprocess
    import sys

    from tests.conftest import TEST_DATABASE_URL

    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    current_user = _director(db_session)
    session = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))
    _upload_all_chunks(db_session, session)
    token = core.start_completion(db_session, session.id)
    assembled = core.assemble_and_validate(db_session, session.id, token)

    final_path = core.final_attachment_path(session.doc_type, session.doc_id, session.filename, session.id, token)
    os.replace(assembled, final_path)

    past = datetime.now(UTC) - timedelta(minutes=10)
    db_session.query(AttachmentUploadSession).filter(AttachmentUploadSession.id == session.id).update(
        {"last_activity_at": past}
    )
    db_session.commit()
    core.recover_stuck_sessions(db_session, now=datetime.now(UTC))  # supersedes the attempt
    assert final_path.exists()

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ)
    env["DATABASE_URL"] = TEST_DATABASE_URL  # the database this test's own writes are visible in
    # ATTACHMENT_STORAGE_ROOT: the subprocess gets its own fresh Settings instance, which never
    # sees the isolated_attachment_storage fixture's in-process tmp_path redirect -- without this,
    # the subprocess computes a DIFFERENT (default) storage root and correctly finds nothing at
    # the wrong path, which would prove nothing about the real reconstruction logic.
    env["ATTACHMENT_STORAGE_ROOT"] = core.settings.attachment_storage_root
    env["PYTHONPATH"] = backend_dir

    # --dry-run first: prove detection without mutation, from the real script, in the real process.
    preview = subprocess.run(
        [sys.executable, "scripts/cleanup_attachment_upload_sessions.py", "--dry-run"],
        cwd=backend_dir, env=env, capture_output=True, text=True, timeout=30,
    )
    assert preview.returncode == 0, preview.stderr
    preview_line = next(l for l in preview.stdout.splitlines() if "Orphaned final-path files" in l)
    assert preview_line.rstrip().endswith("1"), preview.stdout
    assert final_path.exists()  # dry-run: still there

    real_run = subprocess.run(
        [sys.executable, "scripts/cleanup_attachment_upload_sessions.py"],
        cwd=backend_dir, env=env, capture_output=True, text=True, timeout=30,
    )
    assert real_run.returncode == 0, real_run.stderr
    real_line = next(l for l in real_run.stdout.splitlines() if "Orphaned final-path files" in l)
    assert real_line.rstrip().endswith("1"), real_run.stdout
    assert not final_path.exists()  # actually removed, by a process that shared nothing with this one


# ---------------------------------------------------------------------------
# Chunk-write race (revision 5/6)
# ---------------------------------------------------------------------------


def test_two_overlapping_writes_for_the_same_chunk_never_interleave(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    current_user = _director(db_session)
    session = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))

    attempt_1 = core.claim_chunk(db_session, session.id, 0)  # claimed_attempt=1
    assert attempt_1 == 1
    # The client retries before attempt 1's write ever reaches promotion.
    attempt_2 = core.claim_chunk(db_session, session.id, 0)  # claimed_attempt bumped to 2
    assert attempt_2 == 2

    # Attempt 2's write finishes and promotes first.
    result_2 = core.write_and_promote_chunk(db_session, session.id, 0, attempt_2, b"B" * 30)
    assert result_2["promoted"]

    # Attempt 1's delayed write now tries to promote -- must be refused, never overwrite attempt 2.
    result_1 = core.write_and_promote_chunk(db_session, session.id, 0, attempt_1, b"A" * 30)
    assert result_1 == {"promoted": False, "reason": "superseded by a newer retry of this chunk"}

    accepted = core._chunk_accepted_path(session.id, 0).read_bytes()
    assert accepted == b"B" * 30  # only attempt 2's bytes, never a mix


def test_abandoned_pending_write_claim_reclaimed_by_ordinary_retry_and_swept(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    current_user = _director(db_session)
    session = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))

    attempt_1 = core.claim_chunk(db_session, session.id, 0)
    partial_path = core._chunk_temp_path(session.id, 0, attempt_1)
    partial_path.write_bytes(b"partial, abandoned")  # never promoted

    attempt_2 = core.claim_chunk(db_session, session.id, 0)
    assert attempt_2 == 2
    result = core.write_and_promote_chunk(db_session, session.id, 0, attempt_2, b"A" * 30)
    assert result["promoted"]

    assert partial_path.exists()  # attempt 1's leftover file, not yet swept
    removed = core.sweep_orphaned_attempt_temp_files(db_session)
    assert removed == 1
    assert not partial_path.exists()
    assert core._chunk_accepted_path(session.id, 0).exists()  # attempt 2's promoted result untouched


# ---------------------------------------------------------------------------
# Lock order: chunk promotion vs. completion never deadlock (revision 6 fix)
# ---------------------------------------------------------------------------


def test_chunk_promotion_and_completion_never_deadlock(client, director_user, db_session):
    """A real concurrency test: two threads, two independent DB sessions, contending for the
    same session row at the same time. Both must finish within a short timeout -- a lock-order
    bug would show up here as one thread hanging forever."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    current_user = _director(db_session)
    session = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))
    # Leave chunk 0/1 written, chunk 2 not yet -- so completion will refuse (not proceed), but
    # the point is that the ATTEMPT to lock the session row must never hang.
    for index in (0, 1):
        attempt = core.claim_chunk(db_session, session.id, index)
        core.write_and_promote_chunk(db_session, session.id, index, attempt, CONTENT[index * 30:(index + 1) * 30])
    db_session.commit()
    # Captured once, before any thread starts: db_session.commit() expires `session`'s
    # attributes, and re-reading session.id from two background threads afterward races on the
    # SAME non-thread-safe Session object's own refresh-on-access -- a real, pre-existing bug in
    # this test (its sibling test_cleanup_cannot_race_an_active_session already avoids it this
    # same way), caught via ObjectDeletedError once a faster/slower connection-acquisition path
    # changed the race's timing.
    session_id = session.id

    results = {}

    def _try_chunk_promotion():
        s = TestingSessionLocal()
        try:
            attempt = core.claim_chunk(s, session_id, 2)
            results["chunk"] = core.write_and_promote_chunk(s, session_id, 2, attempt, CONTENT[60:70])
        except core.UploadProtocolError as exc:
            results["chunk"] = {"error": exc.status_code}
        finally:
            s.close()

    def _try_completion():
        s = TestingSessionLocal()
        try:
            results["completion"] = core.start_completion(s, session_id)
        except core.UploadProtocolError as exc:
            results["completion"] = {"error": exc.status_code}
        finally:
            s.close()

    t1 = threading.Thread(target=_try_chunk_promotion)
    t2 = threading.Thread(target=_try_completion)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert not t1.is_alive(), "chunk promotion thread hung -- possible deadlock"
    assert not t2.is_alive(), "completion thread hung -- possible deadlock"
    assert "chunk" in results and "completion" in results


# ---------------------------------------------------------------------------
# Two different sessions, same file, both succeed independently (scope reduction, revision 4)
# ---------------------------------------------------------------------------


def test_two_different_sessions_same_file_both_succeed(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    current_user = _director(db_session)

    session_a = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))
    _upload_all_chunks(db_session, session_a)
    token_a = core.start_completion(db_session, session_a.id)
    assembled_a = core.assemble_and_validate(db_session, session_a.id, token_a)
    attachment_a = core.finalize_completion(db_session, session_a.id, token_a, assembled_a, current_user)

    session_b = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))
    _upload_all_chunks(db_session, session_b)
    token_b = core.start_completion(db_session, session_b.id)
    assembled_b = core.assemble_and_validate(db_session, session_b.id, token_b)
    attachment_b = core.finalize_completion(db_session, session_b.id, token_b, assembled_b, current_user)

    assert attachment_a.id != attachment_b.id
    assert attachment_a.original_sha256 == attachment_b.original_sha256 == DECLARED_SHA256


# ---------------------------------------------------------------------------
# dry-run makes no database or filesystem changes -- explicit verification
# ---------------------------------------------------------------------------


def test_dry_run_cleanup_makes_no_database_or_filesystem_changes(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    current_user = _director(db_session)

    # An abandoned (uploading, stale) session with a real temp chunk file.
    abandoned = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))
    abandoned_id = abandoned.id  # captured now -- cleanup deletes this row; a bare id survives that
    attempt = core.claim_chunk(db_session, abandoned_id, 0)
    core.write_and_promote_chunk(db_session, abandoned_id, 0, attempt, CONTENT[:30])
    old = datetime.now(UTC) - timedelta(hours=48)
    db_session.query(AttachmentUploadSession).filter(AttachmentUploadSession.id == abandoned_id).update(
        {"last_activity_at": old}
    )
    db_session.commit()

    # A stuck (completing, stale) session -- eligible for a token reset.
    stuck = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))
    _upload_all_chunks(db_session, stuck)
    stuck_token = core.start_completion(db_session, stuck.id)
    db_session.query(AttachmentUploadSession).filter(AttachmentUploadSession.id == stuck.id).update(
        {"last_activity_at": datetime.now(UTC) - timedelta(minutes=10)}
    )
    db_session.commit()

    # A completed session with unpurged temp files.
    completed = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))
    _upload_all_chunks(db_session, completed)
    completed_token = core.start_completion(db_session, completed.id)
    assembled = core.assemble_and_validate(db_session, completed.id, completed_token)
    import os

    final_path = core.final_attachment_path(
        completed.doc_type, completed.doc_id, completed.filename, completed.id, completed_token
    )
    os.replace(assembled, final_path)
    from app.models.setting import DocumentType
    from app.api.attachments import _safe_filename

    real_attachment = Attachment(
        id=uuid.uuid4(), doc_type=DocumentType(completed.doc_type), doc_id=completed.doc_id,
        original_filename=_safe_filename(completed.filename), original_size=completed.declared_size,
        original_sha256=completed.declared_sha256, storage_path=str(final_path),
        tag=core._default_tag_for_doc_type(completed.doc_type), uploaded_by_id=current_user.id, version=1,
    )
    db_session.add(real_attachment)
    db_session.flush()  # autoflush=False -- the UPDATE below needs real_attachment.id to exist first
    db_session.query(AttachmentUploadSession).filter(AttachmentUploadSession.id == completed.id).update(
        {"status": "completed", "resulting_attachment_id": real_attachment.id}
    )
    db_session.commit()

    # Snapshot everything before the dry run.
    def _snapshot():
        sessions = {
            s.id: (s.status, s.completion_attempt, s.temp_files_purged_at)
            for s in db_session.query(AttachmentUploadSession).all()
        }
        chunks = {(c.session_id, c.chunk_index): c.status for c in db_session.query(AttachmentUploadChunk).all()}
        files = set()
        root = core.Path(core.settings.attachment_storage_root)
        for p in root.rglob("*"):
            if p.is_file():
                files.add(str(p))
        return sessions, chunks, files

    before = _snapshot()
    result = core.run_cleanup(db_session, dry_run=True)
    db_session.expire_all()
    after = _snapshot()

    assert before == after, "dry-run must leave every session, chunk, and file exactly as it found them"
    assert result["abandoned_sessions_purged"] == 1
    assert result["stuck_sessions_recovered"] == 1
    assert result["completed_sessions_temp_purged"] == 1

    # Now the real run actually changes things.
    real_result = core.run_cleanup(db_session, dry_run=False)
    assert real_result == result
    db_session.expire_all()
    # a plain query, not .get() -- .get() on an id already known-deleted in this session's own
    # identity map raises ObjectDeletedError rather than returning None; a real fresh SELECT
    # (which is what a different request/process would issue) correctly finds nothing.
    assert db_session.query(AttachmentUploadSession).filter_by(id=abandoned_id).first() is None  # purged
    stuck_after = db_session.get(AttachmentUploadSession, stuck.id)
    assert stuck_after.status == "uploading"
    assert stuck_after.completion_attempt == stuck_token + 1  # token actually moved this time
    completed_after = db_session.get(AttachmentUploadSession, completed.id)
    assert completed_after.temp_files_purged_at is not None
    assert final_path.exists()  # the real attachment's own file is always untouched


# ---------------------------------------------------------------------------
# HTTP-level: idempotent retry, reauthorization, cleanup-vs-active-session race
# ---------------------------------------------------------------------------


def _sales_headers(client, db_session, email="sales-upload@test.local"):
    user = User(name="Test Sales", email=email, hashed_password=hash_password("TestPass!1"), role=UserRole.SALES)
    db_session.add(user)
    db_session.commit()
    return _login(client, email)


def _start_session_http(client, headers, doc_type, doc_id, declared_size=70, chunk_size=30, sha=None):
    res = client.post(
        "/attachments/upload-sessions",
        json={
            "doc_type": doc_type, "doc_id": str(doc_id), "filename": "evidence.bin",
            "declared_size": declared_size, "declared_sha256": sha or DECLARED_SHA256, "chunk_size": chunk_size,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def _upload_all_chunks_http(client, headers, session_id, content=CONTENT, chunk_size=30, total_chunks=3):
    for index in range(total_chunks):
        chunk_bytes = content[index * chunk_size: (index + 1) * chunk_size]
        res = client.post(
            f"/attachments/upload-sessions/{session_id}/chunks/{index}",
            files={"file": ("chunk", chunk_bytes, "application/octet-stream")},
            headers=headers,
        )
        assert res.status_code == 200, res.text
        assert res.json()["promoted"], res.text


def test_session_responses_echo_the_authoritative_chunk_size(client, director_user, db_session):
    """The client proposes a chunk_size at start; the server's own record of it (not the
    client's local constant) is what every later slicing/indexing decision must use, especially
    on resume -- both the start response and the status response must carry it."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    session = _start_session_http(client, headers, "cost_sheet", cost_sheet_id, declared_size=70, chunk_size=30)
    assert session["chunk_size"] == 30

    status = client.get(f"/attachments/upload-sessions/{session['id']}/status", headers=headers)
    assert status.status_code == 200, status.text
    assert status.json()["chunk_size"] == 30


def test_final_partial_chunk_is_computed_from_the_authoritative_chunk_size(client, director_user, db_session):
    """declared_size=70, chunk_size=30 -> chunks of 30/30/10. The last chunk's expected size is
    declared_size - chunk_size*(total_chunks-1), not chunk_size itself -- confirm a correctly
    sized final partial chunk is accepted and an incorrectly sized one (chunk_size-sized) is not."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    session = _start_session_http(client, headers, "cost_sheet", cost_sheet_id, declared_size=70, chunk_size=30)
    assert session["total_chunks"] == 3

    for index, size in ((0, 30), (1, 30)):
        res = client.post(
            f"/attachments/upload-sessions/{session['id']}/chunks/{index}",
            files={"file": ("chunk", CONTENT[index * 30:(index + 1) * 30], "application/octet-stream")},
            headers=headers,
        )
        assert res.status_code == 200 and res.json()["promoted"], res.text

    # Wrong: sending chunk_size (30) bytes for the final index, instead of the true remainder (10).
    wrong = client.post(
        f"/attachments/upload-sessions/{session['id']}/chunks/2",
        files={"file": ("chunk", b"X" * 30, "application/octet-stream")}, headers=headers,
    )
    assert wrong.status_code == 422, wrong.text

    # Right: the true remainder (10 bytes).
    right = client.post(
        f"/attachments/upload-sessions/{session['id']}/chunks/2",
        files={"file": ("chunk", CONTENT[60:70], "application/octet-stream")}, headers=headers,
    )
    assert right.status_code == 200 and right.json()["promoted"], right.text


def test_lost_success_response_retry_is_idempotent(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    session = _start_session_http(client, headers, "cost_sheet", cost_sheet_id)
    _upload_all_chunks_http(client, headers, session["id"])

    res1 = client.post(f"/attachments/upload-sessions/{session['id']}/complete", headers=headers)
    assert res1.status_code == 200, res1.text
    attachment_1 = res1.json()

    # The client never saw res1 (simulated: it just retries the same call).
    res2 = client.post(f"/attachments/upload-sessions/{session['id']}/complete", headers=headers)
    assert res2.status_code == 200, res2.text
    attachment_2 = res2.json()

    assert attachment_1["id"] == attachment_2["id"]
    count = db_session.query(Attachment).filter(Attachment.id == attachment_1["id"]).count()
    assert count == 1  # no duplicate Attachment created by the retry


def test_reauthorization_refuses_a_different_user_on_every_session_endpoint(client, director_user, db_session):
    """Proves SESSION-OWNERSHIP enforcement (created_by_id) -- a user who never created this
    session at all. This is necessary but not sufficient: it does not prove the original
    uploader loses access once the underlying DOCUMENT's ownership changes out from under them
    -- see test_reauthorization_refuses_the_original_uploader_after_project_reassignment for
    that distinct claim."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    session = _start_session_http(client, headers, "cost_sheet", cost_sheet_id)
    _upload_all_chunks_http(client, headers, session["id"])
    complete_res = client.post(f"/attachments/upload-sessions/{session['id']}/complete", headers=headers)
    assert complete_res.status_code == 200, complete_res.text

    other_headers = _sales_headers(client, db_session)
    # inspect/resume
    res = client.get(f"/attachments/upload-sessions/{session['id']}", headers=other_headers)
    assert res.status_code == 403, res.text
    res = client.get(f"/attachments/upload-sessions/{session['id']}/status", headers=other_headers)
    assert res.status_code == 403, res.text
    # chunk upload (would 409 anyway since it's completed -- but auth must refuse FIRST, at 403)
    res = client.post(
        f"/attachments/upload-sessions/{session['id']}/chunks/0",
        files={"file": ("x", b"x", "application/octet-stream")}, headers=other_headers,
    )
    assert res.status_code == 403, res.text
    # a retry against an already-completed session is not exempt either
    res = client.post(f"/attachments/upload-sessions/{session['id']}/complete", headers=other_headers)
    assert res.status_code == 403, res.text


def test_reauthorization_refuses_the_original_uploader_after_project_reassignment(client, director_user, db_session):
    """Case 20's actual claim: reassign the parent Project mid-session (Amendment 60 scoping ON)
    -- the ORIGINAL uploader, who still owns the SESSION row itself (created_by_id unchanged),
    must be refused on chunk-upload, resume-inspection, and a retry against an already-completed
    session, once they no longer own the document's project. Session ownership alone is not
    authorization; the target document's current access is re-checked independently, every time."""
    from tests.test_quotations_admin import _add_project_sport, _create_client_record, _create_project, _role_headers

    director = _director_headers(client, director_user)
    assert client.put("/ownership/switch", json={"on": True}, headers=director).status_code == 200

    sales_a = _role_headers(client, db_session, UserRole.SALES, "sales-a-reassign@test.local")
    sales_b = _role_headers(client, db_session, UserRole.SALES, "sales-b-reassign@test.local")
    a_id = client.get("/auth/me", headers=sales_a).json()["id"]
    b_id = client.get("/auth/me", headers=sales_b).json()["id"]

    # Director builds the world, then hands it to Sales A -- same established pattern as
    # test_own_records.py's own _give/_world helpers.
    client_id = _create_client_record(client, director, "Reassignment Test Client")
    project_id = _create_project(client, director, client_id)
    project_sport_id = _add_project_sport(client, director, project_id, "box_cricket")
    cost_sheet_id = client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": 100000}, headers=director
    ).json()["id"]
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=director)
    estimate_id = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 100000}]},
        headers=director,
    ).json()["id"]
    give = client.patch(f"/ownership/client/{client_id}", json={"owner_id": a_id, "cascade": True}, headers=director)
    assert give.status_code == 200, give.text  # the project follows the client

    # Scenario 1: reassignment mid-session, before completion. Sales A starts a session and
    # writes one chunk while they still own it.
    session = _start_session_http(client, sales_a, "estimate", estimate_id)
    res = client.post(
        f"/attachments/upload-sessions/{session['id']}/chunks/0",
        files={"file": ("chunk", CONTENT[:30], "application/octet-stream")}, headers=sales_a,
    )
    assert res.status_code == 200 and res.json()["promoted"], res.text

    # Reassign the client (and cascaded project) away from A, to B.
    reassign = client.patch(f"/ownership/client/{client_id}", json={"owner_id": b_id, "cascade": True}, headers=director)
    assert reassign.status_code == 200, reassign.text

    # A (still created_by_id on the session) is now refused everywhere on this session.
    res = client.get(f"/attachments/upload-sessions/{session['id']}", headers=sales_a)
    assert res.status_code == 404, res.text  # Amendment 60's concealed NOT_FOUND, not 403
    res = client.get(f"/attachments/upload-sessions/{session['id']}/status", headers=sales_a)
    assert res.status_code == 404, res.text
    res = client.post(
        f"/attachments/upload-sessions/{session['id']}/chunks/1",
        files={"file": ("chunk", CONTENT[30:60], "application/octet-stream")}, headers=sales_a,
    )
    assert res.status_code == 404, res.text
    res = client.post(f"/attachments/upload-sessions/{session['id']}/complete", headers=sales_a)
    assert res.status_code == 404, res.text

    # Scenario 2: reassignment AFTER completion -- a retry against an already-completed session
    # is not exempt. Give the project back to A, let them complete a fresh session normally,
    # THEN reassign away, THEN retry /complete.
    client.patch(f"/ownership/client/{client_id}", json={"owner_id": a_id, "cascade": True}, headers=director)
    session2 = _start_session_http(client, sales_a, "estimate", estimate_id)
    _upload_all_chunks_http(client, sales_a, session2["id"])
    complete_res = client.post(f"/attachments/upload-sessions/{session2['id']}/complete", headers=sales_a)
    assert complete_res.status_code == 200, complete_res.text

    client.patch(f"/ownership/client/{client_id}", json={"owner_id": b_id, "cascade": True}, headers=director)
    retry_res = client.post(f"/attachments/upload-sessions/{session2['id']}/complete", headers=sales_a)
    assert retry_res.status_code == 404, retry_res.text  # refused, not the cached receipt


def test_cleanup_cannot_race_an_active_session(client, director_user, db_session):
    """Fixture a session right at the 24h abandoned-session boundary; fire a chunk upload and
    cleanup's own claim concurrently. Expected: exactly one wins by construction, never both,
    never a corrupted partial state."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    current_user = _director(db_session)
    session = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))
    session_id = session.id
    db_session.query(AttachmentUploadSession).filter(AttachmentUploadSession.id == session_id).update(
        {"last_activity_at": datetime.now(UTC) - timedelta(hours=24, seconds=1)}
    )
    db_session.commit()

    results = {}

    def _try_chunk_write():
        s = TestingSessionLocal()
        try:
            attempt = core.claim_chunk(s, session_id, 0)
            results["chunk"] = core.write_and_promote_chunk(s, session_id, 0, attempt, CONTENT[:30])
        except core.UploadProtocolError as exc:
            results["chunk"] = {"error": exc.status_code}
        finally:
            s.close()

    def _try_cleanup_claim():
        s = TestingSessionLocal()
        try:
            results["cleanup"] = core.claim_and_purge_abandoned_sessions(s, now=datetime.now(UTC))
        finally:
            s.close()

    t1 = threading.Thread(target=_try_chunk_write)
    t2 = threading.Thread(target=_try_cleanup_claim)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)
    assert not t1.is_alive() and not t2.is_alive()

    fresh = TestingSessionLocal()
    try:
        remaining = fresh.query(AttachmentUploadSession).filter(AttachmentUploadSession.id == session_id).first()
        if remaining is None:
            # cleanup won: the chunk write must have been refused (session gone by the time it
            # tried to act, or the locked status check already caught it) -- never both.
            assert results["chunk"] == {"error": 404} or results["chunk"] == {"error": 409}
        else:
            # the chunk write won: the session must still be exactly 'uploading', not purged out
            # from under a legitimately in-flight write.
            assert remaining.status == "uploading"
            assert results["chunk"].get("promoted") is True
    finally:
        fresh.close()


def test_claim_chunk_409_survives_the_row_vanishing_right_after_rollback(client, director_user, db_session, monkeypatch):
    """Deterministic version of the race the test above exercises only probabilistically.
    claim_chunk's status-mismatch branch used to call db.rollback() -- expiring session's
    attributes and releasing the row lock just taken -- and only THEN build its 409 message by
    reading session.status/total_chunks. A row deleted by someone else in that exact window
    (e.g. cleanup purging this same abandoned session) made that read raise ObjectDeletedError
    instead of the clean 409 this function means to return. Fixed by capturing both values
    before the rollback (app/core/attachment_upload.py). Forces the exact window deterministically
    by deleting the row, via a second real connection, from inside a wrapped rollback() call --
    no thread timing involved, so this either always catches a regression or never does."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    current_user = _director(db_session)
    session = _start_session(db_session, current_user, doc_id=uuid.UUID(cost_sheet_id))
    session_id = session.id
    # Not 'uploading' -- forces claim_chunk's status-mismatch branch (the one with the fixed
    # read-after-rollback), not its session-is-None branch.
    db_session.query(AttachmentUploadSession).filter(AttachmentUploadSession.id == session_id).update(
        {"status": "failed"}
    )
    db_session.commit()

    real_rollback = db_session.rollback

    def _rollback_then_delete_via_a_second_connection():
        real_rollback()
        other = TestingSessionLocal()
        try:
            other.query(AttachmentUploadSession).filter(AttachmentUploadSession.id == session_id).delete()
            other.commit()
        finally:
            other.close()

    monkeypatch.setattr(db_session, "rollback", _rollback_then_delete_via_a_second_connection)

    with pytest.raises(core.UploadProtocolError) as exc_info:
        core.claim_chunk(db_session, session_id, 0)
    assert exc_info.value.status_code == 409
