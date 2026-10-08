"""Disposable signed test subjects; release-safety identity is NEVER production authority."""
import json
import gzip
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tarfile

from package_release import digest, pack


def run(args, **kwargs):
    return subprocess.run(args, check=True, timeout=300, stderr=subprocess.DEVNULL, **kwargs)


def create(root):
    root.mkdir(parents=True, exist_ok=True)
    sha = os.environ.get("GITHUB_SHA") or run(["git", "-c", "safe.directory=*", "rev-parse", "HEAD"], stdout=subprocess.PIPE).stdout.decode().strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "Rakesh-Nesta/NestaPrime-Estimator")
    run_id, attempt = os.environ.get("GITHUB_RUN_ID", "1"), os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    tag = "nestaprime-release:" + sha + "-" + run_id + "-" + attempt
    payload = root / "payload"
    payload.mkdir()
    meta = {"repository": repo, "workflow": ".github/workflows/release-safety.yml", "commit": sha, "run_id": run_id, "run_attempt": attempt,
            "source_ref": os.environ.get("GITHUB_REF", "refs/heads/codex/lightsail-release-automation")}
    (root / "fixture.json").write_text(json.dumps(meta))
    run(["docker", "build", "--label", "org.opencontainers.image.revision=" + sha, "-t", tag, "."], stdout=subprocess.DEVNULL)
    good = run(["docker", "inspect", "-f", "{{.Id}}", tag], stdout=subprocess.PIPE).stdout.decode().strip()
    old_tag = "np-release-test-previous:" + run_id + "-" + attempt
    recipe = ("FROM " + tag + "\nLABEL disposable.previous=true\n").encode()
    run(["docker", "build", "-t", old_tag, "-"], input=recipe, stdout=subprocess.DEVNULL)
    (root / "previous-image").write_text(old_tag)
    # Synthetic fixture audit evidence deliberately does NOT claim a real image
    # audit pass. This signer workflow is rejected by production policy.
    for name in ("backend-packages.txt", "backend-audit.json"):
        (payload / name).write_text("[]")
    (payload / "eligibility.json").write_text(json.dumps({"commit": sha}))
    (payload / "release.json").write_text(json.dumps({key: meta[key] for key in ("repository", "workflow", "commit", "run_id", "run_attempt")}))
    (payload / "commit").write_text(sha)
    (payload / "image-tag").write_text(tag)
    dist = root / "dist"
    dist.mkdir()
    (dist / "index.html").write_text('<html><script src="/app.js"></script>disposable release</html>')
    (dist / "app.js").write_text('console.log("disposable");')
    (dist / "release.txt").write_text(sha + "\n")
    manifest = {p.name: digest(p) for p in dist.iterdir()}
    (payload / "frontend-files.json").write_text(json.dumps(manifest))

    def frontend():
        with tarfile.open(payload / "frontend.tar.gz", "w:gz") as archive:
            for path in sorted(dist.iterdir()):
                archive.add(path, arcname=path.name)

    def image(image_id):
        (payload / "image-id").write_text(image_id)
        process = subprocess.Popen(["docker", "save", tag], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        with gzip.open(payload / "backend.tar.gz", "wb") as output:
            shutil.copyfileobj(process.stdout, output)
        process.stdout.close()
        if process.wait(timeout=300) != 0:
            raise RuntimeError("Disposable image export failed")
    image(good)
    frontend()
    pack(payload, root / "success.tar")
    (dist / "unlisted.js").write_text("unlisted")
    frontend()
    pack(payload, root / "extra.tar")
    (dist / "unlisted.js").unlink()
    original = (dist / "index.html").read_bytes()
    (dist / "index.html").unlink()
    frontend()
    pack(payload, root / "missing.tar")
    (dist / "index.html").write_text("altered index")
    frontend()
    pack(payload, root / "altered.tar")
    (dist / "index.html").write_bytes(original)
    frontend()
    for kind, recipe in [("backend-failure", "CMD [\"sh\",\"-c\",\"exit 42\"]\n"),
                         ("migration-failure", "RUN printf 'raise RuntimeError(\"disposable migration fault\")\\n' > /app/alembic/env.py\n")]:
        temp_tag = "np-release-test-fault:" + kind + "-" + run_id
        run(["docker", "build", "-t", temp_tag, "-"], input=("FROM " + old_tag + "\n" + recipe).encode(), stdout=subprocess.DEVNULL)
        bad = run(["docker", "inspect", "-f", "{{.Id}}", temp_tag], stdout=subprocess.PIPE).stdout.decode().strip()
        run(["docker", "tag", temp_tag, tag])
        image(bad)
        pack(payload, root / (kind + ".tar"))
        run(["docker", "image", "rm", temp_tag], stdout=subprocess.DEVNULL)
    run(["docker", "tag", good, tag])
    print("Created six disposable subjects; no production signer or real audit success claimed.")


if __name__ == "__main__":
    create(Path(sys.argv[1]))
