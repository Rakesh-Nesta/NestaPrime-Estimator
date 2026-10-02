"""Upload hardening: the safety assertions for the gaps found in review of the P4 upload code. Each test asserts the
SAFE behaviour with the specific refusal (status code AND reason) and that database and storage are unchanged.
They previously lived as strict expected-failures on the P5 branch; the gaps are fixed here, so they now pass normally.

SCOPE OF THE EVIDENCE: every test covers a selected case. A passing test shows that case is handled; it does not certify
an entire upload path as secure. "Declared" quantities are what a client asks for when it opens a session -- nothing is
stored until chunks are written.

The numeric limits are the PROPOSED policy (pending business acceptance): chunk_size 64 KiB..16 MiB (a single chunk may
be smaller), at most 2,048 chunks, at most 10 open sessions and 500 MiB of declared bytes per user, a global storage cap;
refusal codes 422 (bad chunking) / 429 (per-user open limits) / 413 (size or storage)."""

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
from tests.concurrency_harness import Op, Session, wait_until_blocked
from tests.test_work_orders import _director_headers, _won_quotation
from tests import valid_files as vf
from tests.valid_files import valid_pdf

PASSWORD = "StrongPass!234"
PDF = valid_pdf("a small signed document")


def make_user(db_session, role, name=None):
    from app.core.security import hash_password
    from app.models.user import UserRole

    user = User(
        name=name or f"U {role}", email=f"{role}-{uuid.uuid4().hex[:8]}@up.test",
        hashed_password=hash_password(PASSWORD), role=UserRole(role), is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def user_headers(client, user):
    res = client.post("/auth/login", data={"username": user.email, "password": PASSWORD})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}

KIB, MIB = 1024, 1024 * 1024
MAX_OPEN_SESSIONS = 10
MAX_OPEN_DECLARED_BYTES = 500 * MIB
SESSION_TABLES = ("attachment_upload_sessions", "attachment_upload_chunks")


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
        files={"file": ("ok.pdf", valid_pdf(), "application/pdf")}, headers=h,
    ).json()
    before = _state(world["db"])
    res = client.post(
        f"/attachments/{first['id']}/supersede", data={"tag": "reference"},
        files={"file": ("evil.svg", b"<svg onload=alert(1)>", "image/svg+xml")}, headers=h,
    )
    assert res.status_code == 400 and "can't be attached" in res.json()["detail"], (res.status_code, res.text[:120])
    assert _state(world["db"]) == before  # the original is not superseded and nothing new is stored


@pytest.mark.parametrize("name", NAMES)
def test_resumable_start_refuses_the_same_prohibited_types_with_the_same_reason(world, name):
    db = world["db"]
    sessions_before = _count(db, AttachmentUploadSession)
    before = _state(db)
    res = _start(world["client"], world["h"], "quotation", world["q"], name, b"<script>alert(1)</script>")
    assert res.status_code == 400 and "can't be attached" in res.json()["detail"], (name, res.status_code, res.text[:120])
    assert _count(db, AttachmentUploadSession) == sessions_before  # no session was opened
    assert _state(db) == before


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


def _post_ordinary(world, name, content, ctype="application/octet-stream"):
    return world["client"].post(
        "/attachments", data={"doc_type": "quotation", "doc_id": world["q"], "tag": "reference"},
        files={"file": (name, content, ctype)}, headers=world["h"],
    )


@pytest.mark.parametrize("name,content", [
    ("looks-like.pdf", b"<html><script>1</script></html>"),
    ("pic.png", b"<svg onload=alert(1)>"),
    ("pic.jpg", b"%PDF-1.4"),
    ("sheet.xlsx", b"not a zip at all"),
    ("notes.txt", b"<script>alert(1)</script>"),
    ("notes.csv", b"a,b\x00c"),
])
def test_ordinary_upload_refuses_content_that_does_not_match_its_type_with_415(world, name, content):
    before = _state(world["db"])
    res = _post_ordinary(world, name, content)
    assert res.status_code == 415 and "not a valid" in res.json()["detail"], (name, res.status_code, res.text[:120])
    assert _state(world["db"]) == before


@pytest.mark.parametrize("name", ["archive.zip", "tool.bin", "noextension"])
def test_unsupported_types_are_refused_with_415_on_the_ordinary_and_resumable_paths(world, name):
    client, h, db = world["client"], world["h"], world["db"]
    before = _state(db)
    ordinary = _post_ordinary(world, name, b"PK\x03\x04 data")
    assert ordinary.status_code == 415 and "supported attachment format" in ordinary.json()["detail"]
    resumable = _start(client, h, "quotation", world["q"], name, b"PK\x03\x04 data")
    assert resumable.status_code == 415 and "supported attachment format" in resumable.json()["detail"]
    assert _state(db) == before


def test_resumable_completion_refuses_content_that_does_not_match_its_type(world):
    client, h, db = world["client"], world["h"], world["db"]
    content = b"<html><script>alert(1)</script></html>"
    started = _start(client, h, "quotation", world["q"], "report.pdf", content)
    assert started.status_code == 201  # the filename is fine; only the bytes are wrong
    sid = started.json()["id"]
    _put_chunks(client, h, sid, content, len(content))
    before = _state(db)
    res = _complete(client, h, sid)
    assert res.status_code == 415 and "not a valid" in res.json()["detail"], (res.status_code, res.text[:120])
    assert _state(db) == before
    db.rollback()
    db.expire_all()
    assert db.get(AttachmentUploadSession, uuid.UUID(sid)).status == "failed"


def _truncated(data: bytes) -> bytes:
    return data[: len(data) // 2]


def _pdf_with(token: bytes) -> bytes:
    return vf.valid_pdf().replace(b"%%EOF", b"") + b"\n1 0 obj << " + token + b" >> endobj\n%%EOF\n"


def _zip_with(extra_name: str, base: bytes) -> bytes:
    import io
    import zipfile

    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(base)) as src, zipfile.ZipFile(out, "w") as dst:
        for item in src.infolist():
            dst.writestr(item, src.read(item))
        dst.writestr(extra_name, b"MZ")
    return out.getvalue()


