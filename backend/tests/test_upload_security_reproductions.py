"""Upload-security gates for three concerns raised from SOURCE INSPECTION of an earlier head (not demonstrated
exploits): (1) one prohibited-file policy across ordinary / supersede / resumable uploads, (2) permission
changes while a resumable upload is assembled and finalized, (3) resource limits.

SCOPE OF THE EVIDENCE. Every test covers a selected case. A passing test shows that case is handled; it does NOT
certify an entire upload path as secure. "Declared" quantities are what a client ASKS FOR when it opens a session;
nothing is stored until chunks are written, so e.g. thirty 100 MB sessions demonstrate acceptance of ~3 GB of
declarations, not 3 GB of stored data.

HOW THEY GATE. Each test asserts the SAFE behaviour with the SPECIFIC refusal (status code AND reason) and that the
database and storage tree are unchanged -- an unrelated 5xx can never count as protection. A confirmed, not-yet-fixed
gap carries `xfail(strict=True, raises=AssertionError)`: `raises=AssertionError` means only a failed safety assertion
counts as the known gap (a crash, 500 or missing attribute fails the test instead of passing vacuously), and
`strict=True` turns the test red the day the gap is fixed until the mark is removed. P5_UPLOAD_REPRO_RAW=1 drops the
marks to show the raw failures.

The limit numbers below are the PROPOSED policy (pending approval): chunk_size 64 KiB..16 MiB (a single chunk may
be smaller), at most 2,048 chunks, at most 10 open sessions and 500 MiB of declared bytes per user, a global storage
cap; refusal codes 422 (bad chunking) / 429 (per-user open limits) / 413 (size or storage)."""

import hashlib
import os
import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, text

from app.config import settings
from app.core import attachment_upload as upload_core
from app.models.attachment import Attachment
from app.models.attachment_upload_session import AttachmentUploadSession
from app.models.user import User
from tests.db_snapshot import full_snapshot, storage_snapshot
from tests.p5_concurrency import Op, Session, wait_until_blocked
from tests.p5_helpers import make_user, user_headers
from tests.test_work_orders import _director_headers, _won_quotation

RAW = bool(os.environ.get("P5_UPLOAD_REPRO_RAW"))
KIB, MIB = 1024, 1024 * 1024
MAX_OPEN_SESSIONS = 10
MAX_OPEN_DECLARED_BYTES = 500 * MIB
SESSION_TABLES = ("attachment_upload_sessions", "attachment_upload_chunks")


def known_gap(reason):
    return (lambda f: f) if RAW else pytest.mark.xfail(strict=True, raises=AssertionError, reason=reason)


# ------------------------------------------------------------------ helpers


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _start(client, headers, doc_type, doc_id, filename, content=b"x", chunk_size=None, declared_size=None):
    return client.post(
        "/attachments/upload-sessions",
        json={
            "doc_type": doc_type, "doc_id": str(doc_id), "filename": filename,
            "declared_size": declared_size if declared_size is not None else len(content),
            "declared_sha256": _sha(content), "chunk_size": chunk_size or max(len(content), 1),
        },
        headers=headers,
    )


def _put_chunks(client, headers, session_id, content, chunk_size):
    for index, offset in enumerate(range(0, len(content), chunk_size)):
        res = client.post(
            f"/attachments/upload-sessions/{session_id}/chunks/{index}",
            files={"file": (f"c{index}", content[offset:offset + chunk_size], "application/octet-stream")},
            headers=headers,
        )
        assert res.status_code == 200, res.text


def _complete(client, headers, session_id):
    return client.post(f"/attachments/upload-sessions/{session_id}/complete", headers=headers)


def _state(db):
    """What a refused request must leave untouched: every column of every row outside upload-session bookkeeping
    (a refused session may legitimately be marked failed), plus the stored-file tree."""
    return full_snapshot(db, exclude_tables=SESSION_TABLES), storage_snapshot(settings.attachment_storage_root)


def _count(db, model):
    db.rollback()
    db.expire_all()
    return db.query(func.count()).select_from(model).scalar()


