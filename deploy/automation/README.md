# Lightsail release automation — production disabled

Codex implements this package; Claude independently reviews it. This PR authorizes preparation only. No production setup, dispatch, first deployment, merge or paid staging resources are authorized. Leave repository `RELEASE_DEPLOY_REQUESTS_ENABLED` and environment `PRODUCTION_DEPLOY_ENABLED` absent, and host `enabled` false.

## Inspected baseline and release contract

Based on main `17a67113c47075a06234f442a198e272e66eaaf5`. Existing deployment builds on the server. Host nginx serves `/var/www/nestaprime/dist`, strips `/api/`, and proxies loopback 8000. Frontend API configuration is compiled; these artifacts use same-origin `/api`. Production Compose uses Postgres 16, persistent project-scoped DB/uploads volumes and protected host `.env`. Inventory every installed override, including scanner/integration configuration. Do not omit overrides or modify the reviewed PR branches.

The backend CMD runs `alembic upgrade head` before gunicorn, so startup can mutate schema/data. Existing nightly backup uses whole-DB SQL/gzip, retains 14 dumps and a best-effort P5 sidecar. Keep that procedure and coordinated uploads/snapshot drills. This helper adds a retained whole-DB custom-format dump; it does not back up uploads or eliminate concurrent writes.

Dispatch only on main with its explicit **current tip**, equal to the dispatch workflow SHA. The latest main push run/attempt of `backend-ci.yml` must pass `test`, `docker-build`, and `dependency-audit`; skipped/neutral are rejected. Check again after approval and immediately before backend replacement. A main advance makes an approved release stale: start a fresh dispatch. Production reruns are forbidden because approval history cannot reliably distinguish attempts. There is no atomic transaction between GitHub's tip and Docker; branch advancement during the final API-to-mutation interval remains a staging/operator consideration.

Preparation builds linux/amd64 once, labels the actual backend image, inventories that image and audits it. Existing advisories block release; this PR adds no exceptions or dependency fixes. Inventory, audit JSON and audit log are uploaded even on rejection. The release contains image ID/archive, exact frontend manifest, audit and CI evidence, and repository/workflow/commit/run metadata. An outer `release.tar` binds all payload bytes. GitHub OIDC/Sigstore attests that outer digest. The host verifies the signed digest, intended repository, main ref, exact workflow, source/signer commit and run/attempt **before extraction**. Self-supplied checksums alone never authorize a release. The exact frontend file set must match the manifest; extra, missing or changed files fail.

Only the same verified image/archive and frontend are used on host. No production build or pull occurs. Workflow concurrency and a nonblocking host flock prevent overlap. Before replacement the helper checks nginx, existing DB access, disk, adopted frontend symlink, candidate migration graph, retained previous image/override and backup. Archive listing sets `backup_readable`; only a successful whole-DB restore into an internal isolated network with matching Alembic revision/P5 marker sets `backup_restore_rehearsed`. Candidate migrations run there and must preserve the marker and reach the candidate head before live backend replacement. A rehearsal does not prove every business-data or concurrent-write recovery scenario.

Backend readiness requires healthy HTTP JSON **and** an actual SQL query through the candidate backend's configured role with the expected schema head. After switching the frontend symlink, HTTPS health and every served frontend file digest must match. A static health response alone cannot pass. Root-protected records retain sanitized step identifiers, failure categories, exit codes, previous release and recovery metadata, never command output or credentials. Keep raw private database artifacts off GitHub. The controller bounds process groups and HTTP child processes, propagates termination/deadline signals past retries, and bounds container-side commands. Execution is at most 900 seconds plus four cleanup operations of at most five seconds each; outer remote and SSH timeouts provide additional bounds. Cleanup failure is recorded for an operator.

## One-time GitHub setup — later, separately authorized administrator

