"""Preserve bounded reproductions of Claude's original guard findings; no host deployment."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

BASE = "cff58ccf4a52ccc6a4ddf9e7790ce94efd0b4ef7"
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    source = root / "legacy.py"
    source.write_bytes(subprocess.check_output(["git", "-c", "safe.directory=*", "show", BASE + ":deploy/automation/host_release.py"]))
    spec = importlib.util.spec_from_file_location("legacy", source)
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)
    payload = root / "payload"
    payload.mkdir()
    for name in legacy.FILES:
        (payload / name).write_text("fabricated disposable payload")
    (payload / "commit").write_text("a" * 40)
    (payload / "image-tag").write_text("nestaprime-release:" + "a" * 40 + "-1-1")
    (payload / "image-id").write_text("sha256:" + "b" * 64)
    (payload / "eligibility.json").write_text(json.dumps({"commit": "a" * 40}))
    # An attacker can change bytes and supply corresponding hashes.
    (payload / "backend.tar.gz").write_text("changed backend with recomputed manifest")
    (payload / "SHA256SUMS").write_text("".join(hashlib.sha256((payload / name).read_bytes()).hexdigest() + "  " + name + "\n" for name in sorted(legacy.FILES)))
    legacy.verify_bundle(payload)
    front = root / "front"
    front.mkdir()
    (front / "index.html").write_text("index")
    (front / "unlisted.js").write_text("extra script")
    archive = root / "frontend.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for path in front.iterdir():
            bundle.add(path, arcname=path.name)
    extracted = root / "extracted"
    legacy.extract_frontend(archive, extracted)
    sums = root / "frontend-files.sha256"
    sums.write_text(hashlib.sha256((front / "index.html").read_bytes()).hexdigest() + "  index.html\n")
    subprocess.run(["sha256sum", "-c", str(sums)], cwd=extracted, check=True, stdout=subprocess.DEVNULL)
    result = {"reviewed_head": BASE, "scope": "legacy verifier/extraction utilities only; legacy main was never invoked",
        "recomputed_self_checksums_accepted": True, "unlisted_frontend_file_accepted": (extracted / "unlisted.js").is_file()}
    Path(sys.argv[1]).write_text(json.dumps(result, indent=2))
    print("Preserved original guard failures using fabricated disposable data; no live helper invoked.")
