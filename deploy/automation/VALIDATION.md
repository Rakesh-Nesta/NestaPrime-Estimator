# Preparation validation — 8 October 2026

Base: main `17a67113c47075a06234f442a198e272e66eaaf5`.

Executed `disposable.sh` in a local Docker CLI container with Docker Desktop's Linux daemon. All infrastructure used unique `np-release-test-*` names and was removed by the script's EXIT trap. No production endpoint, credentials or application data were used.

- Three safety test groups passed: exact main CI eligibility rejects wrong SHA/branch/event, incomplete/failed/skipped/neutral/cancelled checks; altered or incomplete artifact hashes reject; tar traversal/absolute paths/symlinks reject.
- Built actual main backend image, saved/reloaded it and verified unchanged image ID.
- Started actual backend against a disposable Postgres 16 database; startup Alembic migrations completed and HTTP health returned `ok`.
- Dumped entire database in custom format; restored into a second disposable Postgres 16 instance with error-stop. Alembic revision and original P5 marker matched.
- Built actual frontend for `/api`, served it from disposable nginx, and compared served index bytes.
- Ran the exact real-image inventory audit command separately. It failed closed with seven reported advisories in two installed distributions (`pip` and `python-jose`), with only the existing ecdsa exception ignored. Release preparation is blocked on that audited image; no dependency fixes or additional exceptions were made.
- Python 3.12 safety tests/syntax, Bash syntax, actionlint (including ShellCheck), and staged whitespace validation passed.

An initial Windows sandbox-only invocation hit temporary-directory ACL errors; the same tests passed in the Linux disposable harness. GitHub API and Docker became reachable with approved execution outside the sandbox. Official action tag commits were resolved through GitHub API and pinned.

Limits: production helper orchestration, real SSH authentication/host-key rejection, protected-environment approval and actual public TLS/frontend asset checks have not been exercised on a staging host. Required staging acceptance remains before deployment enablement. Existing Backend CI and the new disposable CI run are separate GitHub results; local tests do not assert main is currently eligible. Real-image dependency audit is fail-closed and may prevent a release because of existing advisories. No exception or unrelated dependency implementation was changed.
