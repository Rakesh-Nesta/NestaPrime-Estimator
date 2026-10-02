"""Real-Alembic verification of the PDF-exclusions (b7a4c9d2e1f3) and message-send-attempts (c8e5d0f3a2b4) migrations.

Self-contained and reproducible; creates its own throwaway Postgres database (always dropped) and never touches the dev or
test databases. Works on the feature branch alone AND on a combined P5 + features tree (it detects P5's migration and then also
checks the documented marker exception).

Checks:
  1. exactly ONE Alembic head, with no temporary revision edits;
  2. upgrade to head; real rows are created with the application's models (a user, an attachment, an exclusion, a message
     attempt that was resent);
  3. `downgrade -1` is REFUSED while message send-attempt records exist (nothing dropped, rows intact), succeeds once they are
     removed; likewise `downgrade -1` is REFUSED while an exclusion exists, succeeds once it is removed;
  4. (combined tree) the next downgrade passes through P5's own guard and P5's `p5_migration_marker` table and row are KEPT
     (the documented rollback exception);
  5. re-upgrade to head succeeds and there is still exactly one head.

Usage (from backend/, local Postgres running, credentials in .env):  .venv/Scripts/python.exe scripts/verify_feature_migrations.py
"""
import os
import subprocess
import sys

import psycopg

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
NAME = "nestaprime_feature_migration_check"
P5_REVISION = "a5e7c2d9b413"


def password() -> str:
    for line in open(os.path.join(BACKEND, ".env")):
        if line.startswith("DATABASE_URL="):
            return line.strip().split("://", 1)[1].split(":", 1)[1].split("@", 1)[0]
    raise RuntimeError("DATABASE_URL not found in .env")


PW = password()
ENV = {**os.environ, "DATABASE_URL": f"postgresql+psycopg://nestaprime:{PW}@localhost:5432/{NAME}", "PYTHONPATH": BACKEND}
RESULTS: list[tuple[str, bool]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name} {detail}")