@pytest.fixture()
def world(client, director_user, db_session):
    h = _director_headers(client, director_user)
    pid, q = _won_quotation(client, h)
    stages = client.get(f"/projects/{pid}/stages", headers=h).json()
    return dict(h=h, pid=pid, q=q, stage_id=stages[0]["id"], db=db_session, client=client, director_id=director_user.id)


# ================================================================== 1. one prohibited-file policy

NAMES = ["evil.html", "EVIL.HTML", "x.svg", "run.exe", "a.js", "trail.html. "]


@pytest.mark.parametrize("name", NAMES)
def test_ordinary_upload_refuses_prohibited_types_with_the_specific_reason_and_stores_nothing(world, name):
    before = _state(world["db"])
    res = world["client"].post(
        "/attachments", data={"doc_type": "quotation", "doc_id": world["q"], "tag": "reference"},
        files={"file": (name, b"<script>1</script>", "text/html")}, headers=world["h"],
    )
    assert res.status_code == 400 and "can't be attached" in res.json()["detail"], (name, res.status_code, res.text[:120])
    assert _state(world["db"]) == before


def test_supersede_refuses_prohibited_types_with_the_specific_reason_and_changes_nothing(world):
    client, h = world["client"], world["h"]
    first = client.post(
        "/attachments", data={"doc_type": "quotation", "doc_id": world["q"], "tag": "reference"},
        files={"file": ("ok.pdf", b"%PDF-1.4", "application/pdf")}, headers=h,
    ).json()
    before = _state(world["db"])
    res = client.post(
        f"/attachments/{first['id']}/supersede", data={"tag": "reference"},
        files={"file": ("evil.svg", b"<svg onload=alert(1)>", "image/svg+xml")}, headers=h,
    )
    assert res.status_code == 400 and "can't be attached" in res.json()["detail"], (res.status_code, res.text[:120])
    assert _state(world["db"]) == before  # the original is not superseded and nothing new is stored


@known_gap("the resumable path never applies BLOCKED_ATTACHMENT_EXTENSIONS at start_session()")
@pytest.mark.parametrize("name", NAMES)
def test_resumable_start_refuses_the_same_prohibited_types_with_the_same_reason(world, name):
    db = world["db"]
    sessions_before = _count(db, AttachmentUploadSession)
    before = _state(db)
    res = _start(world["client"], world["h"], "quotation", world["q"], name, b"<script>alert(1)</script>")
    assert res.status_code == 400 and "can't be attached" in res.json()["detail"], (name, res.status_code, res.text[:120])
    assert _count(db, AttachmentUploadSession) == sessions_before  # no session was opened
    assert _state(db) == before


@known_gap("sessions opened BEFORE a fix keep their old filename; finalize_completion() never re-applies the policy")
def test_a_pre_existing_session_with_a_prohibited_filename_is_refused_at_completion(world):
    client, h, db = world["client"], world["h"], world["db"]
    content = b"<script>alert(1)</script>"
    legacy = AttachmentUploadSession(
        doc_type="quotation", doc_id=uuid.UUID(world["q"]), filename="legacy-evil.html", declared_size=len(content),
        declared_sha256=_sha(content), chunk_size=len(content), total_chunks=1, status="uploading",
        completion_attempt=0, created_by_id=world["director_id"],
    )  # inserted directly: it never passed through any start-time policy
    db.add(legacy)
    db.commit()
    legacy_id = legacy.id
    _put_chunks(client, h, legacy_id, content, len(content))
    before = _state(db)
    res = _complete(client, h, legacy_id)
    assert res.status_code == 400 and "can't be attached" in res.json()["detail"], (res.status_code, res.text[:120])
    assert _state(db) == before  # no Attachment row and no final-path file
    db.rollback()
    db.expire_all()
    assert db.get(AttachmentUploadSession, legacy_id).status == "failed"