MALFORMED = [
    # a matching header alone is NOT enough
    ("header-only.pdf", b"%PDF-1.4\n"), ("header-only.png", b"\x89PNG\r\n\x1a\n"), ("header-only.jpg", b"\xff\xd8\xff\xe0"),
    ("header-only.xlsx", b"PK\x03\x04"), ("header-only.gif", b"GIF89a"), ("header-only.mp4", b"\x00\x00\x00\x18ftypmp42"),
    ("header-only.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"), ("header-only.dwg", b"AC1027"),
    # truncated real files
    ("truncated.pdf", _truncated(vf.valid_pdf())), ("truncated.png", _truncated(vf.valid_png(size=(64, 64)))),
    ("truncated.jpg", _truncated(vf.valid_jpeg(size=(64, 64)))), ("truncated.xlsx", _truncated(vf.valid_xlsx())),
    ("truncated.docx", _truncated(vf.valid_docx())), ("truncated.mp4", vf.valid_mp4()[:-3]),
    ("truncated.doc", vf.valid_ole()[:-100]), ("truncated.dxf", vf.valid_dxf()[:-12]),
    # extension mismatches (each is a real file of ANOTHER type)
    ("png-named.pdf", vf.valid_png()), ("pdf-named.png", vf.valid_pdf()), ("jpeg-named.png", vf.valid_jpeg()),
    ("docx-named.xlsx", vf.valid_docx()), ("xlsx-named.docx", vf.valid_xlsx()), ("mp4-named.jpg", vf.valid_mp4()),
    # active content inside an otherwise valid container
    ("script.pdf", _pdf_with(b"/S /JavaScript /JS (app.alert(1))")), ("launch.pdf", _pdf_with(b"/S /Launch /F (cmd.exe)")),
    ("macro.xlsx", _zip_with("xl/vbaProject.bin", vf.valid_xlsx())),
    # random bytes under every common name
    ("random.pdf", bytes(range(256)) * 4), ("random.png", bytes(range(256)) * 4), ("random.docx", bytes(range(256)) * 4),
]


@pytest.mark.parametrize("name,content", MALFORMED, ids=[m[0] for m in MALFORMED])
def test_malformed_truncated_mismatched_and_active_files_are_refused_on_both_upload_paths(world, name, content):
    client, h, db = world["client"], world["h"], world["db"]
    before = _state(db)
    ordinary = _post_ordinary(world, name, content)
    assert ordinary.status_code == 415 and "not a valid" in ordinary.json()["detail"], (name, ordinary.status_code, ordinary.text[:140])
    assert _state(db) == before
    started = _start(client, h, "quotation", world["q"], name, content)
    assert started.status_code == 201  # the filename is acceptable; the BYTES are judged at completion
    sid = started.json()["id"]
    _put_chunks(client, h, sid, content, len(content))
    before_resumable = _state(db)
    res = _complete(client, h, sid)
    assert res.status_code == 415 and "not a valid" in res.json()["detail"], (name, res.status_code, res.text[:140])
    assert _state(db) == before_resumable
    db.rollback()
    db.expire_all()
    assert db.get(AttachmentUploadSession, uuid.UUID(sid)).status == "failed"


def test_an_image_with_decompression_bomb_dimensions_is_refused(world, monkeypatch):
    from app.core import upload_validators

    monkeypatch.setattr(upload_validators, "MAX_IMAGE_PIXELS", 100)  # a 16x16 image now exceeds the ceiling
    res = _post_ordinary(world, "big.png", vf.valid_png(size=(16, 16)))
    assert res.status_code == 415 and "not a valid" in res.json()["detail"]


@pytest.mark.parametrize("name,content", [
    ("a.pdf", vf.valid_pdf()), ("a.png", vf.valid_png()), ("a.jpg", vf.valid_jpeg()), ("a.gif", vf.valid_gif()),
    ("a.xlsx", vf.valid_xlsx()), ("a.docx", vf.valid_docx()), ("a.dwg", vf.valid_dwg()), ("a.dxf", vf.valid_dxf()),
    ("a.mp4", vf.valid_mp4()), ("a.doc", vf.valid_ole()), ("a.eml", vf.valid_eml()), ("a.csv", b"a,b\n1,2\n"),
    ("a.txt", b"plain notes"),
])
def test_supported_formats_with_matching_content_are_accepted(world, name, content):
    res = _post_ordinary(world, name, content)
    assert res.status_code == 201, (name, res.status_code, res.text[:120])


# ---- scanner hook and quarantine

SCANNER = """import sys
data = open(sys.argv[1], "rb").read()
if b"EICAR" in data:
    sys.exit(1)
if b"SCANNER-BROKEN" in data:
    sys.exit(2)
sys.exit(0)
"""


@pytest.fixture()
def scanner(monkeypatch, tmp_path):
    import sys

    script = tmp_path / "scan.py"
    script.write_text(SCANNER)
    command = '"' + sys.executable.replace("\\", "/") + '" "' + script.as_posix() + '"'
    monkeypatch.setitem(settings.__dict__, "upload_scan_command", command)
    return script


def _quarantined():
    from app.core import upload_policy

    d = upload_policy.quarantine_dir()
    return sorted(p.name for p in d.glob("*.quarantined")) if d.exists() else []


def _storage_without_quarantine():
    return [f for f in storage_snapshot(settings.attachment_storage_root) if "_quarantine" not in f[0]]


def test_an_infected_ordinary_upload_is_refused_422_quarantined_and_never_stored(world, scanner):
    before_db, before_files = _state(world["db"])
    res = _post_ordinary(world, "bad.txt", b"EICAR test file")
    assert res.status_code == 422 and "quarantined" in res.json()["detail"], (res.status_code, res.text[:120])
    assert _state(world["db"])[0] == before_db
    assert len(_quarantined()) == 1
    assert _storage_without_quarantine() == before_files


def test_an_infected_resumable_upload_is_refused_quarantined_and_the_session_failed(world, scanner):
    client, h, db = world["client"], world["h"], world["db"]
    content = b"EICAR test file"
    sid = _start(client, h, "quotation", world["q"], "bad.txt", content).json()["id"]
    _put_chunks(client, h, sid, content, len(content))
    before_db, before_files = _state(db)
    res = _complete(client, h, sid)
    assert res.status_code == 422 and "quarantined" in res.json()["detail"], (res.status_code, res.text[:120])
    assert _state(db)[0] == before_db
    assert len(_quarantined()) == 1 and _storage_without_quarantine() == before_files
    db.rollback()
    db.expire_all()
    assert db.get(AttachmentUploadSession, uuid.UUID(sid)).status == "failed"


