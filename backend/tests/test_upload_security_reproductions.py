"""Reproductions of three upload-security concerns raised from SOURCE INSPECTION of an earlier head
(not demonstrated exploits): (1) the prohibited-file policy across ordinary / supersede / resumable uploads,
(2) permission changes while a resumable upload is being assembled, (3) resource limits.

Each test asserts the SAFE behaviour. Where the head does not provide it, the test is marked
`xfail(strict=True)` with the reason: the suite stays green, the gap stays on record, and the day a fix lands the
strict xfail turns red until the mark is removed. Set P5_UPLOAD_REPRO_RAW=1 to drop the marks and see the raw
failures (that is how the evidence in the PR was captured). Tests WITHOUT a mark pass because the head already
behaves safely ("not reproduced").

These are P4-era code paths exercised on the P5 head; nothing here changes their behaviour."""

import hashlib
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, text

from app.core import attachment_upload as upload_core
from app.models.attachment import Attachment
from tests.p5_concurrency import Session
from tests.p5_helpers import make_user, user_headers
from tests.test_work_orders import _director_headers, _won_quotation

RAW = bool(os.environ.get("P5_UPLOAD_REPRO_RAW"))


def known_gap(reason):
    return (lambda f: f) if RAW else pytest.mark.xfail(strict=True, reason=reason)


# ------------------------------------------------------------------ helpers


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _start(client, headers, doc_type, doc_id, filename, content, chunk_size=None, declared_size=None):
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


def _attachment_count(db_session):
    db_session.rollback()
    db_session.expire_all()
    return db_session.query(func.count()).select_from(Attachment).scalar()


@pytest.fixture()
def world(client, director_user, db_session):
    h = _director_headers(client, director_user)
    pid, q = _won_quotation(client, h)
    stages = client.get(f"/projects/{pid}/stages", headers=h).json()
    return dict(h=h, pid=pid, q=q, stage_id=stages[0]["id"], db=db_session, client=client)


# ================================================================== 1. prohibited-file policy


@pytest.mark.parametrize("name", ["evil.html", "EVIL.HTML", "x.svg", "run.exe", "a.js", "trail.html. "])
def test_ordinary_upload_refuses_prohibited_types(world, name):
    res = world["client"].post(
        "/attachments", data={"doc_type": "quotation", "doc_id": world["q"], "tag": "reference"},
        files={"file": (name, b"<script>1</script>", "text/html")}, headers=world["h"],
    )
    assert res.status_code == 400, (name, res.status_code)


def test_supersede_refuses_prohibited_types(world):
    client, h = world["client"], world["h"]
    first = client.post(
        "/attachments", data={"doc_type": "quotation", "doc_id": world["q"], "tag": "reference"},
        files={"file": ("ok.pdf", b"%PDF-1.4", "application/pdf")}, headers=h,
    ).json()
    res = client.post(
        f"/attachments/{first['id']}/supersede", data={"tag": "reference"},
        files={"file": ("evil.svg", b"<svg onload=alert(1)>", "image/svg+xml")}, headers=h,
    )
    assert res.status_code == 400


@known_gap("the resumable path never applies BLOCKED_ATTACHMENT_EXTENSIONS: start_session() takes any filename and "
           "finalize_completion() only runs _safe_filename (which strips folders, not extensions)")
@pytest.mark.parametrize("name", ["evil.html", "EVIL.HTML", "x.svg", "run.exe", "a.js"])
def test_resumable_upload_refuses_the_same_prohibited_types(world, name):
    client, h = world["client"], world["h"]
    content = b"<script>alert(1)</script>"
    started = _start(client, h, "quotation", world["q"], name, content)
    if started.status_code >= 400:  # refusing at start is fine
        return
    _put_chunks(client, h, started.json()["id"], content, len(content))
    res = _complete(client, h, started.json()["id"])
    assert res.status_code >= 400, f"{name} was accepted through the resumable path: {res.status_code}"


def test_resumable_upload_neutralises_path_traversal_in_the_filename(world):
    client, h = world["client"], world["h"]
    content = b"payload"
    started = _start(client, h, "quotation", world["q"], "../../../../escape.txt", content)
    assert started.status_code == 201
    _put_chunks(client, h, started.json()["id"], content, len(content))
    res = _complete(client, h, started.json()["id"])
    assert res.status_code == 200, res.text
    world["db"].rollback()
    world["db"].expire_all()
    stored = os.path.abspath(world["db"].get(Attachment, uuid.UUID(res.json()["id"])).storage_path)
    root = os.path.abspath(__import__("app.config", fromlist=["settings"]).settings.attachment_storage_root)
    assert stored.startswith(root) and ".." not in os.path.relpath(stored, root)


