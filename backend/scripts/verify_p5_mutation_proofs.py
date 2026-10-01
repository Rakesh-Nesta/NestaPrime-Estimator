"""Mutation proofs: break one P5 safeguard at a time, confirm the targeted tests FAIL, then restore the file
(git checkout) and confirm the working tree is clean. Proves the acceptance tests detect a broken protocol
rather than passing vacuously. Exit codes are read directly from each pytest subprocess (no pipes).

Run from backend/ with a CLEAN working tree (it restores each mutated file with `git checkout --`):
    .venv/Scripts/python.exe scripts/verify_p5_mutation_proofs.py"""
import os
import subprocess
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(BACKEND, ".venv", "Scripts", "python.exe")

MUTATIONS = [
    ("M1 row locks removed from the generic lock helper (Project/Quotation/Agreement/User/Attachment rows)",
     "app/core/p5.py", "        .order_by(model.id)\n        .with_for_update()\n", "        .order_by(model.id)\n",
     "tests/test_p5_concurrency.py -k \"ac14 or ac20 or ac13\""),
    ("M2 account change no longer revalidates its discovered memberships under the User lock",
     "app/core/p5.py", "        if _discover_site_engineer_projects(db, user_id) <= candidates:\n", "        if True:\n",
     "tests/test_p5_concurrency.py -k \"ac29c_assignment or retry_limit\""),
    ("M3 team assignment no longer rechecks that the assignee is active",
     "app/core/p5.py", "    if user is None or not user.is_active:\n", "    if user is None:\n",
     "tests/test_p5_agreement_execution.py tests/test_p5_concurrency.py -k \"ac21 or ac29b\""),
    ("M4 signed-evidence guard removed from the generic attachment-supersede route",
     "app/core/p5_agreements.py", "    if is_evidence is not None:\n", "    if False:\n",
     "tests/test_p5_agreement_execution.py tests/test_p5_concurrency.py -k \"ac16 or ac17\""),
    ("M5 one-way invalidation rule removed (an invalidated authorization can be revived)",
     "app/models/p5.py", "    if previously_invalidated and target.status == AuthorizationStatus.AUTHORIZED:\n", "    if False:\n",
     "tests/test_p5_agreement_execution.py -k ac30"),
    ("M6 Work Order creation no longer requires execution authorization",
     "app/api/work_orders.py", "        p5.require_work_order_authorization(db, quotation, scope)\n", "        pass\n",
     "tests/test_p5_agreement_execution.py -k \"ac01 or ac02 or ac03 or ac04\""),
    ("M7 voiding an Agreement no longer invalidates the bound authorization",
     "app/core/p5_agreements.py", '    p5.invalidate_authorization(db, agreement.quotation_id, "Agreement voided", actor, request)\n', "",
     "tests/test_p5_agreement_execution.py tests/test_p5_concurrency.py -k \"ac10 or ac14\""),
    ("M8 account deactivation no longer triggers the P5 protocol (users.py hook)",
     "app/api/users.py", "        account_change_projects = p5.lock_for_account_change(db, user.id)\n", "        account_change_projects = []\n",
     "tests/test_p5_agreement_execution.py tests/test_p5_concurrency.py -k \"ac18 or ac28\""),
]


def run(cmd):
    return subprocess.run(cmd, cwd=BACKEND, capture_output=True, text=True, shell=True)


bad = []
for name, path, old, new, selector in MUTATIONS:
    full = BACKEND + "\\" + path.replace("/", "\\")
    text = open(full, encoding="utf-8").read()
    assert text.count(old) == 1, (name, text.count(old))
    open(full, "w", encoding="utf-8", newline="").write(text.replace(old, new))
    try:
        result = run(f'"{PY}" -m pytest {selector} -q -p no:cacheprovider -x')
        failed_line = next((l for l in result.stdout.splitlines() if l.startswith("FAILED")), "")
        summary = next((l for l in reversed(result.stdout.splitlines()) if "passed" in l or "failed" in l or "error" in l), "")
    finally:
        run(f'git checkout -- "{path}"')
    detected = result.returncode != 0
    print(f"{'DETECTED' if detected else 'NOT DETECTED'} | {name}\n    pytest-exit={result.returncode} | {failed_line[:150]} | {summary}")
    if not detected:
        bad.append(name)
status = run("git status --short backend").stdout.strip()
print("\nworking tree after all restores:", repr(status))
print("undetected mutations:", bad)
sys.exit(1 if bad or status else 0)
