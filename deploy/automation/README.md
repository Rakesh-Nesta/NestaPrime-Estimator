# Lightsail release automation (preparation only)

No production setup or deployment is authorized by this PR. Merge and infrastructure setup require the usual separate decisions. The first production release requires explicit authorization in addition to the GitHub environment review. Dispatch with `deploy=false` by default; leave `PRODUCTION_DEPLOY_ENABLED` absent during preparation.

## Inspected baseline

Based on main `17a67113c47075a06234f442a198e272e66eaaf5`. Existing `deploy/README.md` builds backend and frontend on the server. Host nginx serves `/var/www/nestaprime/dist`, strips `/api/`, and proxies loopback port 8000. The frontend API URL is compiled in; this pipeline uses same-origin `/api`. Production Compose uses Postgres 16, persistent project-scoped database/uploads volumes, host `.env`, and optional scanner/WhatsApp/Telegram settings. `deploy/docker-compose.scan-client.yml` exists on reviewed branches but is absent on this main baseline: do not merge those branches here. Inventory the actually installed overrides during later setup and include them, in order, in host configuration. Never silently drop scanner socket mounts or environment settings.

The Docker CMD runs `alembic upgrade head` before gunicorn. Startup may change schema/data and can fail. Existing backup script uses whole-DB SQL/gzip, checks gzip integrity, retains 14 dumps, and has a best-effort P5 sidecar. New deployment uses a separate whole-DB custom-format dump, checks `pg_restore --list`, records its hash and current Alembic revision, and preserves it without automatic pruning. This is an archive integrity check, not proof of restorability: the disposable test actually restores a dump and compares the original P5 marker. Keep nightly backups and snapshot/restore drills; this dump does not back up attachments or eliminate writes after its point in time.

## Release contract

Only dispatch on `main`, with a full 40-character ancestor of fetched main. The most recent main **push** run of `backend-ci.yml`, including its latest attempt, must succeed, with `test`, `docker-build`, and `dependency-audit` all successful (skipped/neutral do not pass). These are the inspected mandatory CI jobs; protect main with these checks and update the explicit allowlist if CI changes. CI is checked again after approval. Failed current advisories block preparation; this PR does not fix dependencies or extend exceptions.

Preparation builds linux/amd64 once, labels the image with the commit, inventories installed distributions from that actual image, and audits the inventory with the existing documented PYSEC-2026-1325 exception only. The image ID, saved image archive hash, frontend archive/file hashes, CI evidence and audit report are uploaded together. GitHub artifact v4 provides immutable per-run artifacts; download comes only from the same run/attempt, never a caller-supplied run. Production loads that image archive and verifies ID and label. It extracts the frontend safely and verifies every file before switching the nginx directory symlink. No source checkout, rebuild, image pull, DB recreation, nginx configuration edit or automatic application rollback occurs on production.

One workflow concurrency group serializes preparation/approval/deployment without cancellation; a nonblocking host `flock` also excludes manual helper overlap. Deployment checks existing containers/DB health, nginx configuration, at least 5 GiB free disk, and the adopted symlink. It saves the previous image and frontend path, completes the backup, recreates only backend with `--no-build --pull never --no-deps`, confirms the running image ID, checks backend and public HTTPS health, release marker, index hash and every served JS/CSS hash. Failures stop and retain a host record; migration or post-switch failure requires an operator. There is a brief availability window between backend restart and frontend switch. Runner job and per-command timeouts bound execution; no background remote release is launched.

## Exact one-time GitHub setup (later, authorized administrator)

1. Review/merge this PR. Repository administrator must confirm the plan supports required environment reviewers for this repository's visibility. For private repositories, check the applicable GitHub Enterprise capability; do not proceed with an unprotected environment.
2. Settings → Branches/rulesets: protect `main`, require PR review and the three CI jobs above, block force pushes/deletion and restrict bypass. Add deployment automation paths to the repository's existing CODEOWNERS/review process.
3. Settings → Environments → create **production** deliberately. Add at least one independent required reviewer, enable **Prevent self-review**, disable administrator bypass, and select deployment branches/tags with exactly one **branch** rule named `main` (no tag rule). The workflow checks reviewer/self-review/branch protections after approval and refuses otherwise. Administrator bypass must be verified in the UI by the administrator: the public REST schema does not reliably expose it.
4. Add environment variables `DEPLOY_HOST` (verified DNS name/static IP) and `DEPLOY_USER=nestaprime-deploy`. Leave `PRODUCTION_DEPLOY_ENABLED` absent. Only after separately authorizing the first live release set it to `explicitly-authorized`. This value is an operational interlock, not a substitute for approval.
5. Add **environment secrets**, never repository-wide secrets: `DEPLOY_SSH_KEY` (dedicated private key) and `DEPLOY_KNOWN_HOSTS` (verified full OpenSSH known_hosts line for that exact host). Enter using GitHub UI or `gh secret set --env production NAME < protected-file`; never command-line secret literals, chat, tickets, source, echoed shell variables or debug tracing. Securely erase the local key copy after placement. The workflow writes temporary mode-600 files, uses BatchMode/StrictHostKeyChecking, and deletes them on exit.
6. Settings → Actions: enable Actions, permit the pinned official actions. Workflow token needs only `contents:read` and `actions:read`; no packages write, AWS credential, PAT or OIDC is used. Administrators configuring environments/secrets need repository administration/environments/secrets write access. Dispatch operators need Actions write; reviewers need environment review eligibility. The API environment inspection may require read access to environments; verify this during a preparation run before enabling deployment.