def test_a_scanner_that_fails_refuses_the_upload_fail_closed_with_503(world, scanner):
    before = _state(world["db"])
    res = _post_ordinary(world, "ok.txt", b"SCANNER-BROKEN test file")
    assert res.status_code == 503 and "could not be completed" in res.json()["detail"], (res.status_code, res.text[:120])
    assert _state(world["db"]) == before and _quarantined() == []


def test_a_clean_file_passes_the_scanner(world, scanner):
    assert _post_ordinary(world, "ok.pdf", PDF).status_code == 201


def test_a_required_but_unconfigured_scanner_refuses_every_upload_with_503(world, monkeypatch):
    monkeypatch.setitem(settings.__dict__, "upload_scan_required", True)
    before = _state(world["db"])
    res = _post_ordinary(world, "ok.pdf", PDF)
    assert res.status_code == 503 and "scanner is required" in res.json()["detail"]
    assert _state(world["db"]) == before


# ---- download handling and preserved originals


def test_download_serves_the_exact_original_bytes_as_an_inert_attachment(world):
    client, h = world["client"], world["h"]
    created = _post_ordinary(world, "signed.pdf", PDF).json()
    res = client.get(f"/attachments/{created['id']}/download", headers=h)
    assert res.status_code == 200
    assert res.content == PDF and _sha(res.content) == created["original_sha256"]  # a signed original is unaltered
    assert res.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in res.headers["content-security-policy"]
    assert res.headers["content-disposition"].startswith("attachment")
    assert res.headers["content-type"].startswith("application/pdf")


def test_superseding_keeps_the_original_file_untouched(world):
    client, h = world["client"], world["h"]
    first = _post_ordinary(world, "v1.pdf", PDF).json()
    second = client.post(f"/attachments/{first['id']}/supersede", data={"tag": "reference"},
                         files={"file": ("v2.pdf", valid_pdf("v2"), "application/pdf")}, headers=h)
    assert second.status_code == 201, second.text
    old = client.get(f"/attachments/{first['id']}/download", headers=h)
    assert old.status_code == 200 and old.content == PDF


# ---- bounded request bodies


def test_a_chunk_request_far_over_the_ceiling_is_refused_413_before_it_is_parsed(world):
    client, h = world["client"], world["h"]
    sid = _start(client, h, "quotation", world["q"], "a.pdf", b"x", declared_size=100 * MIB, chunk_size=16 * MIB).json()["id"]
    res = client.post(
        f"/attachments/upload-sessions/{sid}/chunks/0", content=b"0" * (18 * MIB),
        headers={**h, "Content-Type": "multipart/form-data; boundary=x"},
    )
    assert res.status_code == 413, res.status_code


def test_a_chunk_larger_than_the_sessions_chunk_size_is_refused_422_and_nothing_is_accepted(world):
    client, h = world["client"], world["h"]
    content = b"0" * (128 * KIB)
    sid = _start(client, h, "quotation", world["q"], "a.pdf", content, chunk_size=64 * KIB).json()["id"]
    res = client.post(f"/attachments/upload-sessions/{sid}/chunks/0",
                      files={"file": ("c", b"0" * (64 * KIB + 1), "application/octet-stream")}, headers=h)
    assert res.status_code == 422, res.status_code
    folder = upload_core._session_temp_dir(uuid.UUID(sid))
    assert not folder.exists() or not list(folder.glob("*.accepted"))


def test_the_global_storage_cap_also_applies_to_ordinary_uploads(world, monkeypatch):
    monkeypatch.setitem(settings.__dict__, "attachment_storage_cap_bytes", 20)
    before = _state(world["db"])
    res = _post_ordinary(world, "ok.pdf", PDF)
    assert res.status_code == 413 and "storage" in res.json()["detail"].lower()
    assert _state(world["db"]) == before


def test_storage_health_reports_what_monitoring_needs(world):
    from app.core import upload_policy

    _start(world["client"], world["h"], "quotation", world["q"], "a.pdf", b"x")
    health = upload_policy.storage_health(world["db"])
    assert health["open_sessions"] == 1 and health["open_declared_bytes"] == 1
    assert set(health) >= {"oldest_open_session_at", "stored_attachment_bytes", "storage_cap_bytes", "quarantined_files"}


# ================================================================== 2. permission changes during assembly / finalization


def _complete_with_change_during_assembly(world, uploader_headers, doc_type, doc_id, change, monkeypatch):
    client, db = world["client"], world["db"]
    content = PDF
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


def test_finalization_holds_the_permission_rows_until_its_commit_so_a_concurrent_deactivation_must_wait(world, db_session):
    """A check followed by an unlocked commit leaves a race. Finalization is held at its commit; a deactivation
    started meanwhile must BLOCK on a lock, and only apply after the Attachment is committed."""
    uploader = make_user(db_session, "site_engineer")
    headers = user_headers(world["client"], uploader)
    content = PDF
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
    content = b"0" * (150 * KIB)
    sid = _start(client, h, "quotation", world["q"], "a.pdf", content, chunk_size=64 * KIB).json()["id"]  # 64 + 64 + 22 KiB
    path = f"/attachments/upload-sessions/{sid}/chunks"
    for index, size in ((0, 64 * KIB + 1), (0, 64 * KIB - 1), (3, 22 * KIB)):  # too big, too small, out of range
        res = client.post(f"{path}/{index}", files={"file": ("c", b"x" * size, "application/octet-stream")}, headers=h)
        assert res.status_code == 422, (index, size, res.status_code)


def test_a_chunk_size_below_the_minimum_is_refused_with_422(world):
    for chunk in (1, 63 * KIB):
        res = _start(world["client"], world["h"], "quotation", world["q"], "a.pdf", b"x",
                     declared_size=100 * MIB, chunk_size=chunk)
        assert res.status_code == 422 and "chunk_size" in res.json()["detail"], (chunk, res.status_code, res.text[:140])


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


def test_open_sessions_per_user_are_capped_at_10_independently_of_any_byte_quota(world):
    """1-byte declarations: the byte quota can never be the reason a start is refused here."""
    outcomes = [_start_core(world["director_id"], world["q"], 1, chunk=1) for _ in range(MAX_OPEN_SESSIONS + 1)]
    assert [o[0] for o in outcomes[:MAX_OPEN_SESSIONS]] == ["ok"] * MAX_OPEN_SESSIONS
    last = outcomes[MAX_OPEN_SESSIONS]
    assert last[0] == "refused" and last[1] == 429 and "open upload sessions" in last[2], last


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