def test_content_is_not_inspected_documented_gap(world):
    """Documented coverage, not a pass/fail policy: there is no content sniffing, MIME validation or malware
    scanning anywhere in the upload path (no such code or dependency exists in app/ or requirements.txt). A file
    named .pdf whose bytes are HTML is accepted by both paths; only the extension deny-list applies."""
    client, h = world["client"], world["h"]
    res = client.post(
        "/attachments", data={"doc_type": "quotation", "doc_id": world["q"], "tag": "reference"},
        files={"file": ("looks-like.pdf", b"<html><script>1</script></html>", "application/pdf")}, headers=h,
    )
    assert res.status_code == 201  # current behaviour, recorded as the documented gap


# ================================================================== 2. permission changes during assembly


def _complete_with_change_during_assembly(world, uploader_headers, doc_type, doc_id, change, monkeypatch):
    client, db = world["client"], world["db"]
    content = b"a small signed document"
    started = _start(client, uploader_headers, doc_type, doc_id, "evidence.pdf", content)
    assert started.status_code == 201, started.text
    _put_chunks(client, uploader_headers, started.json()["id"], content, len(content))
    before = _attachment_count(db)
    original = upload_core.assemble_and_validate

    def assemble_then_permissions_change(session_db, session_id, token):
        result = original(session_db, session_id, token)
        change()  # committed by ANOTHER session while this request is mid-assembly
        return result

    monkeypatch.setattr(upload_core, "assemble_and_validate", assemble_then_permissions_change)
    res = _complete(client, uploader_headers, started.json()["id"])
    return res, before, _attachment_count(db)


@known_gap("complete_upload_session authorizes ONCE up front; finalize_completion commits with the permissions as they "
           "were at the start of the request (a deactivated uploader still gets their Attachment committed)")
def test_deactivating_the_uploader_during_assembly_refuses_completion(world, db_session, monkeypatch):
    uploader = make_user(db_session, "site_engineer")
    headers = user_headers(world["client"], uploader)

    def deactivate():
        s = Session()
        s.execute(text("UPDATE users SET is_active = false WHERE id = :i"), {"i": str(uploader.id)})
        s.commit(); s.close()

    res, before, after = _complete_with_change_during_assembly(world, headers, "project_stage", world["stage_id"], deactivate, monkeypatch)
    assert res.status_code in (401, 403, 404) and after == before, (res.status_code, res.text[:160], f"attachments before={before} after={after}")


@known_gap("the required-role check is not repeated at finalization")
def test_removing_the_required_role_during_assembly_refuses_completion(world, db_session, monkeypatch):
    uploader = make_user(db_session, "site_engineer")
    headers = user_headers(world["client"], uploader)

    def demote():
        s = Session()
        s.execute(text("UPDATE users SET role = 'CA_TAX' WHERE id = :i"), {"i": str(uploader.id)})
        s.commit(); s.close()

    res, before, after = _complete_with_change_during_assembly(world, headers, "project_stage", world["stage_id"], demote, monkeypatch)
    assert res.status_code in (401, 403, 404) and after == before, (res.status_code, res.text[:160], f"attachments before={before} after={after}")


@known_gap("the Amendment 60 ownership check (require_visible_document) is not repeated at finalization")
def test_removing_ownership_during_assembly_refuses_completion(world, db_session, monkeypatch):
    client, h = world["client"], world["h"]
    owner = make_user(db_session, "sales", name="Owner")
    other = make_user(db_session, "sales", name="Successor")
    assert client.put("/ownership/switch", json={"on": True}, headers=h).status_code == 200
    assert client.patch(f"/ownership/project/{world['pid']}", json={"owner_id": str(owner.id), "cascade": True}, headers=h).status_code == 200
    headers = user_headers(client, owner)

    def reassign():
        s = Session()
        s.execute(text("UPDATE projects SET owner_id = :o WHERE id = :p"), {"o": str(other.id), "p": world["pid"]})
        s.commit(); s.close()

    res, before, after = _complete_with_change_during_assembly(world, headers, "quotation", world["q"], reassign, monkeypatch)
    assert res.status_code in (401, 403, 404) and after == before, (res.status_code, res.text[:160], f"attachments before={before} after={after}")


def test_control_a_completion_with_unchanged_permissions_commits(world, db_session, monkeypatch):
    """Guards the three tests above: without a permission change the same flow succeeds, so their failures are
    caused by the change, not by the harness."""
    uploader = make_user(db_session, "site_engineer")
    headers = user_headers(world["client"], uploader)
    res, before, after = _complete_with_change_during_assembly(world, headers, "project_stage", world["stage_id"], lambda: None, monkeypatch)
    assert res.status_code == 200 and after == before + 1


# ================================================================== 3. resource limits


