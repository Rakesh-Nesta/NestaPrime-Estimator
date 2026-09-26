# Section 61 — Amendment No. 58 Spec

## Amendment No. 58 — Application Security Hardening

### Registered scope
The Director's question (26 September 2026): "what about app security". The app is live on the internet at
`https://app.nestaprime.in` and holds client, pricing, cost and margin data. This amendment closes the
gaps a review of the code and the live server found, and adds the checks that would have caught them. Evidence
is in `docs/annexures/Annexure-2.md`, Amendment No. 58. In short: the basics are sound (HTTPS with HSTS, role
gates on every route with the role read from the database on every request, a login lockout, Argon2 password
hashes, CORS limited to the one origin, the database and the backend not reachable from outside, `npm audit`
clean), but there is **no Content-Security-Policy, no request throttling on the server, public API docs pages,
sessions that survive a password change, no record of lockouts, an unfiltered attachment upload, and no
dependency scanning** -- and the only security scan on record (11 September, unauthenticated, API only) predates
most of the amendments and endpoints in the app today.

### Governing principles
- **Change nothing a user does.** Nobody's workflow, role or screen changes. The two visible effects are a
  one-time sign-in after the deploy (item 5) and a longer minimum password (item 7).
- **Roll out so it can be undone.** Server-side items are one nginx configuration file (reinstalled the way
  the HSTS change was, with the previous file kept); nothing here needs a database migration.
- **Prove it in a real browser and against the real server.** A security header that breaks a screen is worse
  than none, so the Content-Security-Policy ships only after every screen has been opened per role with zero
  violations, and each server change is verified from outside.
- **A guard beats a promise.** Where a rule matters ("every route needs a login"), a test enforces it so a
  future amendment cannot quietly break it.
- **Honest scope.** This is hardening plus an authenticated automated scan. It is **not** the third-party
  penetration test the blueprint's Phase 5 calls for, and it says so in its results.

### Proposed spec

**Part A -- Web server (nginx; one configuration file, no rebuild, no migration)**
1. **Content-Security-Policy and related headers** on the app and the API: `default-src 'self'`; scripts from
   `'self'` only; styles from `'self'`, Google Fonts (`fonts.googleapis.com`) and inline styles (React's
   `style` attributes need it); fonts from `fonts.gstatic.com`; images from `'self'`, `data:` and `blob:`;
   `connect-src 'self'`; `object-src 'none'`; `base-uri 'self'`; `form-action 'self'`;
   `frame-ancestors 'none'`. Plus `Permissions-Policy` (camera, microphone, geolocation, payment off) and
   `server_tokens off` (the nginx version is currently in every response). Shipped only after item 12's
   browser pass shows no violations on any screen.
2. **Throttling.** A per-address limit on `/api/auth/login` (proposed 10 requests a minute, burst 10) and a
   generous one on the rest of the API (proposed 20 requests a second, burst 40), answering **429**. The
   office shares one public address, so the numbers are set well above what a team logging in at 9 a.m. does.
3. **Request size.** The default body limit falls from 100 MB to 2 MB everywhere except the attachment upload
   routes, which keep 100 MB (M.3) -- the logo (5 MB cap) and the two import routes get a limit that matches
   their own.
4. **API docs pages off.** `/api/docs` and `/api/redoc` answer 404 in production. `/api/openapi.json` stays
   readable (see decision 2).

**Part B -- Backend (code; tests)**
5. **A session ends when the password changes.** The sign-in token carries a short fingerprint of the stored
   password hash; a token whose fingerprint no longer matches is refused (401). A password change or a
   Director's reset therefore ends every existing session for that person. Tokens issued before this ships
   carry no fingerprint and are refused too: **everyone signs in once after the deploy.** Deactivation
   already ends a session at once, and roles are read from the database each request (both checked, both stay).
6. **Record the security events.** An account lockout, and a person changing their own password, are written
   to the existing audit log (no migration). Individual wrong passwords are not written (the throttle bounds
   them and a guessing run must not be able to fill the audit table).
7. **Passwords.** Wherever a password is set (self-service change, Director creating a user, Director reset)
   the minimum becomes **10 characters**, and a new password may not equal the current one or the person's
   email. Existing passwords keep working until changed.
8. **Attachments.** The stored file name is reduced to a plain name (no folders, no odd characters, length
   capped). Types that can run or render as a page are refused with a plain message -- `.html .htm .xhtml
   .svg .js .mjs .exe .msi .bat .cmd .com .scr .ps1 .sh .jar .php .py .vbs .dll .lnk` -- everything else a
   site team really attaches (drawings, photos, PDFs, spreadsheets, video) still uploads. Downloads remain
   forced downloads (they already are).
9. **A guard for every future route.** A test lists every route in the app and fails unless it either
   requires a login (401 without one) or is on a short, written public list (login, health, the API schema,
   and the WhatsApp webhook, which checks its own secret). A new route added without authentication fails CI.

**Part C -- Pipeline and scanning**
10. **Dependency scanning in CI.** `pip-audit` for the Python packages and `npm audit --omit=dev` for the
    front end run on every PR; findings of High/Critical severity fail the build, anything unfixable is
    recorded with the reason in `docs/security/`. A weekly Dependabot configuration for pip, npm, GitHub
    Actions and Docker keeps versions moving.
