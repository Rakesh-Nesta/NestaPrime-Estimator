import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from eligibility import validate

# fcntl exists on the Linux target; allow pure verifier testing on Windows.
if sys.platform == "win32":
    sys.modules["fcntl"] = type("Fcntl", (), {})()
from host_release import FILES, ReleaseFault, extract_frontend, verify_bundle


class SafetyTests(unittest.TestCase):
    def test_eligibility_failures(self):
        sha = "a" * 40
        run = dict(head_sha=sha, head_branch="main", event="push", head_repository={"full_name": "owner/repo"}, status="completed", conclusion="success")
        jobs = [dict(name=n, status="completed", conclusion="success") for n in ["test", "docker-build", "dependency-audit"]]
        validate(run, jobs, sha, "owner/repo")
        for field, value in [("head_sha", "b" * 40), ("head_branch", "pr"), ("event", "pull_request"), ("status", "in_progress"), ("conclusion", "failure")]:
            bad = copy.deepcopy(run)
            bad[field] = value
            with self.assertRaises(AssertionError):
                validate(bad, jobs, sha, "owner/repo")
        for result in ["failure", "skipped", "neutral", "cancelled", None]:
            bad = copy.deepcopy(jobs)
            bad[0]["conclusion"] = result
            with self.assertRaises(AssertionError):
                validate(run, bad, sha, "owner/repo")
        with self.assertRaises(AssertionError):
            validate(run, jobs[:2], sha, "owner/repo")

    def test_bundle_tamper_and_missing_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in FILES:
                (root / name).write_text("test")
            (root / "commit").write_text("a" * 40)
            (root / "image-tag").write_text("nestaprime-release:" + "a" * 40 + "-1-1")
            (root / "image-id").write_text("sha256:" + "b" * 64)
            (root / "eligibility.json").write_text(json.dumps({"commit": "a" * 40}))
            sums = "".join(hashlib.sha256((root / n).read_bytes()).hexdigest() + "  " + n + "\n" for n in sorted(FILES))
            (root / "SHA256SUMS").write_text(sums)
            verify_bundle(root)
            (root / "backend.tar.gz").write_text("tampered")
            with self.assertRaises(ReleaseFault):
                verify_bundle(root)
            (root / "SHA256SUMS").write_text(sums.splitlines()[0] + "\n")
            with self.assertRaises(ReleaseFault):
                verify_bundle(root)

    def test_archive_traversal_and_link(self):
        for name, kind in [("../outside", tarfile.REGTYPE), ("/absolute", tarfile.REGTYPE), ("link", tarfile.SYMTYPE)]:
            with tempfile.TemporaryDirectory() as temp:
                archive = Path(temp) / "bad.tar.gz"
                with tarfile.open(archive, "w:gz") as out:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    member.linkname = "/etc/passwd"
                    out.addfile(member)
                with self.assertRaises(ReleaseFault):
                    extract_frontend(archive, Path(temp) / "dist")


if __name__ == "__main__":
    unittest.main()