## Exact one-time Lightsail setup (later, authorized host administrator)

Use Lightsail's trusted console session; this PR does not run these commands. This is a privileged deployment principal: Docker access is root-equivalent, and its uploaded images can execute application code. Protect the dedicated key accordingly. No AWS IAM permission is needed by the release workflow. An operator performing setup needs access to this instance's trusted SSH console and sudo; firewall changes require Lightsail instance networking permissions.

1. Inventory the running Compose project and files from container labels (`com.docker.compose.project`, `.project.config_files`, `.project.working_dir`) privately on host. Confirm exact DB/upload volume names, active overrides, architecture `x86_64`, nginx root, HTTPS domain, backup storage, host env ownership and scanner settings. If any differs, adapt/review setup before proceeding. Never print container environment or rendered `docker compose config` into CI/chat. Keep the original checkout/project and `.env`; configure absolute paths below.
2. Install Python >=3.12, Docker/Compose v2, nginx, `util-linux`/flock and CA certificates. Validate `docker compose version`, `nginx -t`, and external HTTPS certificate renewal. Do not replace production nginx configuration with this PR.
3. Create principal and directories:

```bash
sudo useradd --create-home --shell /bin/bash nestaprime-deploy
sudo install -d -o nestaprime-deploy -g nestaprime-deploy -m 700 /home/nestaprime-deploy/incoming /home/nestaprime-deploy/.ssh
sudo install -d -o root -g root -m 755 /var/lib/nestaprime/releases
# From the separately reviewed automation checkout:
sudo install -o root -g root -m 755 deploy/automation/host_release.py /usr/local/sbin/nestaprime-release
sudo install -o root -g root -m 600 /dev/null /etc/nestaprime-active-image.yml
sudo sh -c 'printf "services: {}\n" > /etc/nestaprime-active-image.yml'
```

4. Generate a dedicated Ed25519 key on a secure administrator workstation with `ssh-keygen -t ed25519 -f <protected-path>`; do not reuse the Lightsail default instance key. Install only the public key into `/home/nestaprime-deploy/.ssh/authorized_keys`, prefixed with `restrict` (disable forwarding/PTY), ownership nestaprime-deploy and mode 600. Keep the private half solely in the production environment secret. Permit inbound TCP 22 only from the chosen runner network: GitHub-hosted runner addresses vary; prefer an isolated ephemeral runner with a fixed egress IP and change `runs-on` through review. Do not run untrusted PR jobs on a production-accessible runner.
5. Verify the host key through the trusted Lightsail console: `sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`. Obtain the public key there; create `<DEPLOY_HOST> ssh-ed25519 <public-key>` locally, compare its fingerprint out of band, then store as `DEPLOY_KNOWN_HOSTS`. `ssh-keyscan` alone does not establish trust. Key rotation requires the same verification.
6. Write root-owned mode-600 `/etc/nestaprime-release.json`, with actual approved values (no secrets in this JSON):

```json
{
  "deploy_user": "nestaprime-deploy",
  "release_root": "/var/lib/nestaprime/releases",
  "compose_project": "ACTUAL_EXISTING_PROJECT",
  "env_file": "/home/ubuntu/NestaPrime-Estimator/.env",
  "compose_files": ["/home/ubuntu/NestaPrime-Estimator/docker-compose.prod.yml", "/etc/nestaprime-active-image.yml"],
  "frontend_link": "/var/www/nestaprime/dist",
  "public_url": "https://ACTUAL_DOMAIN",
  "active_override": "/etc/nestaprime-active-image.yml"
}
```

Insert every existing production override before the active-image file. Compose files, host config and helper must be administrator-controlled, never writable by the deployment user. Keep application credentials in the existing protected host `.env`, not GitHub. Restrict reads to current approved owners. Ensure nginx can traverse the release directory; private archives/logs/records remain mode 600.

