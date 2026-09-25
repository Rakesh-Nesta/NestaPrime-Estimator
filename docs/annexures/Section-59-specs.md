# Section 59 — Amendment No. 55 Spec

## Amendment No. 55 — HTTPS on a Real Domain

### Registered scope
The Director's instruction (25 September 2026): register and spec HTTPS on a real domain -- the last item
from Amendment 48's audit, and the reason the Director's phone cannot open the site. Evidence is in
`docs/annexures/Annexure-2.md`, Amendment No. 55. In short: production is plain HTTP on a bare IP
address. Every login (email and password), every access token and every quotation, rate and client phone
number crosses the network in clear text, nothing at the edge tells a browser to insist on HTTPS, and port
443 is closed, so there is no HTTPS to fall back to. This is an infrastructure change more than a code
change: a domain name, a certificate, an nginx configuration and a cutover that can be undone.

### Governing principles
- **Credentials and business data never travel over plain HTTP.** After the cutover the only thing plain
  HTTP does is send the browser to HTTPS.
- **Reversible at every step.** The old configuration is kept, `nginx -t` runs before every reload, and the
  rollback is written down before the cutover starts, not after.
- **Nothing is guessed.** The domain, who controls its DNS, and where the WhatsApp/Telegram callbacks point
  are the Director's to say or to check; this spec does not invent them.
- **Proved from outside.** As with every deploy, the result is confirmed from what the public internet
  sees (certificate, redirects, headers, the served bundle), not from a pasted terminal.
- **Staged, not all at once.** Strict-Transport-Security starts short and is raised only after the site
  has run cleanly, because a wrong long-lived HSTS cannot be taken back from the browsers that saw it.

### What only the Director can supply or do
1. **A domain name** for the app (proposal: a subdomain of the company's own domain -- for example
   `app.<company domain>` -- rather than buying a new one), and **someone who can add one DNS `A` record**
   pointing it at the server's static IP `65.1.234.78`.
2. **Open TCP port 443** in the Lightsail firewall (Networking tab of the instance). Today `https://` to the
   IP times out, which is a closed port, not a missing certificate. Port 80 stays open.
3. **Say where the WhatsApp/Telegram callbacks point**, if they are configured (they were unset on the
   server on 16 September): a callback aimed at `http://65.1.234.78/...` would be redirected and break.

### Proposed spec

**Part A -- In the repository (one PR; nothing on the server changes until the runbook is followed)**
1. **`deploy/nginx/nestaprime.conf` is rewritten** with `__DOMAIN__` placeholders replaced at install time:
   - port 80: serves the ACME challenge path (`/.well-known/acme-challenge/`) and **redirects everything
     else to `https://__DOMAIN__`** (301); a second port-80 block answers `server_name 65.1.234.78` with a
     301 to the domain, so old bookmarks move;
   - port 443 (`ssl http2`): the certificate from `/etc/letsencrypt/live/__DOMAIN__/`, TLS 1.2 and 1.3
     only, the existing `/api/` reverse proxy (with `X-Forwarded-Proto $scheme`), the SPA fallback and
     `client_max_body_size 100M` exactly as today;
   - response headers on the HTTPS server: `Strict-Transport-Security` (staged, item 4), `X-Content-Type-
     Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`.
   A second file, `deploy/nginx/nestaprime-bootstrap.conf`, is the same site on port 80 only with the ACME
   path and no redirect, used for the one step that must happen before a certificate exists.
2. **The backend trusts the proxy's forwarded headers.** The `gunicorn` command gains
   `--forwarded-allow-ips="*"`. This is safe here because the container's port is published only on
   `127.0.0.1` (nginx is the only client); without it FastAPI cannot tell the request was HTTPS and any
   redirect it builds (a trailing-slash redirect, for example) would point at `http://` and be blocked by
   the browser as mixed content.
3. **Configuration that names the site is updated:** `backend/.env.example`, the `CORS_ORIGINS` line and
   the `VITE_API_URL` build argument in `deploy/README.md` become the `https://` domain, in both the
   first-install steps and the redeploy commands. The README gains the new runbook (item 5) and a short
   "when the certificate cannot renew" section.
4. **HSTS is staged:** `max-age=300` (five minutes) for the first verified run, then raised to
   `max-age=15552000` (180 days) in a one-line follow-up after a week with nothing wrong. No
   `includeSubDomains` and no `preload`, so nothing beyond this one host is committed.
5. **The runbook (user-run on the server, in this order):**
   1. Director: add the DNS record; open port 443; confirm the callback URLs. Confirm the name resolves.
   2. Install certbot; install the **bootstrap** config and reload (only port 80 changes).
   3. Obtain the certificate with the webroot method (`certbot certonly --webroot`); confirm the files.
   4. Set `.env` `CORS_ORIGINS` to the https origin; rebuild the backend (forwarded-headers change).
   5. Install the **final** config (`nginx -t` first) and reload.
   6. Rebuild the frontend with `VITE_API_URL=https://<domain>/api` and copy it (the copy as its own step).
   7. Prove it from outside (below); then `certbot renew --dry-run`; confirm the renewal timer is active.
   Rollback, written first: restore the previous `/etc/nginx/sites-available/nestaprime` (kept as
   `nestaprime.pre-https`), reload, and rebuild the frontend with the old `http://65.1.234.78/api`.