def test_resumable_filename_cannot_escape_the_storage_root(world):
    """One selected case (a '../' filename); not a certification of path handling."""
    client, h, db = world["client"], world["h"], world["db"]
    content = b"payload"
    started = _start(client, h, "quotation", world["q"], "../../../../escape.txt", content)
    assert started.status_code == 201
    _put_chunks(client, h, started.json()["id"], content, len(content))
    res = _complete(client, h, started.json()["id"])
    assert res.status_code == 200, res.text
    db.rollback()
    db.expire_all()
    stored = os.path.abspath(db.get(Attachment, uuid.UUID(res.json()["id"])).storage_path)
    root = os.path.abspath(settings.attachment_storage_root)
    assert stored.startswith(root) and ".." not in os.path.relpath(stored, root)


def test_content_is_not_inspected_documented_gap(world):
    """Documented coverage, not a policy gate: no content sniffing, MIME validation or malware scanning exists in the
    upload path today. A file named .pdf whose bytes are HTML is accepted by the ordinary path."""
    res = world["client"].post(
        "/attachments", data={"doc_type": "quotation", "doc_id": world["q"], "tag": "reference"},
        files={"file": ("looks-like.pdf", b"<html><script>1</script></html>", "application/pdf")}, headers=world["h"],
    )
    assert res.status_code == 201  # current behaviour, recorded as the documented gap


# ================================================================== 2. permission changes during assembly / finalization


def _complete_with_change_during_assembly(world, uploader_headers, doc_type, doc_id, change, monkeypatch):
    client, db = world["client"], world["db"]
    content = b"a small signed document"
    started = _start(client, uploader_headers, doc_type, doc_id, "evidence.pdf", content)
    assert started.status_code == 201, started.text
    _put_chunks(client, uploader_headers, started.json()["id"], content, len(content))
    before = _state(db)
    original = upload_core.assemble_and_validate

    def assemble_then_permissions_change(session_db, session_id, token):
        result = original(session_db, session_id, token)
        change()  # committed by ANOTHER session while this request is mid-assembly
        return result

    monkeypatch.setattr(upload_core, "assemble_and_validate", assemble_then_permissions_change)
    res = _complete(client, uploader_headers, started.json()["id"])
    return res, before, _state(db)


@known_gap("complete_upload_session authorizes ONCE up front; finalize_completion commits on the permissions as they were")
def test_deactivating_the_uploader_during_assembly_refuses_completion_with_401(world, db_session, monkeypatch):
    uploader = make_user(db_session, "site_engineer")
    headers = user_headers(world["client"], uploader)

    def deactivate():
        s = Session()
        s.execute(text("UPDATE users SET is_active = false WHERE id = :i"), {"i": str(uploader.id)})
        s.commit()
        s.close()

    res, before, after = _complete_with_change_during_assembly(world, headers, "project_stage", world["stage_id"], deactivate, monkeypatch)
    assert res.status_code == 401, (res.status_code, res.text[:160])
    assert after[1] == before[1] and after[0]["attachments"] == before[0]["attachments"]  # no row, no stored file


@known_gap("the required-role check is not repeated at finalization")
def test_removing_the_required_role_during_assembly_refuses_completion_with_403(world, db_session, monkeypatch):
    uploader = make_user(db_session, "site_engineer")
    headers = user_headers(world["client"], uploader)

    def demote():
        s = Session()
        s.execute(text("UPDATE users SET role = 'CA_TAX' WHERE id = :i"), {"i": str(uploader.id)})  # enum stores the NAME
        s.commit()
        s.close()

    res, before, after = _complete_with_change_during_assembly(world, headers, "project_stage", world["stage_id"], demote, monkeypatch)
    assert res.status_code == 403, (res.status_code, res.text[:160])
    assert after[1] == before[1] and after[0]["attachments"] == before[0]["attachments"]