1. Review/merge through the existing process. Protect main with review and all three required CI jobs; restrict force pushes/deletion/bypass. Add automation files to the repository review/CODEOWNERS process. Do not run untrusted jobs on a production-accessible runner.
2. Create environment **production**, choose explicit independent individual reviewers, forbid self-review, disable administrator bypass, and allow exactly one deployment **branch** named main. The helper pins environment ID and reviewer numeric IDs and verifies fresh approval by a listed person other than the triggering actor. Team-only, missing/ambiguous approval and policy drift fail closed.
3. **Enablement blocker:** the environment API must return verifiable `can_admins_bypass: false`. The public REST schema may omit this property. UI attestation alone is not accepted by this package. If the API cannot prove enforcement, keep deployment disabled and obtain a separately reviewed verifiable protection mechanism; do not remove this check or infer permission from an absent field. Verify approval history/read permissions and environment-policy visibility with the intended credentials in staging.
4. Add environment variables `DEPLOY_HOST` and `DEPLOY_USER=nestaprime-deploy`. Leave both enablement variables absent during preparation. Only after staging acceptance and separate live authorization may the administrator set repository `RELEASE_DEPLOY_REQUESTS_ENABLED=explicitly-authorized`, environment `PRODUCTION_DEPLOY_ENABLED=explicitly-authorized`, and host enabled true. All three interlocks are required. The first rejects deployment requests before builds/approval; they do not replace human approval.
5. Add **production environment secrets** `DEPLOY_SSH_KEY` (dedicated private key) and `DEPLOY_KNOWN_HOSTS` (out-of-band verified full known_hosts line). Use the UI or stdin from a protected file, never a literal in commands, source, logs or chat. The workflow uses mode-600 temporary files, explicit identities, strict host checking, no interactive/password fallback, connection/keepalive and command timeouts, and deletes local files on exit.
6. Permit pinned official actions. Prepare/test signing requires `contents:read`, `actions:read`, `id-token:write`, `attestations:write`; deployment requires contents/actions read. No AWS credentials or registry write permission are needed. Repository administrators need environment, variable and secret configuration permissions; operators need Actions write; reviewers need the configured environment eligibility. A separate minimal host read credential must support contents/main, Actions run/jobs/approval history and environment policy reads; use a narrowly scoped GitHub App installation credential with a reviewed renewal mechanism, or an expiring fine-grained token with required read grants. Store only on host in a root-owned mode-600 file. Validate access and expiry without printing the token. Unsupported API permissions block enablement.

## One-time Lightsail setup — later, separately authorized host administrator

