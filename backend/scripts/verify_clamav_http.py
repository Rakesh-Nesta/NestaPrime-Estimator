"""Real ASGI HTTP routes + restored rehearsal DB + actual ClamAV; not nginx/Gunicorn.

Creates a disposable Director and upload records. NEVER use this DB for cutover.
Does not import pytest fixtures, drop tables, migrate, or use production storage.
"""

import argparse
import hashlib
import secrets
import sys
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.engine import make_url

from app.config import settings


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-disposable", action="store_true", required=True)
    parser.parse_args()
    url = make_url(settings.database_url)
    require(url.host == "nestaprime-rehearsal-db" and url.database == "nestaprime_estimator",
            "Refusing: this script requires the named disposable rehearsal database")

    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.security import hash_password
    from app.db.base import Base
    from app.db.session import SessionLocal
    from app.models.document import Quotation
    from app.models.user import User, UserRole
    from app.models.attachment_upload_session import AttachmentUploadSession

    real_command = "clamdscan --config-file=/app/scripts/clamd-client.conf --stream --no-summary"
    clean = b"NestaPrime real HTTP scanner rehearsal.\n"
    eicar = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

    with TemporaryDirectory(prefix="nesta-http-rehearsal-") as directory, SessionLocal() as db:
        root = Path(directory)
        settings.attachment_storage_root = str(root / "uploads")
        settings.upload_scan_required = True
        missing_config = root / "unavailable.conf"
        missing_config.write_text(f"LocalSocket {root / 'absent.sock'}\n")
        missing_command = f"clamdscan --config-file={missing_config} --stream --no-summary"
        quotation_id = db.execute(select(Quotation.id).limit(1)).scalar_one()
        password = secrets.token_urlsafe(24) + "Aa!7"
        user = User(name="Disposable scanner rehearsal", email=f"rehearsal-{uuid.uuid4().hex}@example.invalid",
                    hashed_password=hash_password(password), role=UserRole.DIRECTOR,
                    is_active=True, must_change_password=False)
        db.add(user)
        db.commit()
        email = user.email

        def snapshot():
            db.rollback()
            db.expire_all()
            rows = {}
            for table in Base.metadata.sorted_tables:
                if table.name in {"attachment_upload_sessions", "attachment_upload_chunks"}:
                    continue
                statement = select(table)
                if list(table.primary_key.columns):
                    statement = statement.order_by(*table.primary_key.columns)
                rows[table.name] = [tuple(repr(value) for value in row) for row in db.execute(statement)]
            files = {}
            storage = Path(settings.attachment_storage_root)
            for path in storage.rglob("*"):
                if path.is_file():
                    relative = path.relative_to(storage)
                    if relative.parts[0] not in {"_upload_tmp", "_quarantine"}:
                        files[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
            return rows, files

        with TestClient(app) as client:
            login = client.post("/auth/login", data={"username": email, "password": password})
            require(login.status_code == 200, f"Rehearsal login failed: {login.status_code}")
            headers = {"Authorization": "Bearer " + login.json()["access_token"]}

            def ordinary(content):
                return client.post("/attachments", headers=headers,
                                   data={"doc_type": "quotation", "doc_id": str(quotation_id), "tag": "reference"},
                                   files={"file": ("rehearsal.txt", content, "text/plain")})

            def check_download(attachment_id, content):
                response = client.get(f"/attachments/{attachment_id}/download", headers=headers)
                require(response.status_code == 200 and response.content == content,
                        "Downloaded bytes differ from the submitted file")

            for path_name in ("ordinary", "supersede", "resumable"):
                for outcome in ("clean", "infected", "unavailable"):
                    settings.upload_scan_command = real_command
                    content = eicar if outcome == "infected" else clean
                    session_id = None
                    original_id = None
                    if path_name == "supersede":
                        original = ordinary(clean)
                        require(original.status_code == 201, f"Supersede baseline failed: {original.status_code}")
                        original_id = original.json()["id"]
                    if path_name == "resumable":
                        start = client.post("/attachments/upload-sessions", headers=headers, json={
                            "doc_type": "quotation", "doc_id": str(quotation_id), "filename": "rehearsal.txt",
                            "declared_size": len(content), "declared_sha256": hashlib.sha256(content).hexdigest(),
                            "chunk_size": len(content),
                        })
                        require(start.status_code == 201, f"Session start failed: {start.status_code}")
                        session_id = start.json()["id"]
                        chunk = client.post(f"/attachments/upload-sessions/{session_id}/chunks/0", headers=headers,
                                            files={"file": ("chunk", content, "application/octet-stream")})
                        require(chunk.status_code == 200, f"Chunk failed: {chunk.status_code}")

                    before = snapshot()
                    settings.upload_scan_command = missing_command if outcome == "unavailable" else real_command
                    if path_name == "ordinary":
                        response = ordinary(content)
                    elif path_name == "supersede":
                        response = client.post(f"/attachments/{original_id}/supersede", headers=headers,
                                               data={"tag": "reference"},
                                               files={"file": ("rehearsal.txt", content, "text/plain")})
                    else:
                        response = client.post(f"/attachments/upload-sessions/{session_id}/complete", headers=headers)
                    expected = (200 if path_name == "resumable" else 201) if outcome == "clean" else (422 if outcome == "infected" else 503)
                    require(response.status_code == expected,
                            f"{path_name}/{outcome}: expected {expected}, got {response.status_code}: {response.text[:300]}")

                    if outcome == "clean":
                        check_download(response.json()["id"], content)
                    else:
                        require(snapshot() == before, f"{path_name}/{outcome}: changed non-session DB data or servable files")
                        if session_id:
                            db.rollback()
                            db.expire_all()
                            session = db.get(AttachmentUploadSession, uuid.UUID(session_id))
                            expected_state = "failed" if outcome == "infected" else "uploading"
                            require(session.status == expected_state and session.resulting_attachment_id is None,
                                    f"Unexpected refused-session state: {session.status}")
                    print(f"PASS {path_name}/{outcome}: HTTP {expected}", flush=True)

                    if session_id and outcome == "unavailable":
                        settings.upload_scan_command = real_command
                        retry = client.post(f"/attachments/upload-sessions/{session_id}/complete", headers=headers)
                        require(retry.status_code == 200, f"Scanner recovery retry failed: {retry.status_code}")
                        check_download(retry.json()["id"], clean)
                        print("PASS recovered scanner completes the same session", flush=True)
                    if session_id and outcome == "clean":
                        before_retry = snapshot()
                        settings.upload_scan_command = missing_command
                        retry = client.post(f"/attachments/upload-sessions/{session_id}/complete", headers=headers)
                        require(retry.status_code == 200 and retry.json()["id"] == response.json()["id"],
                                "Completed-session retry did not return its original receipt")
                        require(snapshot() == before_retry, "Completed retry changed data/files")
                        print("PASS completed-session retry returns receipt without scanner/new files", flush=True)

        print("HTTP_REHEARSAL_CHECKS=11; disposable DB contains test records and must not be promoted", flush=True)


if __name__ == "__main__":
    main()
