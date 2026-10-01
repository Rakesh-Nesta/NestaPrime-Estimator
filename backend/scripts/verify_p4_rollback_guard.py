"""P4 migration (509d1202ac03) rollback-guard verification -- acceptance case 24.

The migration's own downgrade() refuses (raises RuntimeError, naming exactly what it found) if
any of 13 conditions hold: 10 individual Attachment columns are non-null, either of the two new
upload-protocol tables has a row, or any project_construction_stages row has moved off
'not_started'. This script proves each of those 13 conditions is independently detected --
not just "downgrade sometimes refuses" -- by populating exactly one at a time against a
disposable database, confirming the refusal names that one specifically, clearing it, confirming
downgrade then succeeds, and restoring the schema before moving to the next.

Entirely self-contained and reproducible: creates its own throwaway Postgres database (dropped
at the end whether the run passes or fails), runs the real Alembic migration history against it,
drives a real uvicorn instance of this app to build one small, realistic record chain (via the
same API endpoints production traffic uses -- not hand-built rows that might not satisfy
constraints the app itself would enforce), then exercises `alembic downgrade -1` / `upgrade +1`
13 times over. Never touches the real dev or test databases.

Usage (from backend/, with the local Postgres server running and credentials matching .env):
    .venv/Scripts/python.exe scripts/verify_p4_rollback_guard.py
"""
import os
import socket
import subprocess
import sys
import time

import httpx
import psycopg

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = os.path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe")
CHECK_DB_NAME = "nestaprime_p4_rollback_check"


def _db_password() -> str:
    with open(os.path.join(BACKEND_DIR, ".env")) as f:
        for line in f:
            if line.startswith("DATABASE_URL="):
                return line.strip().split("://", 1)[1].split(":", 1)[1].split("@", 1)[0]
    raise RuntimeError("DATABASE_URL not found in .env")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


DB_PASSWORD = _db_password()
ADMIN_DB_URL = f"postgresql://nestaprime:{DB_PASSWORD}@localhost:5432/nestaprime_estimator"
CHECK_DB_URL_PSYCOPG = f"postgresql://nestaprime:{DB_PASSWORD}@localhost:5432/{CHECK_DB_NAME}"
CHECK_DB_URL_ALEMBIC = f"postgresql+psycopg://nestaprime:{DB_PASSWORD}@localhost:5432/{CHECK_DB_NAME}"

results = []


def record(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS" if ok else "FAIL") + " - " + name + (f" :: {detail}" if detail else ""))


def sql(query, params=None):
    conn = psycopg.connect(CHECK_DB_URL_PSYCOPG, autocommit=True)
    try:
        cur = conn.cursor()
        cur.execute(query, params)
        return cur.fetchall() if cur.description else None
    finally:
        conn.close()


def run_alembic(args):
    env = os.environ.copy()
    env["DATABASE_URL"] = CHECK_DB_URL_ALEMBIC
    return subprocess.run([PYTHON, "-m", "alembic"] + args, cwd=BACKEND_DIR, env=env, capture_output=True, text=True)


def downgrade():
    return run_alembic(["downgrade", "-1"])


def upgrade():
    return run_alembic(["upgrade", "+1"])


def create_check_database():
    conn = psycopg.connect(ADMIN_DB_URL, autocommit=True)
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (CHECK_DB_NAME,))
        if cur.fetchone():
            cur.execute(f"DROP DATABASE {CHECK_DB_NAME}")
        cur.execute(f"CREATE DATABASE {CHECK_DB_NAME}")
    finally:
        conn.close()


def drop_check_database():
    conn = psycopg.connect(ADMIN_DB_URL, autocommit=True)
    try:
        cur = conn.cursor()
        cur.execute(f"DROP DATABASE IF EXISTS {CHECK_DB_NAME} WITH (FORCE)")
    finally:
        conn.close()


