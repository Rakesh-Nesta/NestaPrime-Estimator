"""P4 migration (509d1202ac03) stage-backfill verification -- acceptance case 6, second half.

Case 6's own wording: "Stage rows are seeded correctly for both new and existing projects... run
the migration against a fixture DB with pre-existing legacy projects -- confirm every one gets
exactly one row per phase, and that a read-only stage-list call creates zero additional rows."

The new-project half (seed_stages_for_project, fired inside POST /projects) is already covered by
tests/test_p4_stage_evidence.py::test_stage_rows_seeded_for_new_project. This script is the other
half, the one actually requiring a real Alembic migration run -- the migration's own upgrade()
backfill (`if project_ids: op.bulk_insert(...)`) can't be exercised by the pytest suite at all,
since tests/conftest.py builds its schema via Base.metadata.create_all, never via Alembic.

Entirely self-contained and reproducible, mirroring verify_p4_rollback_guard.py's own pattern:
creates its own throwaway Postgres database (dropped at the end whether the run passes or fails),
upgrades it to the revision immediately BEFORE P4 (9f2c6b1e4a70 -- no project_construction_stages
table exists yet), creates real "legacy" projects against that pre-P4 schema via a real running
instance of this app, stops the app, upgrades the rest of the way to head (509d1202ac03 runs,
backfilling), and verifies directly against Postgres. Never touches the real dev or test
databases.

Usage (from backend/, with the local Postgres server running and credentials matching .env):
    .venv/Scripts/python.exe scripts/verify_p4_stage_backfill.py
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
CHECK_DB_NAME = "nestaprime_p4_stage_backfill_check"
PRE_P4_REVISION = "9f2c6b1e4a70"  # P4's own down_revision -- the schema immediately before it
EXPECTED_PHASES = (
    "site_prep", "sub_base", "flooring", "structure_fixtures", "lighting", "accessories_finishing",
)

results = []


def record(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS" if ok else "FAIL") + " - " + name + (f" :: {detail}" if detail else ""))


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


def _wait_for_app(base):
    for _ in range(60):
        try:
            if httpx.get(f"{base}/openapi.json", timeout=1).status_code == 200:
                return
        except httpx.TransportError:
            pass
        time.sleep(0.5)
    raise RuntimeError("stage-backfill-check app server never came up")


def create_legacy_projects(count=3):
    """Runs against the PRE-P4 schema -- project_construction_stages does not exist yet, so
    these projects are created exactly the way every real project predating this migration was:
    with no stages at all, nothing special about them. Run in-process (FastAPI TestClient, not a
    real uvicorn server) with seed_stages_for_project monkeypatched to a no-op: this checkout's
    *code* is always the current, P4-aware codebase (there is no old checkout to run), and that
    code unconditionally calls seed_stages_for_project inside create_project -- against a
    database still migrated only to the revision before P4, project_construction_stages doesn't
    exist yet, so that call would fail outright. The monkeypatch is what actually reproduces "a
    project created with no stage awareness at all", which is the real thing every pre-P4
    production project is. Run as its own subprocess so this process's own imports of app.* (none
    so far) never pick up a stale DATABASE_URL."""
    code = """
import os
os.environ["PYTHONPATH"] = r"{backend_dir}"
import sys
sys.path.insert(0, r"{backend_dir}")

import app.api.projects as projects_module
projects_module.seed_stages_for_project = lambda db, project_id: None  # pre-P4 behaviour

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
res = client.post(
    "/auth/login",
    data={{"username": "director@stage-backfill-check.local", "password": "StageBackfillCheck!1"}},
)
res.raise_for_status()
headers = {{"Authorization": f"Bearer {{res.json()['access_token']}}"}}
changed = client.post(
    "/auth/change-password", headers=headers,
    json={{"current_password": "StageBackfillCheck!1", "new_password": "StageBackfillCheck!2"}},
)
changed.raise_for_status()
headers = {{"Authorization": f"Bearer {{changed.json()['access_token']}}"}}

project_ids = []
for i in range({count}):
    client_id = client.post(
        "/clients", headers=headers, json={{"name": f"Legacy Client {{i}}", "type": "school"}}
    ).json()["id"]
    project_id = client.post(
        "/projects", headers=headers,
        json={{
            "client_id": client_id, "city": "Mumbai", "site_condition": "level", "soil_type": "normal",
            "building_status": "open_air", "site_access": "good", "power_available": "yes",
            "water_available": True, "package": "standard",
        }},
    ).json()["id"]
    project_ids.append(project_id)