11. **An authenticated scan.** The 11 September scan never logged in, so it never touched a protected route.
    This amendment scans a local copy **as Director and as Sales** (real tokens, scripted login) with OWASP ZAP,
    and separately runs a role-by-route check against the generated role table (every route, every role: the
    status must match what the table says). Results are written to `docs/security/` as a dated file, with
    what was and was not covered.
12. **Browser pass for the CSP.** Every screen opened as each of the six roles in real Chrome (desktop and
    375px), zero Content-Security-Policy violations and zero refused (4xx) calls, before item 1 is enforced.

**Part D -- Checks on the server itself (read-only commands you run; I read the output)**
13. SSH allows keys only (`PasswordAuthentication no`) -- port 22 is open to the internet; automatic security
    updates are on; the pending kernel restart is done; `.env` is readable by its owner only; the last backup
    is recent and a restore drill is dated. Any finding is reported, and a fix is proposed, not applied.

**Sequencing (one Amendment number, ordered PRs):** PR 1 = Part B + item 10 (backend, tests, CI) -- deploy
is a backend rebuild, no migration, everyone signs in again once. PR 2 = Part A (nginx configuration and its
runbook) -- deploy is reinstalling the configuration file; the CSP goes in only after item 12. PR 3 = items 11
and 13 (scan results and server-check results) as a docs PR. Each is deployed and verified from outside before
the close-out.

### Explicitly out of scope
- **Two-factor sign-in (MFA).** The largest remaining protection against a stolen password, but a feature in
  its own right (enrolment, recovery, roles) -- proposed as its own amendment, not folded in here.
- **Running the backend container as a non-root user.** Worthwhile, but the uploads volume is owned by root
  and a wrong change breaks every upload; it needs its own careful step.
- **Pinning exact package versions** (a lock file) -- changes what the Docker build installs; separate,
  after item 10 shows what is out of date.
- A web application firewall, log shipping, encryption of uploads at rest, single sign-on, or a third-party
  penetration test.
- Any pricing rule, role gate, screen or workflow.

### Acceptance criteria
- From outside: the app and the API answer with a `Content-Security-Policy`, a `Permissions-Policy` and no
  nginx version; `/api/docs` and `/api/redoc` answer 404; 40 wrong logins in a minute from one address end in
  429s while a correct login from a second address still works.
- Every screen, as each of the six roles, at desktop and 375px, opens with zero CSP violations and zero
  refused calls; login, the quotation PDF download, the logo, an attachment upload and the Google font all
  still work.
- Changing a password (self-service or Director reset) makes a token issued before it answer 401; a fresh
  sign-in works; a deactivated user is still refused at once.
- Five wrong passwords lock the account and leave one audit-log entry; an unknown email leaves none.
- A 9-character password is refused everywhere a password is set, a 10-character one accepted, and the same
  or email-equal password refused.
- `../x`, `a/b.pdf` and a very long name are stored as safe plain names; `.html`, `.svg` and `.exe` are refused
  with a plain message; a PDF, JPEG, XLSX and MP4 still upload.
- The all-routes test passes today and fails if a route is added without a login (shown by a throwaway
  route in a check, not left in the code).
- CI runs both audits; the authenticated scan and the role-by-route check are in `docs/security/`, with any
  finding fixed or written down.
- The existing backend suite passes.

### Open decisions (proposed defaults)
1. **Content-Security-Policy enforced** (not report-only), after the browser pass. Proposed: **yes.**
   (There is nowhere to send violation reports, so testing every screen first is the safeguard.)
2. **`/api/openapi.json` stays public**; only the two docs pages are hidden. Proposed: **keep public.**
   Every route behind it needs a login, and deploy checks and the scan use it; hiding it would add little.
   (Alternative: require a Director login for it, and change how deploys are verified.)
3. **Login throttle 10 a minute, API 20 a second, per address.** Proposed: **yes**, adjustable in one file.
4. **Everyone signs in once after the backend deploy** (item 5). Proposed: **yes**, done at a quiet time.
5. **Minimum password 10 characters.** Proposed: **yes.** (Alternative: keep 8.)
6. **Attachments: refuse risky types (deny-list)** rather than allow only a fixed list. Proposed: **deny-list**,
   so no site file type is ever blocked by surprise. (Alternative: an allow-list -- stricter, more support calls.)
7. **Failed-password attempts are not written to the audit log; lockouts are.** Proposed: **yes.**
8. **CI fails on High/Critical dependency findings.** Proposed: **yes**, with unfixable ones recorded, not
   ignored. (Alternative: report only.)
9. **Two-factor sign-in and the non-root container are separate amendments, not part of this one.**
   Proposed: **yes.**
10. **Ordered PRs** (backend and CI, then nginx, then scan results). Proposed: **yes.**

### Approval
☑ Approved — "approve as proposed, all decisions" (26 September 2026)
☐ Approved with changes (noted above)
☐ Not approved

**Prepared by:** R. Patni (with AI development assistance)
**Date:** 26 September 2026