def build_baseline_data(port):
    env = os.environ.copy()
    env["DATABASE_URL"] = CHECK_DB_URL_ALEMBIC
    env["INITIAL_DIRECTOR_EMAIL"] = "director@rollback-check.local"
    env["INITIAL_DIRECTOR_PASSWORD"] = "RollbackCheck!1"
    env["PYTHONPATH"] = BACKEND_DIR
    subprocess.run(
        [PYTHON, os.path.join(BACKEND_DIR, "scripts", "seed_initial_director.py")],
        cwd=BACKEND_DIR, env=env, check=True, capture_output=True, text=True,
    )

    server = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=BACKEND_DIR, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(60):
            try:
                if httpx.get(f"{base}/openapi.json", timeout=1).status_code == 200:
                    break
            except httpx.TransportError:
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError("rollback-check app server never came up")

        res = httpx.post(
            f"{base}/auth/login",
            data={"username": "director@rollback-check.local", "password": "RollbackCheck!1"},
        )
        res.raise_for_status()
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        res = httpx.post(
            f"{base}/auth/change-password",
            headers=headers,
            json={"current_password": "RollbackCheck!1", "new_password": "RollbackCheck!2"},
        )
        res.raise_for_status()
        headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
        director_user_id = httpx.get(f"{base}/auth/me", headers=headers).json()["id"]

        client_id = httpx.post(
            f"{base}/clients", headers=headers, json={"name": "Rollback Check Client", "type": "school"}
        ).json()["id"]
        project_id = httpx.post(
            f"{base}/projects", headers=headers,
            json={
                "client_id": client_id, "city": "Mumbai", "site_condition": "level", "soil_type": "normal",
                "building_status": "open_air", "site_access": "good", "power_available": "yes",
                "water_available": True, "package": "standard",
            },
        ).json()["id"]
        cost_sheet_id = httpx.post(
            f"{base}/projects/{project_id}/cost-sheets", headers=headers, json={"cost_total": 100000}
        ).json()["id"]

        attachment_ids = []
        for i in range(2):
            res = httpx.post(
                f"{base}/attachments", headers=headers,
                data={"doc_type": "cost_sheet", "doc_id": cost_sheet_id, "tag": "soil_report"},
                files={"file": (f"rollback{i}.txt", f"hello{i}".encode(), "text/plain")},
            )
            res.raise_for_status()
            attachment_ids.append(res.json()["id"])

        return {
            "director_user_id": director_user_id,
            "project_id": project_id,
            "attachment1_id": attachment_ids[0],
            "attachment2_id": attachment_ids[1],
        }
    finally:
        server.terminate()
        server.wait(timeout=10)


COLUMN_CASES = [
    ("captured_at", "column:attachments.captured_at", "TIMESTAMP '2026-01-01 00:00:00'"),
    ("captured_at_source", "column:attachments.captured_at_source", "'manual'"),
    ("review_status", "column:attachments.review_status", "'approved'"),
    ("reviewed_by_id", "column:attachments.reviewed_by_id", None),  # director_user_id, filled in below
    ("reviewed_at", "column:attachments.reviewed_at", "TIMESTAMP '2026-01-01 00:00:00'"),
    ("marketing_reuse_approved_at", "column:attachments.marketing_reuse_approved_at", "TIMESTAMP '2026-01-01 00:00:00'"),
    ("marketing_reuse_approved_by_id", "column:attachments.marketing_reuse_approved_by_id", None),
    ("marketing_reuse_revoked_at", "column:attachments.marketing_reuse_revoked_at", "TIMESTAMP '2026-01-01 00:00:00'"),
    ("marketing_reuse_revoked_by_id", "column:attachments.marketing_reuse_revoked_by_id", None),
    ("derived_from_id", "column:attachments.derived_from_id", None),  # attachment2_id, filled in below
]


def confirm_clean_baseline(label):
    res = downgrade()
    if res.returncode != 0:
        record(f"PRECONDITION before '{label}': baseline is clean", False, res.stderr[-800:])
        return False
    up = upgrade()
    if up.returncode != 0:
        record(f"PRECONDITION before '{label}': re-upgrade after baseline check", False, up.stderr[-800:])
        return False
    return True


def run_column_case(column, expected_token, sql_value, attachment1_id):
    if not confirm_clean_baseline(column):
        return
    sql(f"UPDATE attachments SET {column} = {sql_value} WHERE id = %s", (attachment1_id,))
    res = downgrade()
    refused = res.returncode != 0 and expected_token in (res.stdout + res.stderr)
    record(f"downgrade refuses with {column} populated, names it exactly", refused,
           "" if refused else (res.stdout + res.stderr)[-800:])

    sql(f"UPDATE attachments SET {column} = NULL WHERE id = %s", (attachment1_id,))
    res2 = downgrade()
    record(f"downgrade succeeds once {column} is cleared", res2.returncode == 0,
           "" if res2.returncode == 0 else (res2.stdout + res2.stderr)[-800:])

    up = upgrade()
    if up.returncode != 0:
        record(f"re-upgrade after {column} case", False, up.stderr[-800:])