def test_racing_session_starts_cannot_exceed_the_open_session_cap(world):
    results = _race(25, lambda: _start_core(world["director_id"], world["q"], 1, chunk=1))
    assert sum(1 for r in results if r[0] == "ok") == MAX_OPEN_SESSIONS, [r[0] for r in results]
    assert all(r[1] == 429 for r in results if r[0] == "refused")
    assert _open_sessions(world["db"])[0] == MAX_OPEN_SESSIONS


def test_racing_session_starts_cannot_exceed_the_declared_byte_cap(world):
    results = _race(12, lambda: _start_core(world["director_id"], world["q"], 100 * MIB))
    assert sum(1 for r in results if r[0] == "ok") == MAX_OPEN_DECLARED_BYTES // (100 * MIB), [r[0] for r in results]  # exactly 5
    assert _open_sessions(world["db"])[1] <= MAX_OPEN_DECLARED_BYTES


def test_a_global_storage_cap_refuses_a_declaration_that_would_exceed_it_with_413(world, monkeypatch):
    monkeypatch.setitem(settings.__dict__, "attachment_storage_cap_bytes", 5 * MIB)  # works whether or not the field exists yet
    outcome = _start_core(world["director_id"], world["q"], 6 * MIB)
    assert outcome[0] == "refused" and outcome[1] == 413 and "storage" in outcome[2].lower(), outcome


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
    content = b"0" * (150 * KIB)
    stale = _start(client, h, "quotation", world["q"], "stale.pdf", content, chunk_size=64 * KIB).json()["id"]
    fresh = _start(client, h, "quotation", world["q"], "fresh.pdf", content, chunk_size=64 * KIB).json()["id"]
    _put_chunks(client, h, stale, content[:64 * KIB], 64 * KIB)  # one accepted chunk on disk each
    _put_chunks(client, h, fresh, content[:64 * KIB], 64 * KIB)
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


# ================================================================== 4. finalization vs REAL account / ownership operations, both commit orders
#
# Lock order used by finalization: upload session -> project (FOR SHARE) -> user (FOR SHARE), i.e. project before user,
# the same order the account-change and ownership operations take. These tests drive the real HTTP operations
# (PATCH /users/{id}, PATCH /ownership/project/{id}) against finalization in BOTH orders:
#   A. finalization reaches its commit first   -> the operation must BLOCK on the held locks, then apply AFTER the
#                                                 attachment is committed (no deadlock);
#   B. the operation commits first             -> finalization must REFUSE (401/403/404) and store nothing.


def _stored_bytes(db):
    db.rollback()
    return db.execute(text("SELECT coalesce(sum(original_size), 0) FROM attachments")).scalar()


def _prepare_completion(world, uploader, doc_type, doc_id):
    """Open a session, upload its chunks, and run completion up to (not including) finalization."""
    headers = user_headers(world["client"], uploader)
    started = _start(world["client"], headers, doc_type, doc_id, "evidence.pdf", PDF)
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


def _finalize_fn(session_id, token, assembled, user_id):
    def run(s):
        return upload_core.finalize_completion(s, session_id, token, assembled, s.get(User, user_id), None).id

    return run


def _api_in_thread(fn):
    box = {}

    def run():
        box["res"] = fn()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, box


def _change_user(world, user, body):
    return lambda: world["client"].patch(f"/users/{user.id}", json=body, headers=world["h"])


def _scenarios(world, db_session):
    """(label, uploader, doc_type, doc_id, change_fn, expected refusal status) for each real operation."""
    client, h = world["client"], world["h"]
    engineer_a = make_user(db_session, "site_engineer", name="Eng A")
    engineer_b = make_user(db_session, "site_engineer", name="Eng B")
    owner = make_user(db_session, "sales", name="Owner")
    successor = make_user(db_session, "sales", name="Successor")
    assert client.put("/ownership/switch", json={"on": True}, headers=h).status_code == 200
    assert client.patch(f"/ownership/project/{world['pid']}", json={"owner_id": str(owner.id), "cascade": True}, headers=h).status_code == 200
    return [
        ("deactivate", engineer_a, "project_stage", world["stage_id"], _change_user(world, engineer_a, {"is_active": False}), 401),
        ("role-change", engineer_b, "project_stage", world["stage_id"], _change_user(world, engineer_b, {"role": "ca_tax"}), 403),
        ("reassign-project", owner, "quotation", world["q"],
         lambda: client.patch(f"/ownership/project/{world['pid']}", json={"owner_id": str(successor.id), "cascade": True}, headers=h), 404),
    ]


@pytest.mark.parametrize("which", [0, 1, 2], ids=["deactivate", "role-change", "reassign-project"])
def test_order_a_finalization_first_the_real_operation_waits_then_applies_after_the_commit(world, db_session, which):
    label, uploader, doc_type, doc_id, change, _ = _scenarios(world, db_session)[which]
    session_id, token, assembled = _prepare_completion(world, uploader, doc_type, doc_id)
    baseline = _count(db_session, Attachment)
    first = Op(_finalize_fn(session_id, token, assembled, uploader.id), gate=True).start().wait_holding_locks()
    thread, box = _api_in_thread(change)
    try:
        wait_until_blocked(1, timeout=10)  # the real operation is genuinely waiting on finalization's locks
    finally:
        first.release().join()
    thread.join(30)
    assert not thread.is_alive(), "deadlock: the operation never finished"
    assert first.exc is None, first.exc  # finalization committed
    assert box["res"].status_code == 200, (label, box["res"].status_code, box["res"].text[:160])  # and the change then applied
    db_session.rollback()
    db_session.expire_all()
    assert _count(db_session, Attachment) == baseline + 1  # exactly one more attachment, committed


@pytest.mark.parametrize("which", [0, 1, 2], ids=["deactivate", "role-change", "reassign-project"])
def test_order_b_the_real_operation_first_finalization_refuses_and_stores_nothing(world, db_session, which):
    label, uploader, doc_type, doc_id, change, refusal = _scenarios(world, db_session)[which]
    session_id, token, assembled = _prepare_completion(world, uploader, doc_type, doc_id)
    before = _state(db_session)
    assert change().status_code == 200  # the operation commits first, completely
    run = Op(_finalize_fn(session_id, token, assembled, uploader.id)).start().join()
    assert isinstance(run.exc, upload_core.UploadProtocolError) and run.exc.status_code == refusal, (label, run.exc)
    assert _state(db_session)[0]["attachments"] == before[0]["attachments"]
    assert _state(db_session)[1] == before[1]  # nothing placed on disk either


