#!/usr/bin/env python3
"""Root-installed release controller. CLI accepts only a numeric run-attempt slot."""
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import time

# The installed directory is administrator-owned; isolated Python ignores user paths.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from package_release import FILES, digest
from environment_gate import validate_environment, validate_approval
from eligibility import validate


class ReleaseFault(Exception):
    def __init__(self, category, code=None):
        self.category, self.code = category, code


class Deadline(BaseException):
    """Not caught by retry loops or ordinary command-error handling."""


class Interrupted(BaseException):
    pass


def require(condition, category="integrity"):
    if not condition:
        raise ReleaseFault(category)


def path_name(name):
    p = PurePosixPath(name)
    require(not p.is_absolute() and ".." not in p.parts and "\\" not in name and ":" not in name)
    require(not any(ord(char) < 32 for char in name))
    return p.as_posix().removeprefix("./")


def extract_frontend(archive, dest, allowed=None):
    with tarfile.open(archive) as bundle:
        members = bundle.getmembers()
        require(len(members) < 10000 and sum(m.size for m in members) < (512 * 1024**2 if allowed is None else 2 * 1024**3))
        seen, files = set(), set()
        for member in members:
            name = path_name(member.name)
            require(name not in seen and (member.isfile() or member.isdir()))
            seen.add(name)
            if member.isfile():
                files.add(name)
            if allowed is not None:
                require(member.isfile() and name in allowed)
        if allowed is not None:
            require(files == allowed)
        bundle.extractall(dest, members=members, filter="data")


def verify_bundle(root):
    entries = {}
    for line in (root / "SHA256SUMS").read_text().splitlines():
        value, name = line.split("  ", 1)
        require(re.fullmatch(r"[0-9a-f]{64}", value) and name in FILES and name not in entries)
        entries[name] = value
    require(entries.keys() == FILES)
    require(all(digest(root / name) == value for name, value in entries.items()))
    sha, image, image_id = [(root / name).read_text().strip() for name in ("commit", "image-tag", "image-id")]
    require(re.fullmatch(r"[0-9a-f]{40}", sha))
    require(re.fullmatch(r"nestaprime-release:" + sha + r"-[0-9]+-[0-9]+", image))
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", image_id))
    require(json.loads((root / "eligibility.json").read_text())["commit"] == sha)
    return sha, image, image_id


def verify_frontend(root, manifest):
    entries = json.loads(manifest.read_text())
    require(isinstance(entries, dict) and 0 < len(entries) < 10000)
    require(all(path_name(name) == name and name != "." and re.fullmatch(r"[0-9a-f]{64}", value)
                for name, value in entries.items()))
    files = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    require(files == entries.keys(), "frontend-file-set")
    require(all(not (root / name).is_symlink() and digest(root / name) == value for name, value in entries.items()), "frontend-digest")
    return entries


