# Security baseline -- 2026-09-11

First DAST + secrets scan run against this app. No record of either existed before this
(confirmed via `.github/workflows/`, `stackhawk.yml`, and this repo's own history -- see the
blueprint audit note in the main README). Run ahead of the AWS deploy so there's a documented
baseline in place, not because a specific incident prompted it.

## Scope -- read this before trusting any "clean" claim below

**Unauthenticated, spec-driven, API-only.** No JWT was wired into the scan. Every
`require_roles`-gated endpoint returned 401 and was not meaningfully exercised beyond that --
this is a **perimeter scan**, not a full authenticated pass. "0 findings" below means "0
findings among what an anonymous caller can reach," not "every endpoint is secure." A follow-up
authenticated scan (real JWT, scripted login) is still needed to test business-logic-level
issues on protected routes (authorization bypass, IDOR, injection reachable only after login) --
tracked as a real gap, not implied-away by this scan's clean result.

The frontend (React SPA) was not scanned -- out of scope for this pass; the backend API is the
higher-value DAST target per standard SPA-scanning guidance (a client-rendered app has no server
logic of its own to probe).

## Tooling note

The StackHawk `hawk` CLI (the org's standard DAST tool, via the `hawkscan` skill) could not be
installed in this environment -- the Windows MSI reported success but never deployed a runnable
binary (no install location, no PATH entry; this session's sandbox appears to block real file
deployment from MSI installs). Fell back to the community OWASP ZAP Docker image
(`ghcr.io/zaproxy/zaproxy:stable`) instead, specifically `zap-api-scan.py` (OpenAPI-spec-driven,
not the plain spider-based `zap-baseline.py`, which found almost nothing against this app --
a pure JSON API has no HTML homepage to spider from). Findings here are not tracked in any
platform triage system; this file is the only record.

## DAST result: `zap-api-scan.py` against `/openapi.json`

- Target: `http://localhost:8000` (dev), 205 spec-imported URLs / 488 total URLs covered
- Active scan (real payloads, not passive-only): SQLi, XSS, RCE, SSRF, XXE, path traversal,
  template injection, and ~60 other rule families -- all passed clean, no instances
- Initial run: **2 Low findings**, both on public unauthenticated endpoints
  (`/openapi.json`, `/health`):
  - `X-Content-Type-Options Header Missing` [10021]
  - `Cross-Origin-Resource-Policy Header Missing or Invalid` [90004]
- **Fixed same day**: added a small response-header middleware in
  [`backend/app/main.py`](../../backend/app/main.py) (`security_headers`) setting
  `X-Content-Type-Options: nosniff` and `Cross-Origin-Resource-Policy: same-origin` on every
  response
- Rescan: **0 Low, 0 Medium, 0 High, 0 Critical** -- [full report](zap-api-scan-2026-09-11.html)
  (this is the post-fix report; the pre-fix report showing the 2 original findings was not kept,
  since the fix and rescan happened in the same session)

## Secrets sweep: `gitleaks`

- **Git history** (all 101 commits, ~2.47 MB scanned): **0 leaks**
- **Working directory** (uncommitted + vendored files): 62 matches, all inside
  `backend/.venv/` -- third-party SQLAlchemy source code where keyword arguments like
  `is_mixin_scan=True` trip gitleaks' entropy heuristic on the word "scan"/"api"/"key" appearing
  near an `=True`. Not real secrets, not this project's code. No findings in any file this repo
  actually tracks.

## Open follow-ups (not closed by this scan)

1. **Authenticated rescan -- DONE 26 September 2026, see the last section.** (Original note: wire a real JWT into the scan config and rerun against
   `require_roles`-gated routes. This is the gap the "perimeter-only" scope note above exists to
   flag.)
2. **HawkScan CLI install** -- revisit once the sandboxing issue is understood; StackHawk's
   platform-tracked triage (NEW/FALSE_POSITIVE/RISK_ACCEPTED lifecycle) is worth having for
   ongoing use, not just a one-off file like this one.
3. Per the blueprint's own Phase 5 checklist, this still isn't the "third-party penetration
   test" it calls for before full rollout -- this is an automated DAST pass, a smaller thing.


## Amendment 58 (Section 61): authenticated scans and the role-by-route check -- 26 September 2026

This closes open follow-up 1 above (the authenticated rescan). It is still an automated pass, not the third-party
penetration test in follow-up 3.

**What was scanned.** The running app (this repository's code with Amendment 58's backend changes) against a
throwaway copy of the development database, so a scanner fuzzing write routes could not touch real data.
OWASP ZAP `zap-api-scan.py`, driven by `/openapi.json` (269 imported URLs), with a real sign-in token sent on every
request, as **Director** and as **Sales**. The password and token are for local test accounts and appear in none of
the reports.

| Scan | Failures | Warnings | Passes | Report |
| --- | --- | --- | --- | --- |
| Director, before the fix | 0 | 4 | 116 | [before-fix](zap-authenticated-director-2026-09-26-before-fix.md) |
| Director, after the fix | 0 | 3 | 117 | [after-fix](zap-authenticated-director-2026-09-26.md) |
| Sales | 0 | 2 | 118 | [sales](zap-authenticated-sales-2026-09-26.md) |

(The pre-fix report is kept this time; the 11 September one was not.)

**What it found.** One real defect, fixed in #237: about 270 raw 500 responses on `POST /settings`,
`/vehicle-classes`, `/netting-grades`, `/sports`, `/scope-items`, `/hubs` and two bulk routes when a text value was
longer than its database column or contained a NUL character (ZAP's "Server Error" and "Format String Error" rules).
Not exploitable (queries are parameterised) and nothing was half-saved; one app-wide handler now answers 422. After
the fix: no 500s, and the "Format String Error" warning is gone. The warnings that remain, all reviewed and left:
- *Server Error x2*: `/education/ask` answers 503 when no AI key is configured -- the app's deliberate "not
  configured, fail fast" behaviour.
- *Unexpected Content-Type*: the logo, the audit-log and quotation CSV exports and the like return files ZAP did
  not expect to see; informational.
- *Timestamp Disclosure*: a number in `/dashboard` that looks like a Unix time; not sensitive.

**What it cannot tell you.** 96% of the requests were refused for bad input and about 2% succeeded: the scan builds
its requests from the API description, not from real records, so almost every id it sends does not exist. It is good
at injection-type flaws, unhandled errors and headers; it is **not** able to tell whether one person can read or
change another's project or client (broken object-level authorisation), or to exercise multi-step business rules.
That is what a person, or a third-party penetration test, is for.

**Role-by-route check** (`backend/scripts/role_route_check.py`; local or test copies only -- it calls every write
route). It reads the Director's role table (`GET /role-permissions`, generated from the live routes) and calls each
gated route as each of the six roles: a role the table admits must not get 401 or 403, one it does not admit must get
exactly 403, and anonymous calls must get 401. Result on 26 September 2026: **247 gated routes, 642 admitted calls, 840
refused calls, 247 anonymous, 24 sign-in-only -- the table and the server agree on every one.** Deliberately mislabelling
a role produced 97 mismatches, so the check does discriminate. It sees the gate on the route, not checks made inside
a route.

**Also in force from Amendment 58:** `pip-audit` and `npm audit` in CI (one accepted exception, see
[dependency-audit-exceptions.md](dependency-audit-exceptions.md)), a test that fails if any route is added without a
login, and the web-server changes described in `deploy/README.md`.

**Server checklist (item 13), run by the Director on 26 September 2026 -- findings; fixes recommended, not yet applied.**
- **SSH: good.** `passwordauthentication no`, `pubkeyauthentication yes`, `kbdinteractiveauthentication no`,
  `maxauthtries 6`. `permitrootlogin without-password` means root can sign in with a key only; setting it to `no` is
  optional tidiness. Port 22 is open to the internet, but only keys are accepted.
- **Automatic updates: on.** `Update-Package-Lists "1"`, `Unattended-Upgrade "1"`, service active (whether it may
  reboot by itself was not checked).
- **A reboot is pending**: `/var/run/reboot-required` lists `linux-image-7.0.0-1012-aws`, `linux-image-7.0.0-1013-aws`,
  `linux-base` and `libc6`. The server is running an older kernel and libc than are installed. A reboot restarts every
  container, so it belongs at a quiet time, after checking the containers come back by themselves.
- **`.env` is world-readable.** Mode `664` (owner and group can write, everyone can read) on `.env` and
  `.env.pre-https`. They hold the token secret, the database password and the service keys. On a one-user server the
  practical risk is small, but no other account has any reason to read them: `chmod 600` on both.
- **No nightly backup is scheduled -- the most important finding.** `crontab -l` prints "no crontab for ubuntu" and
  `~/nestaprime-backups/` holds a single dump, `nestaprime_estimator_20260915T062410Z.sql.gz` (24,757 bytes, the restore
  drill's). The cron line in `deploy/README.md` ("Backups & restore drill") was never installed, so there has been no
  database dump since 15 September. Lightsail's own snapshot schedule was not visible from here (console only) and
  may be covering it; that is unconfirmed. Install the cron line, then confirm a fresh dump appears.
- **Listening ports:** 22, 80 and 443 on all interfaces; the backend on `127.0.0.1:8000` only; PostgreSQL not
  published on the host; local-only `127.0.0.1:38725` (not identified -- most likely a Docker component) and the local
  resolver on port 53; IPv6 only on 22.

**Follow-up, 26 September 2026 (the Director's output).**
- *Backups: fixed.* The cron line is installed (`crontab -l` shows `0 2 * * * .../deploy/backup_db.sh >> .../backup.log`)
  and a manual run wrote a fresh dump (`nestaprime_estimator_20260926T055832Z.sql.gz`, 38 KB). The first scheduled dump
  is still to be seen on 27 September. The dumps are on the same disk, so they cover a bad deploy or deleted data, not
  loss of the instance; that is the Lightsail snapshot's job and its schedule has not been checked.
- *`.env` mode: fixed.* `600` on `.env` and `.env.pre-https`, confirmed with `stat`.
- *Reboot: done, but the flag remains -- open.* The server rebooted and came back correctly (checked from outside), yet
  `uname -r` reports `6.17.0-1019-aws` and `/var/run/reboot-required` still exists, whereas the flag originally listed
  `linux-image-7.0.0-1012-aws` and `-1013-aws`. Not established whether later updates re-created the flag or an older
  kernel booted. To settle it: `uptime -s; ls -l --time-style=long-iso /var/run/reboot-required; cat
  /var/run/reboot-required.pkgs; dpkg -l 'linux-image-*' | awk '/^ii/{print $2, $3}'`. If the flag is newer than the boot
  time, another reboot at a quiet moment clears it; if a newer kernel is installed than the one running, the boot
  loader's default needs a look. No exposure is known either way: every check from outside passes.