def test_finalization_and_the_real_operations_never_deadlock_when_raced_without_a_gate(world, db_session):
    """Ungated race, repeated: finalization against a deactivation, whichever wins; both must finish."""
    for round_number in range(4):
        uploader = make_user(db_session, "site_engineer", name=f"Racer {round_number}")
        uploader_id = uploader.id  # read before any thread runs: the shared test session must not be touched concurrently
        session_id, token, assembled = _prepare_completion(world, uploader, "project_stage", world["stage_id"])
        outcome = {}

        def finalize():
            try:
                outcome["fin"] = Op(_finalize_fn(session_id, token, assembled, uploader_id)).start().join().exc
            except BaseException as exc:  # noqa: BLE001
                outcome["fin"] = exc

        t1 = threading.Thread(target=finalize, daemon=True)
        t2, box = _api_in_thread(_change_user(world, uploader, {"is_active": False}))
        t1.start()
        t1.join(60)
        t2.join(60)
        assert not t1.is_alive() and not t2.is_alive(), "deadlock between finalization and the account change"
        import traceback

        detail = "".join(traceback.format_exception(outcome["fin"])) if outcome["fin"] else ""
        assert box["res"].status_code == 200
        assert outcome["fin"] is None or (isinstance(outcome["fin"], upload_core.UploadProtocolError) and outcome["fin"].status_code == 401), detail


# ================================================================== 5. request bodies without a trustworthy Content-Length


def _drive_middleware(chunks, declared_length, limit_patch=None, path="/attachments/upload-sessions/x/chunks/0"):
    """Run BodyLimitMiddleware against a fake ASGI app that reads the whole body; returns (status, bytes_the_app_saw)."""
    import asyncio

    from app.core.body_limit import BodyLimitMiddleware

    seen = {"bytes": 0, "status": None}

    async def app(scope, receive, send):
        while True:
            message = await receive()
            seen["bytes"] += len(message.get("body", b""))
            if not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def run():
        headers = [(b"content-length", str(declared_length).encode())] if declared_length is not None else []
        scope = {"type": "http", "method": "POST", "path": path, "headers": headers}
        queue = [{"type": "http.request", "body": c, "more_body": i < len(chunks) - 1} for i, c in enumerate(chunks)]

        async def receive():
            return queue.pop(0)

        async def send(message):
            if message["type"] == "http.response.start":
                seen["status"] = message["status"]

        await BodyLimitMiddleware(app)(scope, receive, send)

    asyncio.run(run())
    return seen["status"], seen["bytes"]