def test_declared_size_limits_are_enforced(world):
    client, h = world["client"], world["h"]
    assert _start(client, h, "quotation", world["q"], "a.pdf", b"x", declared_size=100 * 1024 * 1024 + 1).status_code == 413
    assert _start(client, h, "quotation", world["q"], "a.pdf", b"x", declared_size=0).status_code == 413
    assert _start(client, h, "quotation", world["q"], "a.pdf", b"x", declared_size=-5).status_code == 413
    ok = _start(client, h, "quotation", world["q"], "a.pdf", b"x", declared_size=100 * 1024 * 1024, chunk_size=100 * 1024 * 1024)
    assert ok.status_code == 201  # exactly the documented 100 MB maximum is allowed (one chunk)


def test_chunk_bodies_must_match_the_expected_size_and_index(world):
    client, h = world["client"], world["h"]
    content = b"0123456789"
    sid = _start(client, h, "quotation", world["q"], "a.pdf", content, chunk_size=4).json()["id"]  # 4 + 4 + 2
    path = f"/attachments/upload-sessions/{sid}/chunks"
    assert client.post(f"{path}/0", files={"file": ("c", b"x" * 5, "application/octet-stream")}, headers=h).status_code == 422  # too big
    assert client.post(f"{path}/0", files={"file": ("c", b"x" * 3, "application/octet-stream")}, headers=h).status_code == 422  # too small
    assert client.post(f"{path}/3", files={"file": ("c", b"x" * 2, "application/octet-stream")}, headers=h).status_code == 422  # out of range
    assert client.post(f"{path}/-1", files={"file": ("c", b"x" * 4, "application/octet-stream")}, headers=h).status_code in (404, 405, 422)


@known_gap("start_session() accepts any positive chunk_size, so declared_size=100 MB with chunk_size=1 creates a "
           "session with 104,857,600 chunks; there is no cap on total_chunks")
def test_an_absurd_chunk_count_is_refused(world):
    res = _start(world["client"], world["h"], "quotation", world["q"], "a.pdf", b"x",
                 declared_size=100 * 1024 * 1024, chunk_size=1)
    assert res.status_code in (413, 422), f"{res.status_code}: total_chunks={res.json().get('total_chunks')}"


@known_gap("there is no per-user (or per-document) limit on open upload sessions")
def test_open_upload_sessions_per_user_are_capped(world):
    client, h = world["client"], world["h"]
    refused = False
    for i in range(80):
        res = _start(client, h, "quotation", world["q"], f"s{i}.pdf", b"x")
        if res.status_code >= 400:
            refused = True
            break
    assert refused, "80 simultaneous sessions for one user were all accepted"


@known_gap("no storage quota exists: declared bytes across a user's open sessions are not bounded (30 x 100 MB declared)")
def test_total_declared_bytes_across_open_sessions_are_bounded(world):
    client, h = world["client"], world["h"]
    refused = False
    for i in range(30):
        res = _start(client, h, "quotation", world["q"], f"big{i}.pdf", b"x",
                     declared_size=100 * 1024 * 1024, chunk_size=100 * 1024 * 1024)
        if res.status_code >= 400:
            refused = True
            break
    assert refused, "3 GB of declared uploads for one user were all accepted"


def test_abandoned_sessions_are_cleaned_up_and_active_ones_are_left_alone(world, db_session):
    client, h = world["client"], world["h"]
    content = b"0123456789"
    stale = _start(client, h, "quotation", world["q"], "stale.pdf", content, chunk_size=5).json()["id"]
    fresh = _start(client, h, "quotation", world["q"], "fresh.pdf", content, chunk_size=5).json()["id"]
    _put_chunks(client, h, stale, content[:5], 5)  # one accepted chunk on disk
    _put_chunks(client, h, fresh, content[:5], 5)
    stale_dir = upload_core._session_temp_dir(uuid.UUID(stale))
    assert stale_dir.exists() and any(stale_dir.iterdir())
    db_session.execute(text("UPDATE attachment_upload_sessions SET last_activity_at = :t WHERE id = :i"),
                       {"t": datetime.now(UTC) - timedelta(hours=25), "i": stale})
    db_session.commit()

    result = upload_core.run_cleanup(db_session)
    db_session.expire_all()
    assert not stale_dir.exists()  # temp chunks deleted
    assert db_session.execute(text("SELECT count(*) FROM attachment_upload_sessions WHERE id = :i"), {"i": stale}).scalar() == 0
    assert db_session.execute(text("SELECT count(*) FROM attachment_upload_sessions WHERE id = :i"), {"i": fresh}).scalar() == 1
    assert upload_core._session_temp_dir(uuid.UUID(fresh)).exists()  # the active session was not touched
    assert result is not None
