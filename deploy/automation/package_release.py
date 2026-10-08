"""Create the attested archive; manifests describe integrity, not authority."""
import hashlib
import json
import os
from pathlib import Path
import tarfile

FILES = {"backend.tar.gz", "frontend.tar.gz", "frontend-files.json", "backend-packages.txt",
         "backend-audit.json", "image-tag", "image-id", "commit", "eligibility.json", "release.json"}


def digest(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pack(root, output):
    (root / "SHA256SUMS").write_text("".join(digest(root / name) + "  " + name + "\n" for name in sorted(FILES)))
    with tarfile.open(output, "w") as archive:
        for name in sorted(FILES | {"SHA256SUMS"}):
            archive.add(root / name, arcname=name, recursive=False)


if __name__ == "__main__":
    root = Path("release")
    frontend = Path("frontend-export/dist")
    (root / "frontend-files.json").write_text(json.dumps({p.relative_to(frontend).as_posix(): digest(p)
        for p in sorted(frontend.rglob("*")) if p.is_file()}, sort_keys=True))
    (root / "release.json").write_text(json.dumps({"repository": os.environ["GITHUB_REPOSITORY"],
        "workflow": ".github/workflows/lightsail-release.yml", "commit": os.environ["RELEASE_SHA"],
        "run_id": os.environ["GITHUB_RUN_ID"], "run_attempt": os.environ["GITHUB_RUN_ATTEMPT"]}, sort_keys=True))
    Path("transfer").mkdir(exist_ok=True)
    pack(root, Path("transfer/release.tar"))
