# ClamAV release candidate

This change builds on the Compose passthrough in PR #281. It installs only
`clamdscan` in the backend image. The scanner engine runs separately, with a
4 GiB memory limit, one CPU, one scan thread and four total queued/active jobs.
The backend must not receive the Docker socket. It streams files over the
dedicated `nestaprime_clamav_socket` Unix-socket volume instead.

Apply `deploy/docker-compose.scan-client.yml` after `docker-compose.prod.yml`.
The override explicitly requires scanning and selects the client command; it
does not depend on the host `.env` to enable that requirement. Keep the backend
port on loopback. The normal backend command runs Alembic on startup: do not
start it against production until the migration rehearsal and backup gates pass.

## Scanner configuration and identity

`deploy/clamav/clamd.conf` is the exact 20-line configuration provisioned on the
new server on 2026-10-03. No TCP socket is configured. Use this daemon image:

`clamav/clamav@sha256:ebec5bc138401b36ae987caa1a3fa3c3b2a21ed3d51f0bfa5852825e663e67b0`

This image reported ClamAV 1.5.4. Signatures in the persistent volume were
updated separately to daily version 28142. These are observed identities, not
permanent freshness guarantees. The scanner's current manual container has no
automatic restart policy or signature-update schedule. Both need operational
configuration and verification before release. Its default image healthcheck
may refer to a different socket; use the configured socket when checking health.

`ConcurrentDatabaseReload no` avoids loading a second engine during reload;
scans can block during that period. `AlertExceedsMax yes` makes supported limit
exceedances a refusal, not a claim that partial inspection is clean. This does
not establish complete inspection of every format or bound every parser's CPU
time. The scanner's 400 MiB expanded-data limit may refuse a compressed document
that passes the application's separate format validation.

## Evidence and verification boundary

Observed on the new server, before connecting the app: daemon PONG, harmless
text accepted (exit 0), EICAR detected (exit 1). The temporary test files were
removed. Idle memory was 946.2 MiB; host available memory 6.1 GiB. Neither this
reading nor these two scans prove capacity under combined CRM/DB/PDF load.

Run `python scripts/verify_clamav_connection.py` explicitly inside the candidate
backend image with the scanner socket mounted. Override the normal container
command so this check runs no migration. It exercises the real upload inspection
code for clean acceptance, EICAR refusal/quarantine and missing-socket refusal.
All test files and quarantine stay in a temporary directory; no database or
production upload storage is used. This is not an HTTP endpoint test.

The existing application translates scanner exit 0 to acceptance, exit 1 to a
422 quarantine refusal, and other exits/timeouts to 503. The resumable completion
and ordinary upload paths still need verification through HTTP with the built
image. Session creation/chunk writes do not scan and are not a maintenance gate.

Before cutover: verify the image build and client/server compatibility; inspect
the effective Compose configuration without printing secrets; exercise actual
HTTP clean/infected/unavailable behavior; establish scanner restart and signature
update monitoring; test concurrent uploads/PDFs/DB activity, including signature
updates; rehearse migrations on a restored production copy; preserve coordinated
backups and verify frontend/backend release identity. The old live server is
unchanged by this candidate.