Host read credentials need repository **Contents: read** and **Actions: read** (plus mandatory metadata read); no repository write grant is used. Actions read covers environment/branch policy and approval history reads: [environment API](https://docs.github.com/en/rest/deployments/environments#get-an-environment), [branch-policy API](https://docs.github.com/en/rest/deployments/branch-policies#list-deployment-branch-policies), [approval-history API](https://docs.github.com/en/rest/actions/workflow-runs#get-the-review-history-for-a-workflow-run). Environment/branch-policy setup uses administrator authority ([Administration: write](https://docs.github.com/en/rest/deployments/environments#create-or-update-an-environment)). Confirm all endpoint access with the intended credential before enablement; a read grant does not resolve the missing bypass-verification blocker.

Use a trusted Lightsail console and sudo. No commands below have been executed on production. Docker authority is root-equivalent. The workflow needs no AWS IAM permissions; host/firewall setup needs existing instance console and networking authority.

1. Privately inventory Compose project/container labels, all ordered files/working directory, existing DB/uploads volume names, protected `.env`, scanner mounts/settings, x86_64 architecture, nginx paths, HTTPS domain, backups and available disk/RAM for a second Postgres and migration process. Do not print container environments or rendered Compose secrets. Install Python **3.12 or newer**, current GitHub CLI supporting every attestation verification flag, Docker/Compose, nginx, coreutils timeout and sudo. Verify GitHub/Sigstore/TUF egress and trusted public TLS.
2. Create an unprivileged `nestaprime-deploy` user (no docker group), mode-700 home/incoming/.ssh, and root-owned mode-755 `/var/lib/nestaprime/releases`. Install **all four** trusted modules `host_release.py`, `package_release.py`, `environment_gate.py`, `eligibility.py` into `/usr/local/lib/nestaprime-release`, owned root, directories 755/files 644. They must not be deployment-user writable. Install this root-owned mode-755 wrapper as `/usr/local/sbin/nestaprime-release`, using the verified Python path:

```sh
#!/bin/sh
exec /usr/bin/python3 -I /usr/local/lib/nestaprime-release/host_release.py "$@"
```

3. Install root-owned mode-600 `/etc/nestaprime-active-image.yml` initially containing `services: {}`. Insert it last in the exact installed Compose file list; preserve every existing override. Configure other operators/crons to respect the same image override and `/run/lock/nestaprime-release.lock`. Do not invoke legacy `up --build` after adoption.
4. Install a dedicated Ed25519 public key in deployment-user authorized_keys with `restrict`, mode 600. Keep the private half only in the environment secret. Limit TCP22 to approved runner egress; GitHub-hosted IPs vary, so a reviewed isolated ephemeral runner with fixed egress may be needed. Verify host-key fingerprint/public key through trusted Lightsail console (`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`); `ssh-keyscan` alone is not trust. Follow the same process for rotation.
5. Write root-owned mode-600 `/etc/nestaprime-release.json`, substituting reviewed inventory values:

```json
{
  "enabled": false,
  "repository": "Rakesh-Nesta/NestaPrime-Estimator",
  "workflow": ".github/workflows/lightsail-release.yml",
  "source_ref": "refs/heads/main",
  "environment_id": 0,
  "reviewer_ids": [0],
  "github_token_file": "/etc/nestaprime-github-read-token",
  "incoming_root": "/home/nestaprime-deploy/incoming",
  "release_root": "/var/lib/nestaprime/releases",
  "lock_file": "/run/lock/nestaprime-release.lock",
  "compose_project": "ACTUAL_EXISTING_PROJECT",
  "env_file": "/home/ubuntu/NestaPrime-Estimator/.env",
  "compose_files": ["/home/ubuntu/NestaPrime-Estimator/docker-compose.prod.yml", "/etc/nestaprime-active-image.yml"],
  "active_override": "/etc/nestaprime-active-image.yml",
  "frontend_link": "/var/www/nestaprime/dist",
  "nginx_config": "/etc/nginx/nginx.conf",
  "backend_url": "http://127.0.0.1:8000/health",
  "public_url": "https://ACTUAL_DOMAIN",
  "deadline_seconds": 900,
  "health_seconds": 180
}
```

Pin actual environment/reviewer IDs; zero placeholders cannot pass. Put the host GitHub credential only in its protected token file; retain app credentials in the existing protected `.env`. Trust paths/modules/Compose/config must all be administrator-controlled. Allow nginx traversal to release frontend directories; archives, dumps and records remain mode600.
6. Adopt current `/var/www/nestaprime/dist` as a symlink to a copied root-owned `/var/lib/nestaprime/releases/bootstrap/dist` during separately approved maintenance. Preserve the original directory as `dist.pre-automation`; abort if already a symlink or adoption target exists. Set copied frontend directories755/files644, atomically install the symlink, run nginx validation and compare served HTTPS bytes. Restore original directory on failed validation. This adoption itself changes production and is deferred.
7. Install root-owned mode440 sudoers rule `nestaprime-deploy ALL=(root) NOPASSWD: /usr/local/sbin/nestaprime-release *`, validate with visudo. The isolated root CLI accepts one numeric run-attempt slot and fixed administrator config; no arbitrary config/path/test mode or broad sudo. Verify rejection of malformed arguments, symlinked incoming paths and replayed slots in staging.
8. Establish monitoring/retention for previous/current images, frontend and backups; never prune recovery evidence automatically. Rehearse coordinated DB/uploads restore and ensure resources for internal isolated restore/migration rehearsal. Staging must test actual helper installation, token renewal, SSH identity rejection/disconnects, real public TLS and nginx routing, independent approval/self-review/bypass rejection, stale/retry rejection, concurrency, timeout/resource cleanup and operator recovery after pre/post-mutation failures. Disposable tests do not establish these acceptance conditions. No paid staging resources are authorized here.

## Recovery — separately authorized human decision

Read root-protected `record.json` in the run-attempt directory. It records sanitized failure step/category, whether mutation began, previous image/frontend, database revision/marker and backup digest/readability/restore rehearsal. There is no operations.log containing raw output. Stop retries after failed migration, preserve evidence and choose a forward fix or recovery. Never upload dumps or production logs to GitHub.

Only restore the previous application after proving compatibility with the current schema/data. Acquire the shared flock; load retained `previous-backend.tar`; use the recorded image ID in the active image-only override with the exact project/env/files, `up -d --no-build --pull never --no-deps backend`. Restore the recorded previous frontend symlink atomically; verify backend SQL/schema readiness, HTTPS health and previous frontend bytes. Do not recreate volumes or build source.

**Application rollback does not reverse database migrations.** P5 downgrade deliberately preserves its marker and may refuse with data. DB recovery is a separate incident decision with potential lost writes: stop all writers/integrations/crons, take an incident backup, check retained dump hash, rehearse whole-DB restore with `pg_restore --exit-on-error` into disposable Postgres16 and compare revision/marker/business data, then authorize the established whole-database restore procedure and compatible image. Do not delete/invent the marker or restore selected tables. Coordinate uploads snapshots and assess external side effects separately.

## Tests and later automatic trigger

`disposable.sh` builds actual application artifacts and tests migrations, whole-DB restoration and nginx bytes. `test_host_guards.py` tests policy, exact file set, real process-tree/slow-drip deadlines and sanitized diagnostics. `test_host_orchestration.py` executes the actual controller with Docker/Postgres and local TLS nginx, including lock, backups, replacement, switch and failures. Local signing-boundary simulation is explicitly labelled; CI attests test subjects and performs real cryptographic positive/negative verification. CI signer identity is release-safety, never the allowed production workflow. GitHub control-plane responses remain simulated in disposable tests and require real staging acceptance. `legacy_controls.py` preserves the old verifier accepting forged self-checksummed and extra-file payloads.

After staging and explicit authorization, a separate reviewed change may add `workflow_run` for successful completed main-push **Backend CI**, select its exact head SHA and reject if no longer main tip. Refactor the dispatch-only event gate deliberately while preserving independent environment approval, exact eligible source/signer binding and artifact identity; do not simply append a trigger to the current dispatch-only policy. Never execute/download untrusted PR CI artifacts. Automatic live deployment is not enabled.