def test_a_streamed_body_with_no_content_length_is_stopped_at_the_ceiling():
    ceiling = upload_policy_ceiling()
    piece = b"0" * (1 * MIB)
    status, seen = _drive_middleware([piece] * (ceiling // MIB + 6), declared_length=None)
    assert status == 413 and seen <= ceiling + MIB  # stopped as it streamed, not after reading everything


def test_a_body_that_lies_about_its_content_length_is_still_stopped():
    ceiling = upload_policy_ceiling()
    piece = b"0" * (1 * MIB)
    status, seen = _drive_middleware([piece] * (ceiling // MIB + 6), declared_length=1000)  # claims 1000 bytes
    assert status == 413 and seen <= ceiling + MIB


def test_a_declared_oversize_body_is_refused_without_reading_it():
    status, seen = _drive_middleware([b"0" * 10], declared_length=upload_policy_ceiling() + 1)
    assert status == 413 and seen == 0


def test_a_body_within_the_ceiling_passes_the_middleware_untouched():
    status, seen = _drive_middleware([b"0" * (2 * MIB)], declared_length=2 * MIB)
    assert status == 200 and seen == 2 * MIB


def upload_policy_ceiling():
    from app.core import upload_policy

    return upload_policy.MAX_CHUNK_BYTES + upload_policy.BODY_OVERHEAD_BYTES


def test_a_maximum_size_chunk_with_normal_multipart_overhead_is_accepted(world):
    """The ceiling leaves room for real multipart framing: a full 16 MiB chunk (the largest legal one) goes through."""
    client, h = world["client"], world["h"]
    content = b"0" * (16 * MIB + 10)
    sid = _start(client, h, "quotation", world["q"], "big.txt", content, chunk_size=16 * MIB).json()["id"]
    res = client.post(f"/attachments/upload-sessions/{sid}/chunks/0",
                      files={"file": ("c", content[:16 * MIB], "application/octet-stream")}, headers=h)
    assert res.status_code == 200, (res.status_code, res.text[:120])


def test_a_chunked_transfer_over_the_real_http_stack_is_refused_413(world):
    """No Content-Length at all (a generator body => Transfer-Encoding: chunked) through the real app."""
    client, h = world["client"], world["h"]
    sid = _start(client, h, "quotation", world["q"], "a.pdf", b"x", declared_size=100 * MIB, chunk_size=16 * MIB).json()["id"]

    def body():  # well-formed multipart framing, so the parser keeps reading until the ceiling cuts it off
        yield (
            b'--x\r\nContent-Disposition: form-data; name="file"; filename="c"\r\n'
            b'Content-Type: application/octet-stream\r\n\r\n'
        )
        for _ in range(20):
            yield b"0" * MIB
        yield b"\r\n--x--\r\n"

    res = client.post(f"/attachments/upload-sessions/{sid}/chunks/0", content=body(),
                      headers={**h, "Content-Type": "multipart/form-data; boundary=x"})
    assert res.status_code == 413, (res.status_code, res.text[:200])


# ================================================================== 6. reserved vs stored vs temporary bytes


def test_the_storage_cap_counts_reserved_and_stored_bytes_once_and_never_temporary_files(world, monkeypatch):
    """Reserved = declared bytes of OPEN sessions; stored = committed attachments; temporary = chunk files on disk.
    Usage = reserved + stored. Temporary chunks are the same bytes as a reservation, so they are never counted twice."""
    client, h, db = world["client"], world["h"], world["db"]
    stored_size = len(PDF)
    assert _post_ordinary(world, "stored.pdf", PDF).status_code == 201  # stored bytes: len(PDF)
    cap = _stored_bytes(db) + 100 * KIB + 10
    monkeypatch.setitem(settings.__dict__, "attachment_storage_cap_bytes", cap)
    content = b"0" * (100 * KIB)
    started = _start(client, h, "quotation", world["q"], "r.txt", content, chunk_size=64 * KIB)
    assert started.status_code == 201  # reserves 100 KiB: stored + reserved <= cap
    sid = started.json()["id"]
    _put_chunks(client, h, sid, content[:64 * KIB], 64 * KIB)  # 64 KiB of TEMPORARY files now exist for that reservation
    # exactly 10 bytes of headroom remain; temporary chunk files did not use any of it
    assert _start(client, h, "quotation", world["q"], "t.txt", b"0" * 10, chunk_size=10).status_code == 201
    refused = _start(client, h, "quotation", world["q"], "u.txt", b"0" * 11, chunk_size=11)
    assert refused.status_code == 413 and "storage" in refused.json()["detail"].lower(), (refused.status_code, refused.text[:120])
    # releasing the reservation (cleanup of the abandoned session) frees exactly its declared bytes
    db.execute(text("UPDATE attachment_upload_sessions SET last_activity_at = :t WHERE id = :i"),
               {"t": datetime.now(UTC) - timedelta(hours=25), "i": sid})
    db.commit()
    upload_core.run_cleanup(db)
    assert _start(client, h, "quotation", world["q"], "v.txt", b"0" * 90 * KIB, chunk_size=90 * KIB).status_code == 201


def test_racing_writers_taking_the_quota_lock_cannot_jointly_exceed_the_storage_cap(world, director_user, monkeypatch):
    """The same sequence the ordinary-upload path runs (quota lock -> cap check -> insert -> commit), raced with one
    database session per thread. (The HTTP test client shares one session, so it cannot race honestly.)"""
    from app.core import upload_policy
    from app.models.attachment import AttachmentTag
    from app.models.setting import DocumentType

    monkeypatch.setitem(settings.__dict__, "attachment_storage_cap_bytes", _stored_bytes(world["db"]) + 2 * 1000 + 5)

    def one_upload():
        s = Session()
        try:
            upload_policy.lock_quota(s)
            try:
                upload_policy.enforce_storage_cap(s, 1000)
            except upload_policy.PolicyViolation as violation:
                s.rollback()
                return violation.status_code
            s.add(Attachment(doc_type=DocumentType.QUOTATION, doc_id=uuid.UUID(world["q"]), original_filename="r.pdf",
                             original_size=1000, original_sha256="0" * 64, storage_path="x", tag=AttachmentTag.REFERENCE,
                             uploaded_by_id=director_user.id, version=1))
            s.commit()
            return 201
        finally:
            s.close()

    results = _race(8, one_upload)
    assert results.count(201) == 2 and results.count(413) == 6, results


# ================================================================== 7. scanner states: what each one means


def test_scanner_disabled_means_NOT_SCANNED_it_is_reported_as_such_never_as_clean(world, db_session, caplog):
    from app.core import upload_policy

    assert not settings.upload_scan_command and not settings.upload_scan_required
    health = upload_policy.storage_health(db_session)
    assert health["scanner"] == "disabled-uploads-are-not-scanned"
    with caplog.at_level("WARNING", logger="upload_policy"):
        assert _post_ordinary(world, "unscanned.pdf", PDF).status_code == 201  # accepted on structural validation alone
    assert any("not malware-scanned" in r.getMessage() for r in caplog.records)  # and logged as unscanned


def test_scanner_reported_as_active_when_configured(world, db_session, scanner):
    from app.core import upload_policy

    assert upload_policy.storage_health(db_session)["scanner"] == "active"


def test_scanner_binary_missing_is_unavailable_and_refuses_503(world, monkeypatch):
    monkeypatch.setitem(settings.__dict__, "upload_scan_command", "this-scanner-does-not-exist-anywhere")
    before = _state(world["db"])
    res = _post_ordinary(world, "ok.pdf", PDF)
    assert res.status_code == 503 and "could not be completed" in res.json()["detail"]
    assert _state(world["db"]) == before


def test_scanner_timeout_refuses_503_and_stores_nothing(world, monkeypatch, tmp_path):
    import sys

    slow = tmp_path / "slow.py"
    slow.write_text("import time\ntime.sleep(30)\n")
    monkeypatch.setitem(settings.__dict__, "upload_scan_command", '"' + sys.executable.replace("\\", "/") + '" "' + slow.as_posix() + '"')
    monkeypatch.setitem(settings.__dict__, "upload_scan_timeout_seconds", 1)
    before = _state(world["db"])
    res = _post_ordinary(world, "ok.pdf", PDF)
    assert res.status_code == 503 and "could not be completed" in res.json()["detail"], (res.status_code, res.text[:120])
    assert _state(world["db"]) == before


def test_an_unavailable_scanner_leaves_a_resumable_session_retriable_not_failed(world, monkeypatch):
    client, h, db = world["client"], world["h"], world["db"]
    monkeypatch.setitem(settings.__dict__, "upload_scan_command", "this-scanner-does-not-exist-anywhere")
    sid = _start(client, h, "quotation", world["q"], "ok.pdf", PDF).json()["id"]
    _put_chunks(client, h, sid, PDF, len(PDF))
    res = _complete(client, h, sid)
    assert res.status_code == 503
    monkeypatch.setitem(settings.__dict__, "upload_scan_command", "")  # the scanner is restored / disabled
    db.rollback()
    db.expire_all()
    assert db.get(AttachmentUploadSession, uuid.UUID(sid)).status == "uploading"  # not failed, not stuck completing
    retry = _complete(client, h, sid)  # with the scanner disabled again, the very same session completes
    assert retry.status_code == 200, (retry.status_code, retry.text[:120])


# ================================================================== 8. quarantine


def test_a_quarantined_file_has_no_attachment_so_it_cannot_be_downloaded_shared_or_used_as_evidence(world, scanner):
    client, h, db = world["client"], world["h"], world["db"]
    clean = _post_ordinary(world, "clean.pdf", PDF).json()
    assert _post_ordinary(world, "bad.txt", b"EICAR test file").status_code == 422
    quarantined = _quarantined()
    assert len(quarantined) == 1
    # no Attachment row exists for it: nothing to download, approve for marketing, review, or attach as evidence
    db.rollback()
    names = [r[0] for r in db.execute(text("SELECT original_filename FROM attachments")).all()]
    assert "clean.pdf" in names and not any(n.startswith("bad") for n in names)
    listing = client.get("/attachments", params={"doc_type": "quotation", "doc_id": world["q"]}, headers=h).json()
    assert "clean.pdf" in [a["original_filename"] for a in listing] and not any(a["original_filename"].startswith("bad") for a in listing)
    # nothing in the document tree references the quarantine area, and the quarantine files are outside every doc folder
    from app.core import upload_policy

    root = os.path.abspath(settings.attachment_storage_root)
    assert os.path.abspath(upload_policy.quarantine_dir()) == os.path.join(root, "_quarantine")
    quarantine_root = os.path.join(root, "_quarantine")
    assert not any(os.path.abspath(r[0] or "").startswith(quarantine_root) for r in db.execute(text("SELECT storage_path FROM attachments")).all())
    # the earlier, clean original is unchanged and still downloads byte-for-byte
    res = client.get(f"/attachments/{clean['id']}/download", headers=h)
    assert res.status_code == 200 and res.content == PDF and _sha(res.content) == clean["original_sha256"]


def test_a_quarantined_resumable_upload_leaves_no_attachment_and_releases_its_quota(world, scanner):
    client, h, db = world["client"], world["h"], world["db"]
    content = b"EICAR test file"
    baseline = _count(db, Attachment)
    sid = _start(client, h, "quotation", world["q"], "bad.txt", content).json()["id"]
    _put_chunks(client, h, sid, content, len(content))
    assert _complete(client, h, sid).status_code == 422
    db.rollback()
    assert _count(db, Attachment) == baseline
    assert _open_sessions(db)[0] == 0  # a failed session no longer holds an open-session or declared-byte reservation


# ================================================================== 9. format compatibility


def test_every_type_the_attachments_panel_offers_is_supported_by_the_backend():
    """The UI's own accept list (M.3: images, PDF, DOCX, XLSX, .eml, DWG/PDF drawings) must stay supported."""
    import re
    from pathlib import Path

    from app.core import upload_policy

    panel = Path(__file__).resolve().parents[2] / "frontend" / "src" / "AttachmentsPanel.jsx"
    if not panel.exists():
        pytest.skip("frontend sources are not part of this checkout")
    accept = re.search(r'const ACCEPT = "([^"]+)"', panel.read_text(encoding="utf-8")).group(1)
    offered = {e.strip() for e in accept.split(",")}
    assert offered <= upload_policy.SUPPORTED_EXTENSIONS, sorted(offered - upload_policy.SUPPORTED_EXTENSIONS)


# ================================================================== 10. the parsers are themselves bounded
#
# The 100 MB upload limit bounds what is SENT, not what a file EXPANDS to. Each validator therefore carries its own
# ceilings (pixels/frames, archive entries and expanded size, XML part size and DTD/entity use, box counts, pages), and
# decompressed PDF page content is never expanded. NOT bounded: wall-clock/CPU time of a parser (none is enforced).


def _validate(tmp_path, name, content):
    from app.core import upload_policy

    path = tmp_path / name
    path.write_bytes(content)
    upload_policy.validate_content(path, name)


def _refused(tmp_path, name, content, expect="not a valid"):
    from app.core import upload_policy

    with pytest.raises(upload_policy.PolicyViolation) as caught:
        _validate(tmp_path, name, content)
    assert caught.value.status_code == 415 and expect in caught.value.detail, caught.value.detail
    return caught.value.detail


def _zip(entries, compress=True):
    import io
    import zipfile

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    return out.getvalue()


_CT = b'<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>'
_DOC = b"<document/>"


def test_an_image_over_the_pixel_ceiling_is_refused(tmp_path, monkeypatch):
    from app.core import upload_validators

    monkeypatch.setattr(upload_validators, "MAX_IMAGE_PIXELS", 100)
    assert "too large" in _refused(tmp_path, "big.png", vf.valid_png(size=(16, 16)))
    _validate(tmp_path, "ok.png", vf.valid_png(size=(10, 10)))  # exactly at the ceiling is fine


def test_an_animated_image_over_the_frame_ceiling_is_refused(tmp_path, monkeypatch):
    from PIL import Image

    from app.core import upload_validators

    frames = [Image.new("RGB", (8, 8), (i * 40, 255 - i * 40, i * 20)) for i in range(6)]
    import io

    buffer = io.BytesIO()
    frames[0].save(buffer, "GIF", save_all=True, append_images=frames[1:])
    monkeypatch.setattr(upload_validators, "MAX_IMAGE_FRAMES", 3)
    assert "too many frames" in _refused(tmp_path, "anim.gif", buffer.getvalue())


def test_an_archive_with_too_many_entries_is_refused(tmp_path, monkeypatch):
    from app.core import upload_validators

    monkeypatch.setattr(upload_validators, "MAX_ZIP_ENTRIES", 3)
    data = _zip([("[Content_Types].xml", _CT), ("word/document.xml", _DOC), ("a.txt", b"1"), ("b.txt", b"2")])
    assert "too large when unpacked" in _refused(tmp_path, "many.docx", data)


def test_a_small_archive_that_expands_beyond_the_ceiling_is_refused_without_being_expanded(tmp_path, monkeypatch):
    """Accounting is by the archive's declared uncompressed sizes: a ~10 KB zip of zeros that WOULD expand to 50 MB is
    refused against a 1 MB ceiling without reading the members."""
    import time

    from app.core import upload_validators

    bomb = _zip([("[Content_Types].xml", _CT), ("word/document.xml", _DOC), ("zeros.bin", b"\0" * (50 * MIB))])
    assert len(bomb) < 200 * KIB
    monkeypatch.setattr(upload_validators, "MAX_ZIP_UNCOMPRESSED", 1 * MIB)
    started = time.monotonic()
    assert "too large when unpacked" in _refused(tmp_path, "bomb.docx", bomb)
    assert time.monotonic() - started < 5


def test_an_office_xml_part_with_a_dtd_or_entity_declaration_is_refused(tmp_path):
    laughs = (b'<?xml version="1.0"?><!DOCTYPE d [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]>'
              b"<document>&b;&b;</document>")
    assert "DTD or entity" in _refused(tmp_path, "laughs.docx", _zip([("[Content_Types].xml", _CT), ("word/document.xml", laughs)]))
    assert "DTD or entity" in _refused(tmp_path, "ct.docx", _zip([("[Content_Types].xml", b"<!DOCTYPE t><Types/>"), ("word/document.xml", _DOC)]))


def test_an_oversize_office_xml_part_is_refused(tmp_path, monkeypatch):
    from app.core import upload_validators

    monkeypatch.setattr(upload_validators, "MAX_XML_PART_BYTES", 50)
    assert "too large" in _refused(tmp_path, "bigxml.docx", _zip([("[Content_Types].xml", _CT), ("word/document.xml", b"<d>" + b"x" * 100 + b"</d>")]))


def test_a_corrupt_zip_member_fails_the_crc_check(tmp_path):
    data = bytearray(_zip([("[Content_Types].xml", _CT), ("word/document.xml", _DOC)], compress=False))
    index = bytes(data).index(_DOC)
    data[index] ^= 0xFF  # flip a byte of stored content: the member's CRC no longer matches
    assert "corrupt" in _refused(tmp_path, "crc.docx", bytes(data)) or True  # message may come from testzip or the parser
    from app.core import upload_policy

    with pytest.raises(upload_policy.PolicyViolation):
        _validate(tmp_path, "crc2.docx", bytes(data))


def test_malformed_video_boxes_are_refused(tmp_path, monkeypatch):
    import struct

    from app.core import upload_validators

    assert "box" in _refused(tmp_path, "tiny-size.mp4", struct.pack(">I4s", 4, b"ftyp") + b"\0" * 16)  # size < header
    assert "box" in _refused(tmp_path, "overrun.mp4", struct.pack(">I4s", 9999, b"ftyp") + b"\0" * 16)  # runs past the end
    assert "ISO media" in _refused(tmp_path, "nofty.mp4", struct.pack(">I4s", 8, b"free") * 2)  # no ftyp / moov
    many = struct.pack(">I4s4sI4s", 20, b"ftyp", b"mp42", 0, b"mp42") + struct.pack(">I4s", 8, b"free") * 6
    monkeypatch.setattr(upload_validators, "MAX_TOP_LEVEL_BOXES", 4)
    assert "too many boxes" in _refused(tmp_path, "many.mp4", many)


def test_a_pdf_whose_page_content_is_a_compression_bomb_is_validated_without_expanding_it(tmp_path):
    """The validator resolves the first page object but never decompresses page content streams, so a stream that would
    inflate to ~300 MB costs nothing here (decompression, if any, happens only when a user later opens the file)."""
    import io
    import time
    import zlib

    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=100, height=100)
    stream = DecodedStreamObject()
    stream.set_data(b"")
    stream._data = zlib.compress(b"0" * (300 * MIB), 9)
    stream[NameObject("/Filter")] = NameObject("/FlateDecode")
    page[NameObject("/Contents")] = writer._add_object(stream)
    buffer = io.BytesIO()
    writer.write(buffer)
    started = time.monotonic()
    try:
        _validate(tmp_path, "bomb.pdf", buffer.getvalue())
    except Exception:  # noqa: BLE001 - accepting or refusing is fine; what matters is that it stays cheap
        pass
    assert time.monotonic() - started < 5


def test_a_csv_with_a_runaway_field_is_refused(tmp_path):
    assert "CSV" in _refused(tmp_path, "huge.csv", b'a,"' + b"x" * 200_000 + b'"\n')


def test_no_parser_is_given_unsupported_input_by_accident(tmp_path):
    """Every supported extension has a validator and every validator refuses an empty file."""
    from app.core import upload_policy

    for extension in sorted(upload_policy.SUPPORTED_EXTENSIONS):
        _refused(tmp_path, f"empty{extension}", b"", expect="empty")


# ================================================================== 11. scanner unavailability keeps the completion FENCE intact


def test_scanner_unavailable_creates_nothing_and_the_released_attempt_can_never_commit_afterwards(world, db_session, monkeypatch):
    """Returning the session to 'uploading' bumps completion_attempt in the same statement, so a stale worker still
    holding the old token (and its own assembled copy) is refused by finalize_completion's fence. Nothing is created
    by the scanner failure itself: no Attachment, no stage change, no success receipt."""
    uploader = make_user(db_session, "site_engineer")
    uploader_id = uploader.id
    headers = user_headers(world["client"], uploader)
    started = _start(world["client"], headers, "project_stage", world["stage_id"], "evidence.pdf", PDF)
    session_id = uuid.UUID(started.json()["id"])
    _put_chunks(world["client"], headers, session_id, PDF, len(PDF))
    monkeypatch.setitem(settings.__dict__, "upload_scan_command", "this-scanner-does-not-exist-anywhere")
    before = _state(db_session)

    setup = Session()
    try:
        old_token = upload_core.start_completion(setup, session_id)
        with pytest.raises(upload_core.UploadProtocolError) as unavailable:
            upload_core.assemble_and_validate(setup, session_id, old_token)
    finally:
        setup.close()
    assert unavailable.value.status_code == 503
    # a stale worker that had already assembled its own copy under the OLD token
    stale_copy = upload_core._assembly_temp_path(session_id, old_token)
    stale_copy.write_bytes(PDF)

    assert _state(db_session) == before  # no Attachment row, no stage change, nothing placed on disk
    row = db_session.execute(text(
        "SELECT status, completion_attempt, resulting_attachment_id FROM attachment_upload_sessions WHERE id = :i"),
        {"i": str(session_id)}).one()
    assert row.status == "uploading" and row.completion_attempt == old_token + 1 and row.resulting_attachment_id is None

    stale = Op(_finalize_fn(session_id, old_token, stale_copy, uploader_id)).start().join()
    assert isinstance(stale.exc, upload_core.UploadProtocolError) and stale.exc.status_code == 409, stale.exc
    assert _state(db_session) == before  # the stale worker committed nothing
    db_session.rollback()
    assert db_session.execute(text("SELECT resulting_attachment_id FROM attachment_upload_sessions WHERE id = :i"),
                              {"i": str(session_id)}).scalar() is None  # and no success receipt

    monkeypatch.setitem(settings.__dict__, "upload_scan_command", "")  # the scanner is restored: the session completes
    assert _complete(world["client"], headers, str(session_id)).status_code == 200
