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

## Readiness correction for Claude's independent review

Codex is the implementer; Claude is the independent reviewer for this package. The earlier `REVIEW_READY for Codex` handoff was incorrect.

Original head `27198b1af2f6df83630caf11f2bb81389891b23c` has **failed**, not pending, release-safety CI: PR run `37719725434`, inspected job `113124367634`; push run `37719720497`. Both logs show curl exit 56 (connection reset) immediately after nginx image startup. The frontend request used `--retry-connrefused`, which does not retry that reset. Timing is consistent with nginx startup readiness; original container state/logs were not captured, so the server-side cause cannot be established conclusively from that run.

Preserved original logs and run/job metadata are in `evidence/`; logs retain timestamps/content with terminal ANSI formatting removed. They are disposable CI output, not production logs. The original head remains reachable; do not rerun it in place of preserving failure evidence.

Correction replaces the backend/frontend readiness requests with `wait_http.py`: per-request timeout, monotonic overall deadline, bounded response size, content validation, and a useful terminal failure reason. Frontend readiness requires exactly the built index bytes, and the existing independent `cmp` assertion remains. Backend readiness requires HTTP 200 and JSON `status=ok`, followed by the final JSON assertion. DB readiness now has a final successful `pg_isready` assertion. Failed disposable execution prints container state and bounded log/build tails before cleanup and preserves the nonzero exit status; cleanup errors cannot turn failure into success.

Focused execution: eight safety/readiness tests passed in Python 3.12, including real local HTTP reset/recovery, persistent reset, wrong frontend, unhealthy health JSON, 503 and stalled-server deadline tests. The full disposable Docker run passed real image reload identity, migrations/health (nine readiness attempts), whole-database restore including matching P5 marker/revision, and nginx frontend byte comparison. The first local run emitted a Python 3.14 HTTPError resource warning; error responses are now explicitly closed and the finalized Python 3.12 run is clean. Execution transcripts are preserved in `evidence/correction-*.log`.

Intermediate PR run `37720452280` on evidence-only head `9bf59391494f67003437f462ae95c55f740317ed` exposed a diagnostic assertion race: a request at the deadline could overwrite the established wrong-content error with a generic timeout. Readiness still rejected the service, but the useful cause was lost. Its job/run evidence is also retained. The helper now retains the last substantive service failure across timeout exhaustion, and a deterministic mocked-clock regression forces that exact boundary. The final suite has nine tests; positive readiness tests allow two seconds so scheduler jitter cannot masquerade as a service failure. The original eight-test suite was also repeated five times while correcting the issue. Final Python 3.12 and full disposable transcripts are separately named `correction-final-*.log`.

This correction does not modify dependency files, audit logic/exceptions, deployment workflow, production helper, or #293/#294. The previously observed actual-image vulnerability blocker remains separate. Exact correction-head GitHub results are recorded in the PR handoff after completion; local passing tests do not stand in for those results. Staging limitations above still apply.