print("LEGACY_PROJECT_IDS=" + ",".join(project_ids))
""".format(backend_dir=BACKEND_DIR, count=count)

    env = os.environ.copy()
    env["DATABASE_URL"] = CHECK_DB_URL_ALEMBIC
    env["INITIAL_DIRECTOR_EMAIL"] = "director@stage-backfill-check.local"
    env["INITIAL_DIRECTOR_PASSWORD"] = "StageBackfillCheck!1"
    env["PYTHONPATH"] = BACKEND_DIR
    subprocess.run(
        [PYTHON, os.path.join(BACKEND_DIR, "scripts", "seed_initial_director.py")],
        cwd=BACKEND_DIR, env=env, check=True, capture_output=True, text=True,
    )

    result = subprocess.run([PYTHON, "-c", code], cwd=BACKEND_DIR, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout, result.stderr)
        raise RuntimeError("creating legacy projects (monkeypatched, pre-P4 behaviour) failed")
    marker = next(line for line in result.stdout.splitlines() if line.startswith("LEGACY_PROJECT_IDS="))
    return marker.split("=", 1)[1].split(",")


def verify_backfill(project_ids):
    rows = sql(
        "SELECT project_id, phase, status FROM project_construction_stages WHERE project_id = ANY(%s)",
        (project_ids,),
    )
    by_project = {}
    for project_id, phase, status in rows:
        by_project.setdefault(str(project_id), []).append((phase, status))

    all_present = all(str(p) in by_project for p in project_ids)
    record("every legacy project received stage rows from the backfill", all_present, str(sorted(by_project.keys())))

    exact_six_each = all(len(by_project.get(str(p), [])) == 6 for p in project_ids)
    record("each legacy project has exactly 6 rows (one per phase), not more or fewer", exact_six_each)

    phases_match = all(
        {phase for phase, _status in by_project.get(str(p), [])} == set(EXPECTED_PHASES) for p in project_ids
    )
    record("each project's 6 rows are the 6 real distinct phases, no duplicates", phases_match)

    all_not_started = all(
        all(status == "not_started" for _phase, status in by_project.get(str(p), [])) for p in project_ids
    )
    record("every backfilled row starts 'not_started' (indistinguishable from a brand-new project's own seeding)", all_not_started)

    total_rows = sql("SELECT COUNT(*) FROM project_construction_stages")[0][0]
    record(
        "total row count matches exactly (3 projects x 6 phases = 18), no extra rows from anywhere else",
        total_rows == len(project_ids) * 6, f"actual={total_rows}",
    )


def verify_repeated_get_creates_no_rows(port, project_id):
    env = os.environ.copy()
    env["DATABASE_URL"] = CHECK_DB_URL_ALEMBIC
    env["PYTHONPATH"] = BACKEND_DIR
    server = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=BACKEND_DIR, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        _wait_for_app(base)
        # Password was already changed in create_legacy_projects (same database) -- log in with
        # the new one.
        res = httpx.post(
            f"{base}/auth/login",
            data={"username": "director@stage-backfill-check.local", "password": "StageBackfillCheck!2"},
        )
        res.raise_for_status()
        headers = {"Authorization": f"Bearer {res.json()['access_token']}"}

        before = sql("SELECT COUNT(*) FROM project_construction_stages")[0][0]
        first = httpx.get(f"{base}/projects/{project_id}/stages", headers=headers)
        assert first.status_code == 200, first.text
        first_count = len(first.json())
        second = httpx.get(f"{base}/projects/{project_id}/stages", headers=headers)
        assert second.status_code == 200, second.text
        second_count = len(second.json())
        after = sql("SELECT COUNT(*) FROM project_construction_stages")[0][0]

        record(
            "a read-only GET against a migration-backfilled project's stages returns 6, creates no rows",
            first_count == 6 and before == after, f"first={first_count}, second={second_count}, before={before}, after={after}",
        )
        record(
            "calling GET twice in a row is idempotent -- same 6 rows both times, row count never grows",
            first_count == second_count == 6,
        )
    finally:
        server.terminate()
        server.wait(timeout=10)


def main():
    create_check_database()
    try:
        up_to_pre_p4 = run_alembic(["upgrade", PRE_P4_REVISION])
        if up_to_pre_p4.returncode != 0:
            print(up_to_pre_p4.stdout, up_to_pre_p4.stderr)
            raise RuntimeError(f"upgrade to {PRE_P4_REVISION} (pre-P4) failed")
        current = run_alembic(["current"])
        print(f"=== Pre-P4 state: {current.stdout.strip()} ===")

        project_ids = create_legacy_projects(count=3)
        print(f"created {len(project_ids)} legacy projects against the pre-P4 schema: {project_ids}")

        # Confirm the table genuinely doesn't exist yet, pre-migration -- these really are legacy
        # projects with no stages at all, not an artifact of the app silently creating rows.
        pre_migration_table_exists = sql(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'project_construction_stages'"
        )
        record("project_construction_stages does not exist before the migration runs", not pre_migration_table_exists)

        to_head = run_alembic(["upgrade", "head"])
        if to_head.returncode != 0:
            print(to_head.stdout, to_head.stderr)
            raise RuntimeError("upgrade to head (applying P4's own migration) failed")
        current = run_alembic(["current"])
        print(f"=== Post-P4 state: {current.stdout.strip()} ===")

        verify_backfill(project_ids)
        verify_repeated_get_creates_no_rows(_free_port(), project_ids[0])

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
