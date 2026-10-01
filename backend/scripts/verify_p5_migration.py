"""P5 migration (a5e7c2d9b413) end-to-end verification against GENUINELY pre-P5 data -- acceptance
cases 25, 26 and 27 (real-Alembic half).

The pytest suite builds its schema with Base.metadata.create_all, never through Alembic, and has to
*simulate* a pre-P5 database. This script does the real thing, self-contained and reproducible:

1. creates its own throwaway Postgres database (dropped at the end whether the run passes or fails);
2. checks out the P4-merged main commit (69ca579) into a temporary git worktree, so the "legacy" data
   is created by the genuinely OLD application code -- no P5 gates, no P5 tables -- against a database
   migrated only to the revision before P5 (509d1202ac03): a Won quotation WITH a Work Order, and a Won
   quotation WITHOUT one;
3. runs the real P5 Alembic upgrade and verifies the legacy rows were preserved untouched, the six P5
   tables start empty, the partial unique indexes and the single-row marker exist, and the marker is
   not older than the legacy Work Order;
4. proves a clean downgrade of the still-empty P5 schema succeeds, and re-upgrades;
5. runs the adoption script (dry run, then --confirm) and verifies exactly the Work-Order pair is
   adopted as 'legacy_adopted', the Won-without-Work-Order quotation is not, and a repeat run changes
   nothing;
6. drives the CURRENT app: the legacy Work Order's payment/status routes still work; the un-awarded Won
   quotation is blocked until Agreement + team + authorization exist, then starts; a Work Order created
   AFTER the migration is never eligible for adoption;
7. proves `alembic downgrade -1` is REFUSED once P5 data exists, and that nothing was dropped.

Never touches the real dev or test databases.

Usage (from backend/, with the local Postgres server running and credentials matching .env):
    .venv/Scripts/python.exe scripts/verify_p5_migration.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import psycopg

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(BACKEND_DIR)
PYTHON = os.path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe")
CHECK_DB_NAME = "nestaprime_p5_migration_check"
PRE_P5_REVISION = "509d1202ac03"
P5_REVISION = "a5e7c2d9b413"
PRE_P5_COMMIT = "69ca579a59bd54d08958842a572a19f8ff094950"  # main right after P4 merged
WORKTREE = os.path.join(tempfile.gettempdir(), "p5_verify_pre_p5_worktree")
OLD_BACKEND = os.path.join(WORKTREE, "backend")
P5_TABLES = (
    "agreements", "project_execution_authorizations", "project_team_members",
    "project_milestones", "project_tasks", "project_site_issues",
)
DIRECTOR_EMAIL = "director@p5-migration-check.local"
PW1, PW2 = "P5MigrationCheck!1", "P5MigrationCheck!2"

results = []


def record(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS" if ok else "FAIL") + " - " + name + (f" :: {detail}" if detail else ""), flush=True)


def _db_password() -> str:
    with open(os.path.join(BACKEND_DIR, ".env")) as f:
        for line in f:
            if line.startswith("DATABASE_URL="):
                return line.strip().split("://", 1)[1].split(":", 1)[1].split("@", 1)[0]
    raise RuntimeError("DATABASE_URL not found in .env")


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


def scalar(query, params=None):
    rows = sql(query, params)
    return rows[0][0] if rows else None


def env_for(backend_dir):
    env = os.environ.copy()
    env["DATABASE_URL"] = CHECK_DB_URL_ALEMBIC
    env["INITIAL_DIRECTOR_EMAIL"] = DIRECTOR_EMAIL
    env["INITIAL_DIRECTOR_PASSWORD"] = PW1
    env["PYTHONPATH"] = backend_dir
    return env


def run_alembic(args):
    return subprocess.run([PYTHON, "-m", "alembic"] + args, cwd=BACKEND_DIR, env=env_for(BACKEND_DIR), capture_output=True, text=True)


def create_check_database():
    conn = psycopg.connect(ADMIN_DB_URL, autocommit=True)
    try:
        conn.execute(f'DROP DATABASE IF EXISTS "{CHECK_DB_NAME}"')
        conn.execute(f'CREATE DATABASE "{CHECK_DB_NAME}"')
    finally:
        conn.close()


def drop_check_database():
    conn = psycopg.connect(ADMIN_DB_URL, autocommit=True)
    try:
        conn.execute(f'DROP DATABASE IF EXISTS "{CHECK_DB_NAME}" WITH (FORCE)')
    finally:
        conn.close()


def make_worktree():
    shutil.rmtree(WORKTREE, ignore_errors=True)
    subprocess.run(["git", "worktree", "prune"], cwd=REPO_ROOT, check=True, capture_output=True)
    subprocess.run(["git", "worktree", "add", "--detach", WORKTREE, PRE_P5_COMMIT], cwd=REPO_ROOT, check=True, capture_output=True)
    shutil.copy(os.path.join(BACKEND_DIR, ".env"), os.path.join(OLD_BACKEND, ".env"))


def remove_worktree():
    subprocess.run(["git", "worktree", "remove", "--force", WORKTREE], cwd=REPO_ROOT, capture_output=True)
    shutil.rmtree(WORKTREE, ignore_errors=True)
    subprocess.run(["git", "worktree", "prune"], cwd=REPO_ROOT, capture_output=True)


SEED_SCRIPTS = (
    "seed_initial_director",  # first: seed_settings needs a Director to attribute rows to
    "seed_regional_multipliers", "seed_sports", "seed_margin_policies", "seed_settings", "seed_labour_categories",
    "seed_scope_items", "seed_flooring_guides", "seed_lighting_standards", "seed_netting_grades",
    "seed_accessory_catalog", "seed_rate_items", "seed_cross_sell_addons",
)


def seed(backend_dir):
    for name in SEED_SCRIPTS:
        result = subprocess.run(
            [PYTHON, os.path.join(backend_dir, "scripts", f"{name}.py")],
            cwd=backend_dir, env=env_for(backend_dir), capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"{name} failed: {result.stdout[-400:]} {result.stderr[-800:]}")


# A tiny in-process driver, run as its own subprocess so it imports whichever app tree (old worktree or
# current checkout) it is pointed at. Phases are selected by argv[1]; each prints one JSON line.
DRIVER = r'''
import json, sys, uuid
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import app

PW1, PW2, EMAIL = "{pw1}", "{pw2}", "{email}"
phase, state = sys.argv[1], json.loads(sys.argv[2])
client = TestClient(app)

def login():
    res = client.post("/auth/login", data={{"username": EMAIL, "password": PW2}})
    if res.status_code != 200:
        res = client.post("/auth/login", data={{"username": EMAIL, "password": PW1}})
        res.raise_for_status()
        h = {{"Authorization": "Bearer " + res.json()["access_token"]}}
        res = client.post("/auth/change-password", headers=h, json={{"current_password": PW1, "new_password": PW2}})
        res.raise_for_status()
    return {{"Authorization": "Bearer " + res.json()["access_token"]}}

H = login()

def post(path, **kw):
    return client.post(path, headers=H, **kw)

def won_quotation(name):
    cid = post("/clients", json={{"name": name, "type": "school", "contact_name": "C", "phone": "9876543210"}}).json()["id"]
    pid = post("/projects", json={{"client_id": cid, "city": "Mumbai", "site_condition": "level", "soil_type": "normal",
        "building_status": "open_air", "site_access": "good", "power_available": "yes", "water_available": True,
        "package": "standard"}}).json()["id"]
    sport = next(s["id"] for s in client.get("/sports", headers=H).json() if s["key"] == "badminton")
    ps = post(f"/projects/{{pid}}/sports", json={{"sport_id": sport, "building_status": "open_air"}}).json()["id"]
    cs = post(f"/projects/{{pid}}/cost-sheets", json={{"cost_total": 850000}}).json()["id"]
    post(f"/cost-sheets/{{cs}}/verify")
    assert post(f"/projects/{{pid}}/scope-items/confirm-empty").status_code == 200
    survey = post(f"/projects/{{pid}}/site-surveys", json={{}}).json()
    for i in range(4):
        r = client.post("/attachments", data={{"doc_type": "site_survey", "doc_id": survey["id"], "tag": "photo"}},
                        files={{"file": (f"p{{i}}.txt", b"photo", "text/plain")}}, headers=H)
        assert r.status_code == 201, r.text
    assert post(f"/site-surveys/{{survey['id']}}/complete").status_code == 200
    est = post(f"/projects/{{pid}}/estimates", json={{"options": [{{"project_sport_id": ps, "package": "standard", "cost_for_option": 850000}}]}}).json()
    opt = est["options"][0]["id"]
    client.patch(f"/estimates/{{est['id']}}/options/{{opt}}/client-status", json={{"client_status": "approved", "waive_evidence_reason": "check"}}, headers=H)
    qid = post(f"/projects/{{pid}}/quotations", json={{"estimate_id": est["id"], "included_option_ids": [opt]}}).json()["id"]
    post(f"/quotations/{{qid}}/release"); post(f"/quotations/{{qid}}/send")
    won = post(f"/quotations/{{qid}}/mark-won", json={{"reason": "check", "waive_evidence_reason": "check"}})
    assert won.status_code == 200, won.text
    return {{"client": cid, "project": pid, "quotation": qid}}

def p5_ready(q):
    ag = post(f"/quotations/{{q['quotation']}}/agreement"); assert ag.status_code == 201, ag.text; ag = ag.json()
    att = client.post("/attachments", data={{"doc_type": "agreement", "doc_id": ag["id"], "tag": "signed_document"}},
                      files={{"file": ("a.pdf", b"signed", "application/pdf")}}, headers=H); assert att.status_code == 201, att.text
    sig = post(f"/clients/{{q['client']}}/signatories", json={{"name": "S", "designation": "Principal",
        "authorization_date": str(date.today() - timedelta(days=5))}}).json()
    r = post(f"/agreements/{{ag['id']}}/client-sign", json={{"client_signatory_id": sig["id"], "signed_on": str(date.today()),
        "attachment_id": att.json()["id"]}}); assert r.status_code == 200, r.text
    r = post(f"/agreements/{{ag['id']}}/execute"); assert r.status_code == 200, r.text
    eng = post("/users", json={{"name": "Eng", "email": "eng-" + uuid.uuid4().hex[:6] + "@p5check.local", "role": "site_engineer", "password": "EngPass!2345"}}).json()
    r = post(f"/projects/{{q['project']}}/team", json={{"user_id": eng["id"], "project_role": "site_engineer"}}); assert r.status_code == 200, r.text
    r = post(f"/quotations/{{q['quotation']}}/execution-authorization"); assert r.status_code == 200, r.text

out = {{}}
if phase == "legacy":
    a = won_quotation("Legacy With Work Order")
    wo = post(f"/quotations/{{a['quotation']}}/work-order"); assert wo.status_code == 201, wo.text
    a["work_order"] = wo.json()["id"]
    b = won_quotation("Legacy Won Without Work Order")
    out = {{"A": a, "B": b}}
elif phase == "after_upgrade_checks":
    a, b = state["A"], state["B"]
    out["a_wo_get"] = client.get(f"/quotations/{{a['quotation']}}/work-order", headers=H).status_code
    out["a_payments"] = client.get(f"/work-orders/{{a['work_order']}}/payment-summary", headers=H).status_code
    out["a_status_patch"] = client.patch(f"/work-orders/{{a['work_order']}}", json={{"status": "in_progress"}}, headers=H).status_code
    out["a_draft_blocked"] = post(f"/quotations/{{a['quotation']}}/agreement").status_code
    out["b_wo_blocked_before"] = post(f"/quotations/{{b['quotation']}}/work-order").status_code
elif phase == "start_b_and_new_c":
    b = state["B"]
    p5_ready(b)
    wo = post(f"/quotations/{{b['quotation']}}/work-order"); out["b_wo_after_flow"] = wo.status_code
    c = won_quotation("Post-P5 Client"); p5_ready(c)
    wo = post(f"/quotations/{{c['quotation']}}/work-order"); out["c_wo"] = wo.status_code
    out["C"] = c
print("DRIVER_JSON=" + json.dumps(out))
'''.format(pw1=PW1, pw2=PW2, email=DIRECTOR_EMAIL)


def drive(backend_dir, phase, state):
    result = subprocess.run(
        [PYTHON, "-c", DRIVER, phase, json.dumps(state)], cwd=backend_dir, env=env_for(backend_dir),
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(result.stdout[-1500:], result.stderr[-2500:])
        raise RuntimeError(f"driver phase {phase} failed")
    line = next(l for l in result.stdout.splitlines() if l.startswith("DRIVER_JSON="))
    return json.loads(line.split("=", 1)[1])


def adopt(confirm):
    args = [PYTHON, os.path.join(BACKEND_DIR, "scripts", "p5_adopt_legacy_work_orders.py")]
    if confirm:
        args += ["--confirm", "--actor-email", DIRECTOR_EMAIL]
    return subprocess.run(args, cwd=BACKEND_DIR, env=env_for(BACKEND_DIR), capture_output=True, text=True)


def counts():
    return {
        "projects": scalar("SELECT count(*) FROM projects"),
        "quotations": scalar("SELECT count(*) FROM quotations"),
        "work_orders": scalar("SELECT count(*) FROM work_orders"),
    }


def main():
    legacy_ids = None
    try:
        create_check_database()
        make_worktree()
        head_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=WORKTREE, capture_output=True, text=True).stdout.strip()
        record("pre-P5 worktree is the P4-merged main commit", head_commit == PRE_P5_COMMIT, head_commit)

        up = run_alembic(["upgrade", PRE_P5_REVISION])
        record("database migrated to the revision immediately BEFORE P5", up.returncode == 0, up.stderr[-300:])
        record("no P5 tables exist yet", scalar("SELECT count(*) FROM information_schema.tables WHERE table_name = ANY(%s)",
                                               (list(P5_TABLES) + ["p5_migration_marker"],)) == 0)
        seed(OLD_BACKEND)
        legacy = drive(OLD_BACKEND, "legacy", {})
        legacy_ids = legacy
        before = counts()
        record("legacy data created by the OLD code: 2 Won quotations, exactly 1 Work Order",
               before["quotations"] == 2 and before["work_orders"] == 1, str(before))
        legacy_wo_created_at = scalar("SELECT created_at FROM work_orders")

        up = run_alembic(["upgrade", "head"])
        record("P5 Alembic upgrade applies cleanly to a database holding legacy data", up.returncode == 0, up.stderr[-400:])
        record("legacy rows preserved untouched by the migration", counts() == before, f"{counts()} vs {before}")
        record("all six P5 tables exist and start EMPTY",
               all(scalar(f"SELECT count(*) FROM {t}") == 0 for t in P5_TABLES))
        indexes = {r[0] for r in sql("SELECT indexname FROM pg_indexes WHERE tablename = ANY(%s)",
                                     (["agreements", "project_team_members", "project_execution_authorizations"],))}
        record("the three partial unique indexes exist",
               {"uq_agreements_one_current_per_quotation", "uq_project_team_members_one_active_per_user",
                "uq_execution_authorizations_one_authorized_per_quotation"} <= indexes)
        marker = scalar("SELECT deployed_at FROM p5_migration_marker")
        record("marker row written once and is not older than the legacy Work Order", marker is not None and marker >= legacy_wo_created_at,
               f"{marker} >= {legacy_wo_created_at}")
        try:
            sql("INSERT INTO p5_migration_marker (id, deployed_at) VALUES (2, now())")
            second_marker_refused = False
        except Exception:
            second_marker_refused = True
        record("a second marker row is refused by the single-row CHECK", second_marker_refused)

        down = run_alembic(["downgrade", "-1"])
        record("clean downgrade of the still-EMPTY P5 schema succeeds", down.returncode == 0, down.stderr[-300:])
        record("...and drops all seven P5 tables, legacy rows intact",
               scalar("SELECT count(*) FROM information_schema.tables WHERE table_name = ANY(%s)", (list(P5_TABLES) + ["p5_migration_marker"],)) == 0
               and counts() == before)
        up = run_alembic(["upgrade", "head"])
        record("re-upgrade succeeds and writes a fresh marker", up.returncode == 0 and scalar("SELECT count(*) FROM p5_migration_marker") == 1)
        marker = scalar("SELECT deployed_at FROM p5_migration_marker")

        checks = drive(BACKEND_DIR, "after_upgrade_checks", legacy)
        record("legacy Work Order, payments and status routes still work after the upgrade",
               checks["a_wo_get"] == 200 and checks["a_payments"] == 200 and checks["a_status_patch"] == 200, str(checks))
        record("a new Agreement cannot be drafted over a quotation that already has a Work Order",
               checks["a_draft_blocked"] == 409)
        record("the Won-without-Work-Order quotation is blocked in the adoption window",
               checks["b_wo_blocked_before"] == 409)

        dry = adopt(False)
        record("adoption DRY RUN writes nothing", dry.returncode == 0 and scalar("SELECT count(*) FROM agreements") == 0, dry.stdout[-300:])
        done = adopt(True)
        record("adoption --confirm succeeds", done.returncode == 0, (done.stdout + done.stderr)[-500:])
        rows = sql("SELECT quotation_id::text, status FROM agreements")
        record("exactly ONE legacy_adopted row: the quotation that has a Work Order",
               rows == [(legacy["A"]["quotation"], "legacy_adopted")], str(rows))
        record("the Won-without-Work-Order quotation was NOT adopted (no bypass)",
               scalar("SELECT count(*) FROM agreements WHERE quotation_id = %s", (legacy["B"]["quotation"],)) == 0)
        again = adopt(True)
        record("a repeat run adopts nothing and changes nothing",
               again.returncode == 0 and scalar("SELECT count(*) FROM agreements") == 1 and "'adopted': 0" in again.stdout, again.stdout[-200:])

        final = drive(BACKEND_DIR, "start_b_and_new_c", legacy)
        record("the Won-without-Work-Order project starts only after Agreement + team + authorization",
               final["b_wo_after_flow"] == 201, str(final))
        record("a brand-new post-P5 quotation completes the same flow end to end", final["c_wo"] == 201)
        eligible_run = adopt(True)
        record("Work Orders created AFTER the migration are never eligible for adoption",
               "'eligible': 1" in eligible_run.stdout and "'adopted': 0" in eligible_run.stdout, eligible_run.stdout[-200:])
        record("still exactly one legacy_adopted row", scalar("SELECT count(*) FROM agreements WHERE status = 'legacy_adopted'") == 1)

        populated_before = {t: scalar(f"SELECT count(*) FROM {t}") for t in P5_TABLES}
        down = run_alembic(["downgrade", "-1"])
        refused = down.returncode != 0 and "Refusing to downgrade" in (down.stdout + down.stderr)
        record("downgrade is REFUSED once P5 data exists", refused, (down.stderr or down.stdout)[-300:].replace("\n", " "))
        record("...and nothing was dropped or altered",
               {t: scalar(f"SELECT count(*) FROM {t}") for t in P5_TABLES} == populated_before
               and scalar("SELECT version_num FROM alembic_version") == P5_REVISION)
    finally:
        try:
            drop_check_database()
        except Exception as exc:  # noqa: BLE001
            print("cleanup (database) warning:", exc)
        try:
            remove_worktree()
        except Exception as exc:  # noqa: BLE001
            print("cleanup (worktree) warning:", exc)

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