def run_table_case(table, expected_token, insert_fn, cleanup_fn):
    if not confirm_clean_baseline(table):
        return
    insert_fn()
    res = downgrade()
    refused = res.returncode != 0 and expected_token in (res.stdout + res.stderr)
    record(f"downgrade refuses with a row in {table}, names it exactly", refused,
           "" if refused else (res.stdout + res.stderr)[-800:])

    cleanup_fn()
    res2 = downgrade()
    record(f"downgrade succeeds once {table} is empty", res2.returncode == 0,
           "" if res2.returncode == 0 else (res2.stdout + res2.stderr)[-800:])

    up = upgrade()
    if up.returncode != 0:
        record(f"re-upgrade after {table} case", False, up.stderr[-800:])


def run_stage_activity_case(project_id):
    if not confirm_clean_baseline("stage activity"):
        return
    stage_id = sql("SELECT id FROM project_construction_stages WHERE project_id = %s LIMIT 1", (project_id,))[0][0]
    sql("UPDATE project_construction_stages SET status = 'in_progress' WHERE id = %s", (stage_id,))
    res = downgrade()
    expected_token = "project_construction_stages (status != not_started)"
    refused = res.returncode != 0 and expected_token in (res.stdout + res.stderr)
    record("downgrade refuses with one stage not 'not_started', names it exactly", refused,
           "" if refused else (res.stdout + res.stderr)[-800:])

    sql("UPDATE project_construction_stages SET status = 'not_started' WHERE id = %s", (stage_id,))
    res2 = downgrade()
    record("downgrade succeeds once all stages are back to not_started", res2.returncode == 0,
           "" if res2.returncode == 0 else (res2.stdout + res2.stderr)[-800:])

    up = upgrade()
    if up.returncode != 0:
        record("re-upgrade after stage-activity case", False, up.stderr[-800:])


def main():
    create_check_database()
    try:
        up = run_alembic(["upgrade", "head"])
        if up.returncode != 0:
            print(up.stdout, up.stderr)
            raise RuntimeError("initial upgrade to head failed")
        print(f"=== Starting state: {run_alembic(['current']).stdout.strip()} ===")

        data = build_baseline_data(_free_port())
        attachment1_id, attachment2_id, director_user_id = (
            data["attachment1_id"], data["attachment2_id"], data["director_user_id"],
        )

        for column, expected_token, sql_value in COLUMN_CASES:
            if sql_value is None:
                sql_value = (
                    f"'{attachment2_id}'::uuid" if column == "derived_from_id" else f"'{director_user_id}'::uuid"
                )
            run_column_case(column, expected_token, sql_value, attachment1_id)

        run_table_case(
            "attachment_upload_sessions", "table:attachment_upload_sessions",
            insert_fn=lambda: sql(
                "INSERT INTO attachment_upload_sessions "
                "(id, doc_type, doc_id, filename, declared_size, declared_sha256, chunk_size, total_chunks, "
                "created_by_id) VALUES (gen_random_uuid(), 'cost_sheet', %s, 'f.bin', 10, 'deadbeef', 10, 1, %s)",
                (attachment1_id, director_user_id),
            ),
            cleanup_fn=lambda: sql("DELETE FROM attachment_upload_sessions WHERE doc_id = %s", (attachment1_id,)),
        )

        def insert_chunk_and_its_session():
            sql(
                "INSERT INTO attachment_upload_sessions "
                "(id, doc_type, doc_id, filename, declared_size, declared_sha256, chunk_size, total_chunks, "
                "created_by_id) VALUES (gen_random_uuid(), 'cost_sheet', %s, 'f.bin', 10, 'deadbeef', 10, 1, %s)",
                (attachment1_id, director_user_id),
            )
            session_id = sql("SELECT id FROM attachment_upload_sessions WHERE doc_id = %s", (attachment1_id,))[0][0]
            sql("INSERT INTO attachment_upload_chunks (session_id, chunk_index, received_bytes) VALUES (%s, 0, 10)",
                (session_id,))

        def cleanup_chunk_and_its_session():
            sql(
                "DELETE FROM attachment_upload_chunks WHERE session_id IN "
                "(SELECT id FROM attachment_upload_sessions WHERE doc_id = %s)", (attachment1_id,),
            )
            sql("DELETE FROM attachment_upload_sessions WHERE doc_id = %s", (attachment1_id,))

        run_table_case(
            "attachment_upload_chunks", "table:attachment_upload_chunks",
            insert_fn=insert_chunk_and_its_session, cleanup_fn=cleanup_chunk_and_its_session,
        )

        run_stage_activity_case(data["project_id"])

        print("\n=== SUMMARY ===")
        failed = [r for r in results if not r[1]]
        print(f"{len(results) - len(failed)}/{len(results)} passed")
        if failed:
            print("FAILURES:")
            for name, _ok, detail in failed:
                print(f"  - {name} :: {detail}")
        return 1 if failed else 0
    finally:
        drop_check_database()


if __name__ == "__main__":
    sys.exit(main())