class Runner:
    """Bound every process tree. Raw stdout/stderr are never release diagnostics."""
    def __init__(self, cfg, event):
        self.cfg, self.event = cfg, event
        self.end = time.monotonic() + cfg.get("deadline_seconds", 900)
        self.env = {"PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin", "LC_ALL": "C.UTF-8", "GH_PROMPT_DISABLED": "1"}
        # Give gh/TUF a private administrator-controlled cache, without inheriting
        # the caller's GitHub config, credential helpers or home directory.
        home = str(Path(cfg.get("release_root", "/var/empty")))
        self.env.update(HOME=home, GH_CONFIG_DIR=home + "/.gh-config", XDG_CACHE_HOME=home + "/.gh-cache")
        if cfg.get("github_token_file"):
            self.env["GH_TOKEN"] = Path(cfg["github_token_file"]).read_text().strip()
        if cfg.get("tls_ca_file"):
            self.env["SSL_CERT_FILE"] = cfg["tls_ca_file"]

    def remaining(self):
        remaining = self.end - time.monotonic()
        if remaining <= 0:
            raise Deadline()
        return remaining

    def run(self, step, args, *, timeout=300, capture=False, output=None, input_file=None, category="command-exit"):
        self.event(step, "started")
        process = None
        with tempfile.TemporaryFile() as captured:
            try:
                process = subprocess.Popen(args, env=self.env, start_new_session=True,
                    stdin=input_file or subprocess.DEVNULL, stdout=output or (captured if capture else subprocess.DEVNULL), stderr=subprocess.DEVNULL)
                try:
                    process.wait(timeout=min(timeout, self.remaining()))
                except subprocess.TimeoutExpired:
                    if time.monotonic() >= self.end:
                        raise Deadline()
                    raise ReleaseFault("command-timeout")
                require(process.returncode == 0, category)
                if capture:
                    require(captured.tell() <= 4 * 1024**2, "output-limit")
                    captured.seek(0)
                    result = captured.read()
                else:
                    result = b""
                self.event(step, "completed")
                return result
            except ReleaseFault as fault:
                if process is not None and process.poll() is not None:
                    fault.code = process.returncode
                    if fault.code == 124:
                        fault.category = "command-timeout"
                    if fault.category == category and category == "http-response":
                        fault.category = {31: "http-status", 32: "tls-verification", 33: "network-connect", 34: "http-timeout"}.get(process.returncode, category)
                self.event(step, "failed", fault.category, fault.code)
                raise
            finally:
                if process is not None:
                    # kill the entire group even if a parent exited leaving children.
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()

    def fetch(self, step, url, *, timeout=5):
        # Run network I/O in a bounded process: slow-drip responses cannot extend
        # socket timeouts indefinitely or swallow the controller deadline.
        code = """import sys,ssl,urllib.request,urllib.error
try:
 with urllib.request.urlopen(sys.argv[1],timeout=2) as r:
  if r.status!=200: sys.exit(31)
  sys.stdout.buffer.write(r.read(4194305))
except urllib.error.HTTPError: sys.exit(31)
except urllib.error.URLError as e:
 sys.exit(32 if isinstance(e.reason,ssl.SSLCertVerificationError) else 34 if isinstance(e.reason,TimeoutError) else 33)
except TimeoutError: sys.exit(34)
"""
        return self.run(step, [sys.executable, "-I", "-c", code, url], timeout=timeout, capture=True, category="http-response")

    def cleanup(self, args):
        # Resource cleanup has a separate small bound after an interrupted operation.
        process = None
        try:
            process = subprocess.Popen(args, env=self.env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, start_new_session=True)
            return process.wait(timeout=5) == 0
        except (OSError, subprocess.SubprocessError):
            return False
        finally:
            if process is not None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()


class GithubPolicy:
    def __init__(self, cfg, runner):
        self.cfg, self.runner = cfg, runner

    def api(self, path):
        code = "import json,os,sys,urllib.request; h={'Accept':'application/vnd.github+json'}; t=os.environ.get('GH_TOKEN'); h.update({'Authorization':'Bearer '+t} if t else {}); r=urllib.request.urlopen(urllib.request.Request(sys.argv[1],headers=h),timeout=10); sys.stdout.write(r.read().decode())"
        return json.loads(self.runner.run("github.read", [sys.executable, "-I", "-c", code,
            "https://api.github.com/repos/" + self.cfg["repository"] + path], capture=True, timeout=15, category="eligibility-unavailable"))

    def tip(self):
        return self.api("/git/ref/heads/main")["object"]["sha"]

    def check(self, sha, slot):
        require(self.tip() == sha, "eligibility-stale")
        runs = self.api("/actions/workflows/backend-ci.yml/runs?event=push&branch=main&head_sha=" + sha)["workflow_runs"]
        require(runs, "eligibility-checks")
        run = max(runs, key=lambda item: item["id"])
        jobs = self.api(f'/actions/runs/{run["id"]}/attempts/{run["run_attempt"]}/jobs?per_page=100')["jobs"]
        try:
            validate(run, jobs, sha, self.cfg["repository"])
            env = self.api("/environments/production")
            reviewers = validate_environment(env, self.api("/environments/production/deployment-branch-policies")["branch_policies"])
            require(reviewers == set(self.cfg["reviewer_ids"]), "approval-policy-drift")
            run_id, attempt = slot.split("-")
            release = self.api("/actions/runs/" + run_id)
            require(release["head_sha"] == sha and release["event"] == "workflow_dispatch" and release["head_branch"] == "main", "approval-run")
            require(release["run_attempt"] == int(attempt) and release["path"].split("@")[0] == self.cfg["workflow"], "approval-run")
            # Approval history does not reliably identify attempts/timestamps.
            # Require a fresh dispatch rather than reusing an earlier approval.
            require(int(attempt) == 1, "approval-rerun-forbidden")
            require(release["head_repository"]["full_name"] == self.cfg["repository"], "approval-run")
            require(env["id"] == self.cfg["environment_id"], "approval-policy-drift")
            # Fresh API approval for this exact run/attempt, not a bundle claim.
            validate_approval(self.api("/actions/runs/" + run_id + "/approvals"), env["id"], release["triggering_actor"]["id"], reviewers)
        except (AssertionError, KeyError):
            raise ReleaseFault("eligibility-or-approval") from None