def alembic(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([PY, "-m", "alembic", *args], cwd=BACKEND, env=ENV, capture_output=True, text=True)


def conn():
    return psycopg.connect(f"postgresql://nestaprime:{PW}@localhost:5432/{NAME}", autocommit=True)


def scalar(sql: str):
    with conn() as c:
        return c.execute(sql).fetchone()[0]


def has_table(name: str) -> bool:
    return bool(scalar(f"SELECT to_regclass('public.{name}') IS NOT NULL"))


def has_column(table: str, column: str) -> bool:
    return bool(scalar(f"SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{table}' AND column_name='{column}')"))


SEED = r'''
import uuid
from app.db.session import SessionLocal
from app.models.attachment import Attachment, AttachmentTag
from app.models.message import Message, MessageChannel, MessageStatus
from app.models.pdf_image_exclusion import PdfImageExclusion
from app.models.setting import DocumentType
from app.models.user import User, UserRole
from app.core.security import hash_password

db = SessionLocal()
user = User(name="Seed", email="seed@migration.check", hashed_password=hash_password("x"), role=UserRole.DIRECTOR)
db.add(user); db.flush()
doc = uuid.uuid4()
att = Attachment(doc_type=DocumentType.QUOTATION, doc_id=doc, original_filename="p.png", original_size=1, original_sha256="0"*64,
                 storage_path="x", tag=AttachmentTag.PHOTO, uploaded_by_id=user.id, version=1)
db.add(att); db.flush()
db.add(PdfImageExclusion(doc_type="quotation", doc_id=doc, attachment_id=att.id, excluded_by_id=user.id))
first = Message(doc_type=DocumentType.QUOTATION, doc_id=doc, channel=MessageChannel.WHATSAPP, recipient="+91", sender_id=user.id,
                status=MessageStatus.RECORDED, request_id=str(uuid.uuid4()), attempt_state="unknown")
db.add(first); db.flush()
db.add(Message(doc_type=DocumentType.QUOTATION, doc_id=doc, channel=MessageChannel.WHATSAPP, recipient="+91", sender_id=user.id,
               status=MessageStatus.SENT, request_id=str(uuid.uuid4()), attempt_state="accepted",
               previous_attempt_id=first.id, resend_confirmed_by_id=user.id))
db.commit()
print("seeded")
'''


def main() -> int:
    admin = psycopg.connect(f"postgresql://nestaprime:{PW}@localhost:5432/nestaprime_estimator", autocommit=True)
    try:
        admin.execute(f'DROP DATABASE IF EXISTS "{NAME}" WITH (FORCE)')
        admin.execute(f'CREATE DATABASE "{NAME}"')

        heads = alembic("heads").stdout.strip().splitlines()
        check("1. exactly one Alembic head (no temporary edits)", len(heads) == 1, f"{heads}")
        p5_present = os.path.exists(os.path.join(BACKEND, "alembic", "versions", f"{P5_REVISION}_p5_agreement_and_execution_starter.py"))

        up = alembic("upgrade", "head")
        check("2. upgrade to head", up.returncode == 0, up.stderr[-200:] if up.returncode else "")
        seed = subprocess.run([PY, "-c", SEED], cwd=BACKEND, env=ENV, capture_output=True, text=True)
        check("2. real rows created with the application's models", "seeded" in seed.stdout, seed.stderr[-300:])
        before = (scalar("SELECT COUNT(*) FROM messages"), scalar("SELECT COUNT(*) FROM pdf_image_exclusions"))

        refused = alembic("downgrade", "-1")
        check("3. downgrade REFUSED while message send-attempt records exist", refused.returncode != 0 and "Refusing to downgrade" in refused.stderr + refused.stdout)
        check("3. ...and nothing was dropped (columns and rows intact)", has_column("messages", "request_id") and scalar("SELECT COUNT(*) FROM messages") == before[0])

        with conn() as c:
            c.execute("UPDATE messages SET previous_attempt_id = NULL, resend_confirmed_by_id = NULL, request_id = NULL, attempt_state = NULL")
        ok = alembic("downgrade", "-1")
        check("3. downgrade succeeds once the attempt records are gone", ok.returncode == 0 and not has_column("messages", "request_id"), ok.stderr[-200:] if ok.returncode else "")

        refused = alembic("downgrade", "-1")
        check("3. downgrade REFUSED while a PDF image exclusion exists", refused.returncode != 0 and "Refusing to downgrade" in refused.stderr + refused.stdout)
        check("3. ...and the exclusion is intact", has_table("pdf_image_exclusions") and scalar("SELECT COUNT(*) FROM pdf_image_exclusions") == before[1])
        with conn() as c:
            c.execute("DELETE FROM pdf_image_exclusions")
        ok = alembic("downgrade", "-1")
        check("3. downgrade succeeds once the exclusions are gone", ok.returncode == 0 and not has_table("pdf_image_exclusions"), ok.stderr[-200:] if ok.returncode else "")

        if p5_present:
            with conn() as c:
                marker_before = c.execute("SELECT id, deployed_at FROM p5_migration_marker").fetchall()
            ok = alembic("downgrade", "-1")  # P5's own downgrade (its guard passes: no P5 data)
            marker_after = []
            if has_table("p5_migration_marker"):
                with conn() as c:
                    marker_after = c.execute("SELECT id, deployed_at FROM p5_migration_marker").fetchall()
            check("4. P5's downgrade passes its own guard (no P5 data)", ok.returncode == 0 and not has_table("agreements"), ok.stderr[-200:] if ok.returncode else "")
            check("4. P5's marker table and row are KEPT (documented rollback exception)", marker_before == marker_after and len(marker_after) == 1)

        again = alembic("upgrade", "head")
        heads_after = alembic("heads").stdout.strip().splitlines()
        check("5. re-upgrade to head succeeds with exactly one head", again.returncode == 0 and len(heads_after) == 1, again.stderr[-200:] if again.returncode else "")
        if p5_present:
            with conn() as c:
                marker_final = c.execute("SELECT id, deployed_at FROM p5_migration_marker").fetchall()
            check("5. the ORIGINAL P5 marker is unchanged after the downgrade/re-upgrade cycle", marker_final == marker_before and len(marker_final) == 1,
                  f"original={marker_before[0][1].isoformat() if marker_before else None} final={marker_final[0][1].isoformat() if marker_final else None}")
    finally:
        admin.execute(f'DROP DATABASE IF EXISTS "{NAME}" WITH (FORCE)')
        admin.close()
    failed = [name for name, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