7. Adopt the currently served directory under an approved maintenance window (abort if already a symlink; never overwrite a previous adoption):

```bash
sudo test -d /var/www/nestaprime/dist
sudo test ! -L /var/www/nestaprime/dist
sudo test ! -e /var/lib/nestaprime/releases/bootstrap
sudo install -d -m 755 /var/lib/nestaprime/releases/bootstrap
sudo cp -a /var/www/nestaprime/dist /var/lib/nestaprime/releases/bootstrap/dist
sudo find /var/lib/nestaprime/releases/bootstrap/dist -type d -exec chmod 755 {} +
sudo find /var/lib/nestaprime/releases/bootstrap/dist -type f -exec chmod 644 {} +
sudo mv /var/www/nestaprime/dist /var/www/nestaprime/dist.pre-automation
sudo ln -s /var/lib/nestaprime/releases/bootstrap/dist /var/www/nestaprime/dist
sudo nginx -t
```

Verify HTTPS index/assets against the preserved directory. Restore the original directory if adoption verification fails. This setup itself changes production and is explicitly deferred.

8. Install `/etc/sudoers.d/nestaprime-release` root-owned mode 440 with `nestaprime-deploy ALL=(root) NOPASSWD: /usr/local/sbin/nestaprime-release *`; validate with `sudo visudo -cf /etc/sudoers.d/nestaprime-release`. The root-owned helper accepts exactly one numeric run-attempt argument and fixed root-owned config; no arbitrary path or shell command. Do not grant broad sudo or docker group membership.
9. Verify backups/snapshots including uploads and restoration drills; ensure disk retention/monitoring for release archives. Keep at least previous/current artifacts and required recovery dumps. Configure manual maintenance/crons to use the same active image override and coordinate through the host lock; existing cron commands that only exec are unchanged. Never issue legacy `up --build` after adopting releases.

## Recovery (human decision, separately authorized)

Read the root-protected `record.json` and `operations.log` under `/var/lib/nestaprime/releases/<run>-<attempt>`. The record is written before mutations and includes previous image ID, previous frontend target, DB revision, and backup hash. Never upload raw logs or DB dump to GitHub. On failed migrations preserve evidence, stop retries and decide whether a forward fix or database recovery is appropriate. No automatic downgrade or restore occurs.

An application rollback is permissible only after confirming old application compatibility with the current schema/data. Acquire `/run/lock/nestaprime-release.lock` with `flock`; restore the retained previous image with `docker load -i previous-backend.tar`, create an image-only override containing the recorded previous image ID, and run the exact configured Compose project/env/files with that override using `up -d --no-build --pull never --no-deps backend`. Atomically replace the frontend symlink with `previous_frontend`; check backend/public health and the previous index/assets. Set the persistent active-image override to the recovered image. Do not run source builds or `compose down -v`.

**Application rollback does not reverse database migrations.** P5 downgrade intentionally preserves its marker and can refuse when data exists. A DB restore loses writes since the backup and is a separate incident decision: stop all writers (backend plus integrations/crons), take an incident backup, verify the recorded dump hash, restore it into a disposable Postgres 16 instance with `pg_restore --exit-on-error`, confirm Alembic revision and the original P5 marker, then authorize a planned whole-database restore using the established restore runbook and compatible image. Never invent/delete the marker or restore selected tables. Restore uploads from a coordinated snapshot if needed. Assess external messages/side effects separately.

## Tests and later automation

Run `bash deploy/automation/disposable.sh` on a Docker-capable Linux machine. It creates uniquely named containers/network, runs the release safety/readiness tests, builds and reloads the real backend image, exercises migrations/health, restores a real whole-database dump and compares its Alembic revision/P5 marker, and verifies the built frontend served by nginx. HTTP readiness uses per-request timeouts and monotonic deadlines (backend 180 seconds, frontend 60 seconds; an in-flight read can consume at most its additional two-second request timeout). It requires the expected healthy JSON or exact built frontend bytes; exhaustion fails and prints container state and bounded log tails before cleanup. Trap cleanup removes only this test's containers/network/image. Production helper/SSH/environment approval and real TLS are separate staging acceptance checks before enablement; no first live deployment is implied by local passes. Codex implements this package; Claude reviews it independently.

Later, after staging acceptance and explicit authorization, a reviewed change can add `workflow_run` for `Backend CI` with `types: [completed]`, restrict to `main` push/same repository/success, and select **that event's head_sha**, never moving main. Use the same eligibility gate, immutable artifacts, production environment approval, and lock. Do not download artifacts or execute code from untrusted PR CI. Automatic live deployment is not enabled in this PR.

References: [GitHub environments and protections](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments), [workflow run API](https://docs.github.com/en/rest/actions/workflow-runs), [reviewing deployments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/review-deployments).