@known_gap("the Amendment 60 ownership check (require_visible_document) is not repeated at finalization")
def test_removing_ownership_during_assembly_refuses_completion_with_the_concealing_404(world, db_session, monkeypatch):
    client, h = world["client"], world["h"]
    owner = make_user(db_session, "sales", name="Owner")
    other = make_user(db_session, "sales", name="Successor")
    assert client.put("/ownership/switch", json={"on": True}, headers=h).status_code == 200
    assert client.patch(f"/ownership/project/{world['pid']}", json={"owner_id": str(owner.id), "cascade": True}, headers=h).status_code == 200
    headers = user_headers(client, owner)

    def reassign():
        s = Session()
        s.execute(text("UPDATE projects SET owner_id = :o WHERE id = :p"), {"o": str(other.id), "p": world["pid"]})
        s.commit()
        s.close()

    res, before, after = _complete_with_change_during_assembly(world, headers, "quotation", world["q"], reassign, monkeypatch)
    assert res.status_code == 404, (res.status_code, res.text[:160])
    assert after[1] == before[1] and after[0]["attachments"] == before[0]["attachments"]


def test_control_a_completion_with_unchanged_permissions_commits(world, db_session, monkeypatch):
    """Guards the three tests above: with no permission change the same flow succeeds and stores exactly one file."""
    uploader = make_user(db_session, "site_engineer")
    headers = user_headers(world["client"], uploader)
    res, before, after = _complete_with_change_during_assembly(world, headers, "project_stage", world["stage_id"], lambda: None, monkeypatch)
    assert res.status_code == 200
    assert len(after[0]["attachments"]) == len(before[0]["attachments"]) + 1 and len(after[1]) == len(before[1]) + 1


@known_gap("finalization takes no lock on the uploader/project rows it authorized against, so a concurrent "
           "deactivation is not made to wait for the commit (check-then-commit race)")
def test_finalization_holds_the_permission_rows_until_its_commit_so_a_concurrent_deactivation_must_wait(world, db_session):
    """A check followed by an unlocked commit leaves a race. Finalization is held at its commit; a deactivation
    started meanwhile must BLOCK on a lock, and only apply after the Attachment is committed."""
    uploader = make_user(db_session, "site_engineer")
    headers = user_headers(world["client"], uploader)
    content = b"a small signed document"
    started = _start(world["client"], headers, "project_stage", world["stage_id"], "evidence.pdf", content)
    assert started.status_code == 201
    session_id = uuid.UUID(started.json()["id"])
    _put_chunks(world["client"], headers, session_id, content, len(content))
    setup = Session()
    try:
        token = upload_core.start_completion(setup, session_id)
        assembled = upload_core.assemble_and_validate(setup, session_id, token)
    finally:
        setup.close()

    def finalize(s):
        return upload_core.finalize_completion(s, session_id, token, assembled, s.get(User, uploader.id), None).id

    def deactivate(s):
        s.execute(text("UPDATE users SET is_active = false WHERE id = :i"), {"i": str(uploader.id)})
        s.commit()

    first = Op(finalize, gate=True).start().wait_holding_locks()
    second = Op(deactivate).start()
    try:
        wait_until_blocked(1, timeout=5)  # AssertionError here = the deactivation was NOT blocked: the gap
    finally:
        first.release().join()
        second.join()
    assert first.exc is None and second.exc is None


# ================================================================== 3. resource limits (each limit on its own)


def test_declared_size_limits_are_enforced(world):
    client, h = world["client"], world["h"]
    for size in (100 * MIB + 1, 0, -5):
        res = _start(client, h, "quotation", world["q"], "a.pdf", b"x", declared_size=size)
        assert res.status_code == 413, (size, res.status_code, res.text[:120])
    assert _start(client, h, "quotation", world["q"], "a.pdf", b"x", declared_size=100 * MIB, chunk_size=16 * MIB).status_code == 201


def test_chunk_bodies_must_match_the_expected_size_and_index(world):
    client, h = world["client"], world["h"]
    content = b"0123456789"
    sid = _start(client, h, "quotation", world["q"], "a.pdf", content, chunk_size=4).json()["id"]  # 4 + 4 + 2
    path = f"/attachments/upload-sessions/{sid}/chunks"
    for index, size in ((0, 5), (0, 3), (3, 2)):  # too big, too small, out of range
        res = client.post(f"{path}/{index}", files={"file": ("c", b"x" * size, "application/octet-stream")}, headers=h)
        assert res.status_code == 422, (index, size, res.status_code)


