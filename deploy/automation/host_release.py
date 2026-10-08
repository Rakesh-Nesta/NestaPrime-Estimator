#!/usr/bin/env python3
"""Install root-owned as /usr/local/sbin/nestaprime-release. No remote code execution from bundle."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import time
import urllib.request

FILES = {"backend.tar.gz", "frontend.tar.gz", "frontend-files.sha256", "backend-packages.txt",
         "backend-audit.json", "image-tag", "image-id", "commit", "eligibility.json"}


def digest(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_bundle(root):
    entries = {}
    for line in (root / "SHA256SUMS").read_text().splitlines():
        value, name = line.split("  ", 1)
        assert re.fullmatch(r"[0-9a-f]{64}", value) and name in FILES and name not in entries
        entries[name] = value
    assert entries.keys() == FILES
    assert all(digest(root / name) == value for name, value in entries.items())
    sha = (root / "commit").read_text().strip()
    image = (root / "image-tag").read_text().strip()
    image_id = (root / "image-id").read_text().strip()
    assert re.fullmatch(r"[0-9a-f]{40}", sha)
    assert re.fullmatch(r"nestaprime-release:" + sha + r"-[0-9]+-[0-9]+", image)
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", image_id)
    assert json.loads((root / "eligibility.json").read_text())["commit"] == sha
    return sha, image, image_id


def extract_frontend(archive, dest):
    with tarfile.open(archive) as bundle:
        members = bundle.getmembers()
        assert len(members) < 10000 and sum(m.size for m in members) < 512 * 1024**2
        for member in members:
            p = Path(member.name)
            assert not p.is_absolute() and ".." not in p.parts
            assert member.isfile() or member.isdir(), "Links and special files forbidden"
        bundle.extractall(dest, members=members, filter="data")


def main():
    os.umask(0o077)
    assert os.geteuid() == 0 and len(sys.argv) == 2
    def deadline(_signum, _frame):
        raise TimeoutError("Host release deadline reached")
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(900)
    slot = sys.argv[1]
    assert re.fullmatch(r"[0-9]+-[0-9]+", slot)
    cfg = json.loads(Path("/etc/nestaprime-release.json").read_text())
    lock = open("/run/lock/nestaprime-release.lock", "w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    root = Path(cfg["release_root"]) / slot
    root.mkdir(parents=True, exist_ok=False)
    incoming = Path("/home") / cfg["deploy_user"] / "incoming" / slot
    # Root-owned snapshot; reject symlinks, then validate snapshot rather than mutable upload.
    for name in FILES | {"SHA256SUMS"}:
        fd = os.open(incoming / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        info = os.fstat(fd)
        assert stat.S_ISREG(info.st_mode) and info.st_size < 2 * 1024**3
        with os.fdopen(fd, "rb") as src, open(root / name, "xb") as dst:
            shutil.copyfileobj(src, dst)
    sha, image, image_id = verify_bundle(root)
    log = open(root / "operations.log", "ab")

    def run(args, capture=False, **kwargs):
        return subprocess.run(args, check=True, timeout=300, stdout=subprocess.PIPE if capture else log,
                              stderr=log, **kwargs).stdout

    compose = ["docker", "compose", "--project-name", cfg["compose_project"], "--env-file", cfg["env_file"]]
    for file in cfg["compose_files"]:
        compose += ["-f", file]
    def dc(*args, **kwargs):
        return run(compose + list(args), **kwargs)

    assert cfg["public_url"].startswith("https://")
    assert Path(cfg["frontend_link"]).is_symlink(), "One-time adoption must be complete"
    run(["nginx", "-t"])
    db = dc("ps", "-q", "db", capture=True).decode().strip()
    backend = dc("ps", "-q", "backend", capture=True).decode().strip()
    assert db and backend, "Existing running stack required"
    assert run(["docker", "inspect", "-f", "{{.State.Health.Status}}", db], capture=True).strip() == b"healthy"
    previous = run(["docker", "inspect", "-f", "{{.Image}}", backend], capture=True).decode().strip()
    assert shutil.disk_usage(root).free > 5 * 1024**3, "Need at least 5 GiB free"
    record = {"commit": sha, "image_id": image_id, "previous_image_id": previous,
              "previous_frontend": str(Path(cfg["frontend_link"]).resolve()), "status": "preparing"}
    def save():
        (root / "record.json").write_text(json.dumps(record, indent=2))
    save()
    with open(root / "previous-backend.tar", "wb") as out:
        subprocess.run(
            ["docker", "save", previous], stdout=out, stderr=log, check=True, timeout=300)
    # Whole database custom dump includes Alembic revision and P5 marker. No best-effort sidecar.
    with open(root / "database.dump.tmp", "wb") as out:
        subprocess.run(compose + ["exec", "-T", "db", "pg_dump", "-U", "nestaprime", "-Fc",
            "--no-owner", "--no-privileges", "nestaprime_estimator"], stdout=out, stderr=log, check=True, timeout=300)
    backup = root / "database.dump.tmp"
    assert backup.stat().st_size > 0
    with open(backup, "rb") as inp:
        dc("exec", "-T", "db", "pg_restore", "--list", stdin=inp)
    backup.rename(root / "database.dump")
    record["backup_sha256"] = digest(root / "database.dump")
    record["database_revision"] = dc("exec", "-T", "db", "psql", "-U", "nestaprime", "-d",
        "nestaprime_estimator", "-Atc", "SELECT version_num FROM alembic_version", capture=True).decode().strip()
    record["status"] = "backup-complete"
    save()
    run(["docker", "load", "-i", str(root / "backend.tar.gz")])
    assert run(["docker", "image", "inspect", "-f", "{{.Id}}", image], capture=True).decode().strip() == image_id
    assert run(["docker", "image", "inspect", "-f", '{{index .Config.Labels "org.opencontainers.image.revision"}}', image], capture=True).decode().strip() == sha
    frontend = root / "dist"
    extract_frontend(root / "frontend.tar.gz", frontend)
    run(["sha256sum", "-c", str(root / "frontend-files.sha256")], cwd=frontend)
    assert (frontend / "release.txt").read_text().strip() == sha
    for path in [root.parent, root, frontend, *frontend.rglob("*")]:
        path.chmod(0o755 if path.is_dir() else 0o644) if path == frontend or frontend in path.parents else path.chmod(0o755)
    # Persistent override changes ONLY the backend image; same project, volumes and host env.
    override = root / "image.yml"
    override.write_text("services:\n  backend:\n    image: " + image_id + "\n")
    record["status"] = "deploying"
    save()
    try:
        run(compose + ["-f", str(override), "up", "-d", "--no-build", "--pull", "never", "--no-deps", "backend"])
        running = dc("ps", "-q", "backend", capture=True).decode().strip()
        assert run(["docker", "inspect", "-f", "{{.Image}}", running], capture=True).decode().strip() == image_id
        def fetch(url):
            with urllib.request.urlopen(url, timeout=5) as response:
                return response.read()
        for attempt in range(60):
            try:
                assert json.loads(fetch("http://127.0.0.1:8000/health"))["status"] == "ok"
                break
            except Exception:
                if attempt == 59:
                    raise
                time.sleep(2)
        temp = Path(cfg["frontend_link"] + ".next")
        temp.symlink_to(frontend)
        temp.replace(cfg["frontend_link"])
        public = cfg["public_url"].rstrip("/")
        assert json.loads(fetch(public + "/api/health"))["status"] == "ok"
        assert fetch(public + "/release.txt?release=" + slot).decode().strip() == sha
        assert hashlib.sha256(fetch(public + "/?release=" + slot)).hexdigest() == digest(frontend / "index.html")
        # Verify every served JS/CSS artifact, rather than only the SPA fallback.
        for asset in frontend.rglob("*"):
            if asset.is_file() and asset.suffix in {".js", ".css"}:
                assert hashlib.sha256(fetch(public + "/" + asset.relative_to(frontend).as_posix())).hexdigest() == digest(asset)
        record["status"] = "healthy"
        save()
        shutil.copyfile(override, cfg["active_override"])
        print("Release healthy; protected recovery record retained on host.")
    except Exception:
        record["status"] = "failed-needs-operator-recovery"
        save()
        raise


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # No raw commands, environment, DB errors or traceback in GitHub logs.
        print("Release stopped. Authorized operator must inspect the protected host record.", file=sys.stderr)
        sys.exit(1)