GRAPH = """import json,sys
from alembic.config import Config
from alembic.script import ScriptDirectory
s=ScriptDirectory.from_config(Config('/app/alembic.ini'))
heads=s.get_heads(); known={r.revision for r in s.walk_revisions()}
current=json.loads(sys.argv[1]); assert len(heads)==1 and current and set(current)<=known
print(json.dumps(heads))
"""
MIGRATE = "from alembic import command; from alembic.config import Config; command.upgrade(Config('/app/alembic.ini'),'head')"
DATABASE_READY = """import json,sys
from sqlalchemy import create_engine,text
from app.config import settings
with create_engine(settings.database_url,connect_args={'connect_timeout':2,'options':'-c statement_timeout=2000'}).connect() as c:
 assert c.execute(text('SELECT 1')).scalar()==1
 assert sorted(c.execute(text('SELECT version_num FROM alembic_version')).scalars())==json.loads(sys.argv[1])
"""


class Release:
    def __init__(self, cfg, slot, *, github=None, runner_type=Runner):
        require(re.fullmatch(r"[0-9]+-[0-9]+", slot), "slot")
        self.cfg, self.slot = cfg, slot
        self.root = Path(cfg["release_root"]) / slot
        self.record = {"slot": slot, "status": "starting", "step": "initialization", "events": [], "mutation_started": False}
        self.runner = runner_type(cfg, self.event)
        self.github = github or GithubPolicy(cfg, self.runner)
        self.docker = cfg.get("docker", "/usr/bin/docker")
        self.compose = [self.docker, "compose", "--project-name", cfg["compose_project"], "--env-file", cfg["env_file"]]
        for file in cfg["compose_files"]:
            self.compose += ["-f", file]
        self.resources = []

    def save(self):
        path = self.root / "record.json.tmp"
        path.write_text(json.dumps(self.record, indent=2))
        path.chmod(0o600)
        path.replace(self.root / "record.json")

    def event(self, step, result, category=None, code=None):
        self.record["step"] = step
        entry = {"step": step, "result": result}
        if category:
            entry["category"] = category
        if code is not None:
            entry["exit_code"] = code
        self.record["events"].append(entry)
        self.save()

    def dc(self, step, *args, **kwargs):
        return self.runner.run(step, self.compose + list(args), **kwargs)

    def exec(self, step, container, *args, **kwargs):
        budget = max(1, math.ceil(min(kwargs.get("timeout", 300), self.runner.remaining())))
        return self.runner.run(step, [self.docker, "exec", "-i", container, "timeout", str(budget), *args], **kwargs)

    def snapshot(self):
        parent = os.open(self.cfg["incoming_root"], os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            folder = os.open(self.slot, os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            try:
                require(set(os.listdir(folder)) == {"release.tar", "attestation.json"}, "bundle-file-set")
                for name in ("release.tar", "attestation.json"):
                    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
                    with os.fdopen(fd, "rb") as source, open(self.root / name, "xb") as dest:
                        info = os.fstat(source.fileno())
                        require(stat.S_ISREG(info.st_mode) and info.st_size < 2 * 1024**3, "bundle-file-type")
                        shutil.copyfileobj(source, dest)
            finally:
                os.close(folder)
        finally:
            os.close(parent)

    def authenticate(self, sha):
        cfg = self.cfg
        result = self.runner.run("provenance.verify", [cfg.get("gh", "/usr/bin/gh"), "attestation", "verify", str(self.root / "release.tar"),
            "--bundle", str(self.root / "attestation.json"), "--repo", cfg["repository"],
            # Exact certificate identity already binds repository/workflow/ref.
            # gh forbids combining it with the shorthand --signer-workflow.
            "--cert-identity", "https://github.com/" + cfg["repository"] + "/" + cfg["workflow"] + "@" + cfg.get("source_ref", "refs/heads/main"),
            "--source-ref", cfg.get("source_ref", "refs/heads/main"), "--source-digest", sha, "--signer-digest", sha,
            "--cert-oidc-issuer", "https://token.actions.githubusercontent.com", "--deny-self-hosted-runners",
            "--predicate-type", "https://slsa.dev/provenance/v1", "--format", "json"], capture=True, category="authenticity")
        invocation = "https://github.com/" + cfg["repository"] + "/actions/runs/" + self.slot.replace("-", "/attempts/")
        require(any(item["verificationResult"]["statement"]["predicate"]["runDetails"]["metadata"]["invocationId"] == invocation
            and any(subject["digest"].get("sha256") == digest(self.root / "release.tar") for subject in item["verificationResult"]["statement"]["subject"])
            for item in json.loads(result)), "provenance-run-or-digest")

    def state(self, container):
        revision = self.exec("database.revision", container, "psql", "-U", "nestaprime", "-d", "nestaprime_estimator", "-Atc",
            "SELECT version_num FROM alembic_version ORDER BY version_num", capture=True).decode().splitlines()
        require(revision and all(re.fullmatch(r"[a-zA-Z0-9_]{1,100}", item) for item in revision), "database-revision")
        exists = self.exec("database.marker-exists", container, "psql", "-U", "nestaprime", "-d", "nestaprime_estimator", "-Atc",
            "SELECT to_regclass('public.p5_migration_marker') IS NOT NULL", capture=True).strip()
        marker = None
        if exists == b"t":
            marker = self.exec("database.marker", container, "psql", "-U", "nestaprime", "-d", "nestaprime_estimator", "-Atc",
                "SELECT id::text || ':' || deployed_at::text FROM p5_migration_marker ORDER BY id", capture=True).decode().splitlines()
            require(len(marker) == 1 and marker[0].startswith("1:"), "database-marker")
        return {"revisions": revision, "p5_marker": marker}

    def rehearsal(self, backup, db_image, image_id, original, heads):
        prefix = self.cfg["compose_project"] + "-trial-" + self.slot
        network, db, migrator = prefix + "-net", prefix + "-db", prefix + "-migrate"
        self.resources += [("network", network), ("container", db), ("container", migrator)]
        self.runner.run("backup.rehearsal-network", [self.docker, "network", "create", "--internal", network])
        password = secrets.token_hex(24)
        env = self.root / "rehearsal.env"
        env.write_text("POSTGRES_USER=nestaprime\nPOSTGRES_DB=nestaprime_estimator\nPOSTGRES_PASSWORD=" + password + "\nDATABASE_URL=postgresql+psycopg://nestaprime:" + password + "@db:5432/nestaprime_estimator\nSECRET_KEY=" + secrets.token_hex(32) + "\nENVIRONMENT=production\n")
        self.runner.run("backup.rehearsal-start", [self.docker, "run", "-d", "--name", db, "--network", network, "--network-alias", "db", "--env-file", str(env), db_image])
        # The image's temporary init server listens only on a Unix socket and
        # can report ready before database initialization is finished. Require
        # the final TCP server plus an authenticated query of the target DB.
        ready = "pg_isready -h 127.0.0.1 -U nestaprime -d nestaprime_estimator >/dev/null && psql -U nestaprime -d nestaprime_estimator -Atc 'SELECT 1'"
        self.wait("backup.rehearsal-ready", lambda: require(self.exec("backup.rehearsal-pg-ready", db, "sh", "-c", ready,
            timeout=3, capture=True).strip() == b"1", "readiness"), 60)
        with open(backup, "rb") as source:
            self.exec("backup.restore", db, "pg_restore", "-U", "nestaprime", "-d", "nestaprime_estimator", "--exit-on-error", "--no-owner", "--no-privileges", input_file=source, category="backup-restore")
        require(self.state(db) == original, "backup-restored-state")
        self.record["backup_restore_rehearsed"] = True
        self.save()
        budget = str(max(1, math.ceil(min(240, self.runner.remaining()))))
        self.runner.run("migration.rehearsal", [self.docker, "run", "--name", migrator, "--network", network,
            "--env-file", str(env), "--entrypoint", "timeout", image_id, budget, "python", "-c", MIGRATE], timeout=240, category="migration-rehearsal")
        migrated = self.state(db)
        require(migrated["revisions"] == heads, "migration-rehearsal")
        if original["p5_marker"] is not None:
            require(migrated["p5_marker"] == original["p5_marker"], "migration-marker")
        self.record["migration_rehearsed"] = True
        self.save()
        env.unlink()

    def wait(self, step, probe, seconds):
        end = min(self.runner.end, time.monotonic() + seconds)
        while time.monotonic() < end:
            self.event(step, "started")
            self.runner.remaining()
            try:
                probe()
                self.event(step, "completed")
                return
            except ReleaseFault as fault:
                # A global Deadline/Interrupted signal is deliberately not caught.
                self.record["last_probe_failure"] = {"step": self.record["step"], "category": fault.category, "exit_code": fault.code}
                self.save()
                if fault.category not in {"command-exit", "http-response", "http-status", "network-connect", "http-timeout", "readiness"}:
                    raise
            time.sleep(min(1, max(0, end - time.monotonic())))
        self.runner.remaining()
        self.event(step, "started")
        raise ReleaseFault({"backend.ready": "backend-readiness", "database.ready": "database-readiness"}.get(step, "readiness"))

    def health(self, step, url, *, timeout=5):
        body = self.runner.fetch(step, url, timeout=timeout)
        try:
            require(json.loads(body).get("status") == "ok", "readiness")
        except (ValueError, AttributeError):
            raise ReleaseFault("readiness") from None

    def replacement_ready(self, image_id):
        """Discover even exited replacements; allow restarts within one health budget."""
        end = time.monotonic() + self.cfg.get("health_seconds", 180)

        def budget():
            self.runner.remaining()  # Global deadline/interrupts must propagate.
            remaining = end - time.monotonic()
            require(remaining > 0, "backend-readiness")
            return min(5, remaining)

        while time.monotonic() < end:
            self.event("backend.ready", "started")
            try:
                ids = self.dc("backend.running-container", "ps", "-a", "-q", "backend",
                    capture=True, timeout=budget()).decode().split()
                if not ids:
                    self.record["backend_state"] = {"status": "missing"}
                    self.save()
                    raise ReleaseFault("readiness")
                require(len(ids) == 1 and re.fullmatch(r"[0-9a-f]{12,64}", ids[0]), "backend-identity")
                backend = ids[0]
                # Select only safe scalar fields: never retain Config, Error, logs,
                # environment, command lines or healthcheck output from inspect.
                fields = '[{{json .Image}},{{json .State.Status}},{{json .State.Running}},{{json .State.Restarting}},{{json .State.ExitCode}},{{json .State.OOMKilled}},{{json .RestartCount}}]'
                values = json.loads(self.runner.run("backend.running-image",
                    [self.docker, "inspect", "-f", fields, backend], capture=True, timeout=budget()))
                actual, status, running, restarting, exit_code, oom, restarts = values
                require(status in {"created", "running", "paused", "restarting", "removing", "exited", "dead"}
                    and all(type(v) is bool for v in (running, restarting, oom))
                    and all(type(v) is int for v in (exit_code, restarts)), "backend-state")
                self.record["backend_state"] = {"status": status, "running": running, "restarting": restarting,
                    "exit_code": exit_code, "oom_killed": oom, "restart_count": restarts}
                self.save()
                require(actual == image_id, "backend-identity")
                require(status == "running" and running and not restarting, "readiness")
                self.health("backend.http", self.cfg["backend_url"], timeout=budget())
                self.event("backend.ready", "completed")
                return backend
            except ReleaseFault as fault:
                self.record["last_probe_failure"] = {"step": self.record["step"], "category": fault.category, "exit_code": fault.code}
                self.save()
                if fault.category not in {"readiness", "command-exit", "command-timeout", "http-response",
                        "http-status", "network-connect", "http-timeout", "backend-readiness"}:
                    raise
            time.sleep(min(1, max(0, end - time.monotonic())))
        self.runner.remaining()
        self.event("backend.ready", "started")
        raise ReleaseFault("backend-readiness")

    def execute(self):
        cfg = self.cfg
        self.event("enablement", "started")
        require(cfg.get("enabled") is True, "disabled")
        require(cfg["public_url"].startswith("https://"), "tls-required")
        self.event("lock.acquire", "started")
        lock = open(cfg["lock_file"], "a")
        self.lock = lock
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ReleaseFault("lock-contended") from None
        self.event("bundle.snapshot", "started")
        self.snapshot()
        sha = self.github.tip()
        require(re.fullmatch(r"[0-9a-f]{40}", sha), "eligibility")
        self.authenticate(sha)  # Authenticate outer bytes BEFORE reading bundle claims.
        self.event("bundle.integrity", "started")
        payload = self.root / "payload"
        extract_frontend(self.root / "release.tar", payload, FILES | {"SHA256SUMS"})
        commit, image, image_id = verify_bundle(payload)
        manifest = json.loads((payload / "release.json").read_text())
        require(commit == sha and manifest == {"repository": cfg["repository"], "workflow": cfg["workflow"], "commit": sha,
                "run_id": self.slot.split("-")[0], "run_attempt": self.slot.split("-")[1]}, "provenance-manifest")
        self.record.update(commit=sha, image_id=image_id, authenticated_bundle_sha256=digest(self.root / "release.tar"))
        self.event("eligibility.after-approval", "started")
        self.github.check(sha, self.slot)
        self.event("frontend.integrity", "started")
        frontend = self.root / "dist"
        extract_frontend(payload / "frontend.tar.gz", frontend)
        assets = verify_frontend(frontend, payload / "frontend-files.json")
        require((frontend / "release.txt").read_text().strip() == sha, "frontend-commit")
        self.event("prerequisites", "started")
        require(Path(cfg["frontend_link"]).is_symlink(), "frontend-not-adopted")
        require(shutil.disk_usage(self.root).free > cfg.get("min_disk_bytes", 5 * 1024**3), "disk-space")
        self.runner.run("nginx.config", [cfg.get("nginx", "/usr/sbin/nginx"), "-t", "-c", cfg["nginx_config"]])
        db = self.dc("database.container", "ps", "-q", "db", capture=True).decode().strip()
        backend = self.dc("backend.previous-container", "ps", "-q", "backend", capture=True).decode().strip()
        require(db and backend, "existing-stack")
        self.exec("database.authenticated-ready", db, "psql", "-U", "nestaprime", "-d", "nestaprime_estimator", "-Atc", "SELECT 1")
        original = self.state(db)
        previous = self.runner.run("backend.previous-image", [self.docker, "inspect", "-f", "{{.Image}}", backend], capture=True).decode().strip()
        db_image = self.runner.run("database.image", [self.docker, "inspect", "-f", "{{.Image}}", db], capture=True).decode().strip()
        self.record.update(previous_image_id=previous, previous_frontend=str(Path(cfg["frontend_link"]).resolve()), database_before=original)
        self.save()
        self.runner.run("backend.load", [self.docker, "load", "-i", str(payload / "backend.tar.gz")])
        require(self.runner.run("backend.image-id", [self.docker, "inspect", "-f", "{{.Id}}", image], capture=True).decode().strip() == image_id, "backend-identity")
        require(self.runner.run("backend.image-label", [self.docker, "inspect", "-f", '{{index .Config.Labels "org.opencontainers.image.revision"}}', image_id], capture=True).decode().strip() == sha, "backend-identity")
        graph = cfg["compose_project"] + "-graph-" + self.slot
        self.resources.append(("container", graph))
        graph_budget = str(max(1, math.ceil(min(30, self.runner.remaining()))))
        heads = json.loads(self.runner.run("migration.compatibility", [self.docker, "run", "--name", graph, "--network", "none", "--entrypoint", "timeout", image_id,
            graph_budget, "python", "-c", GRAPH, json.dumps(original["revisions"])], capture=True, timeout=35, category="migration-compatibility"))
        with open(self.root / "previous-backend.tar", "wb") as output:
            self.runner.run("backend.retain-previous", [self.docker, "save", previous], output=output)
        shutil.copyfile(cfg["active_override"], self.root / "previous-active-image.yml")
        backup = self.root / "database.dump"
        with open(backup, "wb") as output:
            self.exec("backup.dump", db, "pg_dump", "-U", "nestaprime", "-Fc", "--no-owner", "--no-privileges", "nestaprime_estimator", output=output, category="backup-dump")
        require(backup.stat().st_size > 0, "backup-empty")
        with open(backup, "rb") as source:
            self.exec("backup.readable", db, "pg_restore", "--list", input_file=source, category="backup-unreadable")
        self.record.update(backup_readable=True, backup_sha256=digest(backup))
        self.save()
        self.rehearsal(backup, db_image, image_id, original, heads)
        self.event("eligibility.before-mutation", "started")
        self.github.check(sha, self.slot)
        require(self.state(db) == original, "database-drift")
        for path in [self.root, frontend, *frontend.rglob("*")]:
            path.chmod(0o755 if path.is_dir() else 0o644)
        override = self.root / "image.yml"
        override.write_text("services:\n  backend:\n    image: " + image_id + "\n")
        self.record.update(status="deploying", mutation_started=True)
        self.event("backend.replace", "started")
        self.runner.run("backend.replace", self.compose + ["-f", str(override), "up", "-d", "--no-build", "--pull", "never", "--no-deps", "backend"], category="backend-replace")
        backend = self.replacement_ready(image_id)
        self.wait("database.ready", lambda: self.exec("database.backend-query", backend, "python", "-c", DATABASE_READY,
            json.dumps(heads), timeout=10), cfg.get("health_seconds", 180))
        self.event("backend.persist-image", "started")
        active = Path(cfg["active_override"] + ".next")
        shutil.copyfile(override, active)
        active.replace(cfg["active_override"])
        self.event("frontend.switch", "started")
        link = Path(cfg["frontend_link"] + ".next")
        link.symlink_to(frontend)
        link.replace(cfg["frontend_link"])
        self.record["frontend_switched"] = True
        self.save()
        public = cfg["public_url"].rstrip("/")
        try:
            self.health("public.health", public + "/api/health")
        except ReleaseFault:
            raise ReleaseFault("public-health") from None
        for name in sorted(assets):
            # Verify EVERY file, including marker and index, with no SPA fallback acceptance.
            require(hashlib.sha256(self.runner.fetch("public.file", public + "/" + name + "?release=" + self.slot)).hexdigest() == assets[name], "served-frontend")
        self.record["status"] = "healthy"
        self.event("release.complete", "completed")

    def run(self):
        os.umask(0o077)
        self.root.mkdir(parents=True, exist_ok=False)
        self.save()
        handlers = {}
        def deadline(_signum, _frame):
            raise Deadline()
        def interrupted(_signum, _frame):
            raise Interrupted()
        for sig in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            handlers[sig] = signal.signal(sig, deadline if sig == signal.SIGALRM else interrupted)
        signal.alarm(max(1, math.ceil(self.cfg.get("deadline_seconds", 900))))
        ok = False
        try:
            self.execute()
            ok = True
        except BaseException as error:
            category = "deadline" if isinstance(error, Deadline) else "interrupted" if isinstance(error, Interrupted) else error.category if isinstance(error, ReleaseFault) else "invalid-input-or-internal"
            self.record.update(status="failed-needs-recovery" if self.record["mutation_started"] else "rejected-before-mutation", failure_category=category)
            self.event(self.record["step"], "failed", category, getattr(error, "code", None))
        finally:
            signal.alarm(0)
            # Only release-owned disposable resources; at most 4 x 5 seconds.
            for kind, name in reversed(self.resources):
                command = [self.docker, "rm", "-f", "-v", name] if kind == "container" else [self.docker, "network", "rm", name]
                self.record.setdefault("cleanup", []).append({"resource": kind, "completed": self.runner.cleanup(command)})
            (self.root / "rehearsal.env").unlink(missing_ok=True)
            self.save()
            if hasattr(self, "lock"):
                self.lock.close()
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
        print("Release verified." if ok else "Release stopped: " + self.record["step"] + " / " + self.record["failure_category"])
        return 0 if ok else 1


def main():
    require(os.geteuid() == 0 and len(sys.argv) == 2, "invocation")
    config = Path("/etc/nestaprime-release.json")
    info = config.stat()
    require(info.st_uid == 0 and info.st_mode & 0o022 == 0, "config-permissions")
    cfg = json.loads(config.read_text())
    require(cfg["repository"] == "Rakesh-Nesta/NestaPrime-Estimator" and cfg["workflow"] == ".github/workflows/lightsail-release.yml", "trust-policy")
    require(cfg.get("source_ref", "refs/heads/main") == "refs/heads/main", "trust-policy")
    require(0 < cfg.get("deadline_seconds", 900) <= 900 and 0 < cfg.get("health_seconds", 180) <= 180, "deadline-config")
    if cfg.get("github_token_file"):
        token_info = Path(cfg["github_token_file"]).stat()
        require(token_info.st_uid == 0 and token_info.st_mode & 0o077 == 0 and stat.S_ISREG(token_info.st_mode), "credential-permissions")
    return Release(cfg, sys.argv[1]).run()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BaseException as error:
        if isinstance(error, SystemExit):
            raise
        print("Release invocation rejected; inspect root-owned configuration.", file=sys.stderr)
        sys.exit(1)