6. **A test pins the nginx reference configuration:** a backend test reads `deploy/nginx/nestaprime.conf`
   and the bootstrap file and asserts the directives that matter -- the 301 to HTTPS, the IP-to-domain
   redirect, TLS 1.2/1.3 only, the four security headers, `X-Forwarded-Proto`, `client_max_body_size
   100M`, the ACME path being reachable over HTTP -- so a later edit cannot silently drop one. (There is
   no nginx in CI; this is a text check, not a syntax check, and `nginx -t` on the server remains the gate.)
7. **A test pins the gunicorn flag** in the `Dockerfile` command in the same way.

**Part B -- Frontend:** none. The API address is a build argument; no source line names the server.

**Sequencing:** one PR for Part A; then the runbook, run by the Director step by step with the output
pasted, each step checked from outside; then a docs-only close-out (register, deploy log).

### Explicitly out of scope
- A web application firewall, rate limiting, a Content-Security-Policy, or a security scan of production
  over HTTPS (worth doing next; separate amendment).
- Changing how login or tokens work (tokens are held in memory, not in cookies, so there are no cookie
  flags to change and no sessions to migrate), or any application code.
- A managed load balancer or CDN, IPv6 (`AAAA`) records, a `www` variant, or several domains.
- Email deliverability for the domain, and alerting on certificate expiry (renewal is automatic and
  dry-run-checked; a monitor is a possible follow-up).
- HTTPS between nginx and the backend container, or for the wa-gateway on the same host (loopback only).
- Retiring the IP: the IP stays the server's address; it only stops serving the app over HTTP.

### Acceptance criteria
- `https://<domain>` serves the app with a certificate that verifies (chain valid, name matches, at least
  60 days left); `http://<domain>` answers `301` to `https://<domain>`; `http://65.1.234.78` answers `301`
  to `https://<domain>`. Checked from outside with `curl` and a TLS probe.
- The HTTPS responses carry `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options` and
  `Referrer-Policy`; HSTS starts at `max-age=300`.
- `https://<domain>/api/health` answers `{"status":"ok"}`; an anonymous call to a protected endpoint
  answers 401; a request with `Origin: http://65.1.234.78` is not granted CORS access.
- A request that makes FastAPI build a redirect (a path with a trailing slash) is redirected to an
  `https://` location, never `http://`.
- In real Chrome as Director and as a Sales rep: login works, no mixed-content or blocked requests appear in
  the console, and the screens verified in Amendments 51-54 open with **zero refused (4xx) calls**; a 2 MB
  logo upload still succeeds (`client_max_body_size` kept).
- The Director opens the site on their phone over mobile data.
- `certbot renew --dry-run` succeeds and the renewal timer is active.
- The two repository tests pass and the existing suite is unaffected.

### Open decisions (proposed defaults)
1. **The domain:** a subdomain of the company's own domain. **Needs the name from the Director** -- and
   confirmation of who can add the DNS record. (Alternative: register a new domain.)
2. **Certificates from Let's Encrypt via certbot (webroot method), renewing automatically.** Proposed:
   **yes.** (Alternatives: a certificate from the cloud provider on a load balancer or CDN -- costs money and
   changes the architecture; or a proxy such as Cloudflare in front -- a third party sees all traffic.)
3. **HSTS staged:** `max-age=300` first, `180 days` after a clean week, no subdomains, no preload.
   Proposed: **yes.**
4. **The bare IP redirects to the domain over HTTP** (301) rather than staying a working plain-HTTP way in.
   Proposed: **yes.**
5. **`--forwarded-allow-ips="*"` on gunicorn** (safe because the port is published on loopback only).
   Proposed: **yes.**
6. **Repository tests that pin the nginx reference config and the gunicorn flag.** Proposed: **yes.**
7. **Check the WhatsApp/Telegram callback targets before the cutover** and repoint any that use the IP.
   Proposed: **yes.**
8. **The runbook order and the written rollback in item 5.** Proposed: **yes.**
9. **Division of work:** the Director does the DNS record and the firewall change and runs the server
   commands, pasting output; I write the configuration and prove each step from outside. Proposed: **yes.**
10. **One PR for the repository files, then the runbook, then a docs-only close-out.** Proposed: **yes.**

### Approval
☑ Approved — "approve as proposed, all decisions" (25 September 2026). **The domain name (decision 1), DNS access, opening port 443 and the callback check are still to be supplied**; the repository work uses a `__DOMAIN__` placeholder, and the server runbook does not start until they are.
☐ Approved with changes (noted above)
☐ Not approved

**Prepared by:** R. Patni (with AI development assistance)
**Date:** 25 September 2026