@known_gap("start_session() accepts any positive chunk_size, e.g. 1 byte: a 100 MB declaration becomes 104,857,600 chunks")
def test_a_chunk_size_below_the_minimum_is_refused_with_422(world):
    for chunk in (1, 63 * KIB):
        res = _start(world["client"], world["h"], "quotation", world["q"], "a.pdf", b"x",
                     declared_size=100 * MIB, chunk_size=chunk)
        assert res.status_code == 422 and "chunk_size" in res.json()["detail"], (chunk, res.status_code, res.text[:140])


@known_gap("no upper bound on chunk_size short of the declared size (each chunk body is read fully into memory)")
def test_a_chunk_size_above_the_maximum_is_refused_with_422(world):
    res = _start(world["client"], world["h"], "quotation", world["q"], "a.pdf", b"x",
                 declared_size=100 * MIB, chunk_size=16 * MIB + 1)
    assert res.status_code == 422 and "chunk_size" in res.json()["detail"], (res.status_code, res.text[:140])


def test_chunk_size_boundaries_and_tiny_single_chunk_files_are_accepted(world):
    client, h = world["client"], world["h"]
    a = _start(client, h, "quotation", world["q"], "a.pdf", b"x", declared_size=100 * MIB, chunk_size=64 * KIB)
    assert a.status_code == 201 and a.json()["total_chunks"] == 1600  # the largest legitimate chunk count
    assert _start(client, h, "quotation", world["q"], "b.pdf", b"x", declared_size=100 * MIB, chunk_size=16 * MIB).status_code == 201
    assert _start(client, h, "quotation", world["q"], "c.pdf", b"tiny", chunk_size=4).status_code == 201  # one small chunk


def _start_core(user_id, doc_id, size, chunk=None):
    """Open a session through the core function on its own DB session; returns ('ok', id) or ('refused', code, detail)."""
    s = Session()
    try:
        sess = upload_core.start_session(
            s, s.get(User, user_id), "quotation", uuid.UUID(str(doc_id)), f"f-{uuid.uuid4().hex[:6]}.pdf", size,
            _sha(b"x"), chunk or min(size, 16 * MIB),
        )
        return ("ok", sess.id)
    except upload_core.UploadProtocolError as exc:
        return ("refused", exc.status_code, exc.detail)
    finally:
        s.close()


def _open_sessions(db):
    db.rollback()
    return db.execute(text(
        "SELECT count(*), coalesce(sum(declared_size), 0) FROM attachment_upload_sessions "
        "WHERE status IN ('uploading', 'completing')")).one()


@known_gap("there is no per-user limit on open upload sessions (80 tiny sessions were all accepted)")
def test_open_sessions_per_user_are_capped_at_10_independently_of_any_byte_quota(world):
    """1-byte declarations: the byte quota can never be the reason a start is refused here."""
    outcomes = [_start_core(world["director_id"], world["q"], 1, chunk=1) for _ in range(MAX_OPEN_SESSIONS + 1)]
    assert [o[0] for o in outcomes[:MAX_OPEN_SESSIONS]] == ["ok"] * MAX_OPEN_SESSIONS
    last = outcomes[MAX_OPEN_SESSIONS]
    assert last[0] == "refused" and last[1] == 429 and "open upload sessions" in last[2], last


@known_gap("there is no per-user cap on declared bytes across open sessions")
def test_declared_bytes_per_user_are_capped_independently_of_the_session_count(world):
    """5 x 100 MiB = 500 MiB is the cap; the 6th is refused while only 5 of the 10 session slots are used."""
    outcomes = [_start_core(world["director_id"], world["q"], 100 * MIB) for _ in range(6)]
    assert [o[0] for o in outcomes[:5]] == ["ok"] * 5
    assert outcomes[5][0] == "refused" and outcomes[5][1] == 429 and "declared bytes" in outcomes[5][2], outcomes[5]
    assert _open_sessions(world["db"])[0] == 5 < MAX_OPEN_SESSIONS  # the session-count limit played no part


