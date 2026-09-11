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

1. **Authenticated rescan** -- wire a real JWT into the scan config and rerun against
   `require_roles`-gated routes. This is the gap the "perimeter-only" scope note above exists to
   flag.
2. **HawkScan CLI install** -- revisit once the sandboxing issue is understood; StackHawk's
   platform-tracked triage (NEW/FALSE_POSITIVE/RISK_ACCEPTED lifecycle) is worth having for
   ongoing use, not just a one-off file like this one.
3. Per the blueprint's own Phase 5 checklist, this still isn't the "third-party penetration
   test" it calls for before full rollout -- this is an automated DAST pass, a smaller thing.