def _race(n, fn):
    barrier, results, lock = threading.Barrier(n), [], threading.Lock()

    def worker():
        barrier.wait()
        outcome = fn()
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    assert not any(t.is_alive() for t in threads), "a racing request never finished"
    return results


@known_gap("no limit exists to race against: all 25 concurrent starts are accepted")
def test_racing_session_starts_cannot_exceed_the_open_session_cap(world):
    results = _race(25, lambda: _start_core(world["director_id"], world["q"], 1, chunk=1))
    assert sum(1 for r in results if r[0] == "ok") == MAX_OPEN_SESSIONS, [r[0] for r in results]
    assert all(r[1] == 429 for r in results if r[0] == "refused")
    assert _open_sessions(world["db"])[0] == MAX_OPEN_SESSIONS


@known_gap("no limit exists to race against: all 12 concurrent starts are accepted")
def test_racing_session_starts_cannot_exceed_the_declared_byte_cap(world):
    results = _race(12, lambda: _start_core(world["director_id"], world["q"], 100 * MIB))
    assert sum(1 for r in results if r[0] == "ok") == MAX_OPEN_DECLARED_BYTES // (100 * MIB), [r[0] for r in results]  # exactly 5
    assert _open_sessions(world["db"])[1] <= MAX_OPEN_DECLARED_BYTES


@known_gap("no global storage cap exists")
def test_a_global_storage_cap_refuses_a_declaration_that_would_exceed_it_with_413(world, monkeypatch):
    monkeypatch.setitem(settings.__dict__, "attachment_storage_cap_bytes", 5 * MIB)  # works whether or not the field exists yet
    outcome = _start_core(world["director_id"], world["q"], 6 * MIB)
    assert outcome[0] == "refused" and outcome[1] == 413 and "storage" in outcome[2].lower(), outcome


@known_gap("no per-user limits exist, so there is no quota for abandoned-session cleanup to release")
def test_cleanup_of_abandoned_sessions_releases_the_quota(world, db_session):
    uid, q = world["director_id"], world["q"]
    assert all(_start_core(uid, q, 1, chunk=1)[0] == "ok" for _ in range(MAX_OPEN_SESSIONS))
    assert _start_core(uid, q, 1, chunk=1)[0] == "refused"  # at the cap
    db_session.execute(text("UPDATE attachment_upload_sessions SET last_activity_at = :t"),
                       {"t": datetime.now(UTC) - timedelta(hours=25)})
    db_session.commit()
    upload_core.run_cleanup(db_session)
    assert _start_core(uid, q, 1, chunk=1)[0] == "ok"  # released by cleanup


def test_abandoned_sessions_are_cleaned_up_and_active_ones_are_left_alone(world, db_session):
    client, h = world["client"], world["h"]
    content = b"0123456789"
    stale = _start(client, h, "quotation", world["q"], "stale.pdf", content, chunk_size=5).json()["id"]
    fresh = _start(client, h, "quotation", world["q"], "fresh.pdf", content, chunk_size=5).json()["id"]
    _put_chunks(client, h, stale, content[:5], 5)  # one accepted chunk on disk each
    _put_chunks(client, h, fresh, content[:5], 5)
    stale_dir = upload_core._session_temp_dir(uuid.UUID(stale))
    assert stale_dir.exists() and any(stale_dir.iterdir())
    db_session.execute(text("UPDATE attachment_upload_sessions SET last_activity_at = :t WHERE id = :i"),
                       {"t": datetime.now(UTC) - timedelta(hours=25), "i": stale})
    db_session.commit()
    upload_core.run_cleanup(db_session)
    db_session.expire_all()
    assert not stale_dir.exists()  # temp chunks deleted
    assert db_session.execute(text("SELECT count(*) FROM attachment_upload_sessions WHERE id = :i"), {"i": stale}).scalar() == 0
    assert db_session.execute(text("SELECT count(*) FROM attachment_upload_sessions WHERE id = :i"), {"i": fresh}).scalar() == 1
    assert upload_core._session_temp_dir(uuid.UUID(fresh)).exists()  # the active session was untouched
