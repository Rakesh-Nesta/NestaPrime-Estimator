"""Policy and timeout negative controls; no real GitHub/production credentials."""
import contextlib
import copy
import fcntl
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from environment_gate import validate_approval, validate_environment
from eligibility import eligible
from host_release import Deadline, ReleaseFault, Runner, verify_frontend, extract_frontend
from package_release import digest


class HostGuards(unittest.TestCase):
    def test_failed_actual_image_audit_retains_evidence_and_stops_packaging(self):
        # Controlled tool boundary; exercise the real prepare.sh failure ordering.
        script = Path(__file__).with_name("prepare.sh").resolve()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binaries = root / "bin"
            binaries.mkdir()
            commands = {
                "docker": '#!/bin/sh\ncase "$1" in build) exit 0;; image) printf "sha256:fixture\\n";; run) printf "fixture-package==1\\n";; *) exit 99;; esac\n',
                "python": "#!/bin/sh\nexit 0\n",
                "pip-audit": '#!/bin/sh\nprintf "%s\\n" "$@" > audit-args.txt\nprintf \'{"fixture":"rejected"}\\n\' > release/backend-audit.json\nprintf "fixture audit failure\\n"\nexit 1\n',
            }
            for name, content in commands.items():
                path = binaries / name
                path.write_text(content)
                path.chmod(0o755)
            env = dict(os.environ, PATH=str(binaries) + ":" + os.environ["PATH"], GITHUB_RUN_ID="1", GITHUB_RUN_ATTEMPT="1")
            result = subprocess.run(["bash", str(script), "a" * 40], cwd=root, env=env, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            audit_args = (root / "audit-args.txt").read_text().splitlines()
            self.assertIn("release/backend-packages.txt", audit_args)
            self.assertFalse(any(arg.startswith("--ignore-vuln") or arg == "PYSEC-2026-1325" for arg in audit_args))
            self.assertEqual((root / "release/backend-packages.txt").read_text(), "fixture-package==1\n")
            self.assertEqual(json.loads((root / "release/backend-audit.json").read_text()), {"fixture": "rejected"})
            self.assertIn("fixture audit failure", (root / "release/backend-audit.log").read_text())
            self.assertEqual((root / "release/image-id").read_text().strip(), "sha256:fixture")
            self.assertEqual((root / "release/commit").read_text().strip(), "a" * 40)
            self.assertFalse((root / "transfer/release.tar").exists())

    def test_frontend_exact_set_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "dist"
            root.mkdir()
            (root / "index.html").write_text("built")
            manifest = Path(tmp) / "manifest.json"
            manifest.write_text(json.dumps({"index.html": digest(root / "index.html")}))
            verify_frontend(root, manifest)
            (root / "unlisted.js").write_text("extra")
            with self.assertRaises(ReleaseFault) as failed:
                verify_frontend(root, manifest)
            self.assertEqual(failed.exception.category, "frontend-file-set")
            (root / "unlisted.js").unlink()
            (root / "index.html").write_text("altered")
            with self.assertRaises(ReleaseFault) as failed:
                verify_frontend(root, manifest)
            self.assertEqual(failed.exception.category, "frontend-digest")
            (root / "index.html").unlink()
            with self.assertRaises(ReleaseFault):
                verify_frontend(root, manifest)

    def test_stale_tip_rejected_before_checks(self):
        called = []
        def get(path):
            called.append(path)
            return {"object": {"sha": "b" * 40}}
        with self.assertRaisesRegex(AssertionError, "current main tip"):
            eligible("a" * 40, get)
        self.assertEqual(called, ["/git/ref/heads/main"])

    def test_environment_and_independent_approval(self):
        env = {"can_admins_bypass": False, "protection_rules": [{"type": "required_reviewers", "prevent_self_review": True,
            "reviewers": [{"type": "User", "reviewer": {"id": 2}}]}],
            "deployment_branch_policy": {"custom_branch_policies": True, "protected_branches": False}}
        rules = [{"name": "main", "type": "branch"}]
        self.assertEqual(validate_environment(env, rules), {2})
        for value in (True, None, "false"):
            bad = copy.deepcopy(env)
            bad["can_admins_bypass"] = value
            with self.assertRaises(AssertionError):
                validate_environment(bad, rules)
        bad = copy.deepcopy(env)
        del bad["can_admins_bypass"]
        with self.assertRaises(AssertionError):
            validate_environment(bad, rules)
        for change in ("self-review", "team", "unrestricted-branches"):
            bad = copy.deepcopy(env)
            if change == "self-review":
                bad["protection_rules"][0]["prevent_self_review"] = False
            elif change == "team":
                bad["protection_rules"][0]["reviewers"][0]["type"] = "Team"
            else:
                bad["deployment_branch_policy"] = None
            with self.assertRaises(AssertionError):
                validate_environment(bad, rules)
        for bad_rules in ([], rules * 2, [{"name": "main", "type": "tag"}], [{"name": "*", "type": "branch"}]):
            with self.assertRaises(AssertionError):
                validate_environment(env, bad_rules)
        review = [{"state": "approved", "environments": [{"id": 10}], "user": {"id": 2}}]
        validate_approval(review, 10, 1, {2})
        for reviews, actor, permitted in [(review, 2, {2}), (review, 1, {3}), ([], 1, {2}), (review * 2, 1, {2})]:
            with self.assertRaises(AssertionError):
                validate_approval(reviews, 10, actor, permitted)

    def test_subprocess_tree_deadline(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "child-pid"
            runner = Runner({"deadline_seconds": 1}, lambda *_args: None)
            code = "import pathlib,subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); pathlib.Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(60)"
            start = time.monotonic()
            with self.assertRaises(Deadline):
                runner.run("negative.deadline", [sys.executable, "-c", code, str(marker)])
            # Include scheduling/fork latency on loaded disposable hosts. A
            # surviving 60-second child still fails both this and /proc checks.
            self.assertLess(time.monotonic() - start, 5)
            pid = int(marker.read_text())
            status = Path(f"/proc/{pid}/stat")
            def terminated():
                try:
                    return status.read_text().split()[2] == "Z"
                except (FileNotFoundError, ProcessLookupError):
                    # Linux can reap between open/read, not just before exists().
                    return True
            end = time.monotonic() + 1
            while not terminated() and time.monotonic() < end:
                time.sleep(0.01)
            self.assertTrue(terminated(), "Grandchild survived deadline")

    def test_command_error_does_not_expose_output(self):
        sentinel = os.urandom(16).hex()
        events = []
        runner = Runner({"deadline_seconds": 5}, lambda *event: events.append(event))
        with self.assertRaises(ReleaseFault) as failed:
            runner.run("negative.exit", [sys.executable, "-c", "import sys; print(sys.argv[1]); print(sys.argv[1],file=sys.stderr); sys.exit(23)", sentinel], capture=True)
        self.assertEqual(failed.exception.code, 23)
        self.assertNotIn(sentinel, repr(events) + repr(failed.exception))

    def test_container_style_timeout_remains_a_timeout(self):
        runner = Runner({"deadline_seconds": 5}, lambda *_args: None)
        with self.assertRaises(ReleaseFault) as failed:
            runner.run("negative.inner-timeout", ["timeout", "0.1", sys.executable, "-c", "import time; time.sleep(60)"])
        self.assertEqual((failed.exception.category, failed.exception.code), ("command-timeout", 124))

    def test_slow_drip_health_cannot_extend_deadline(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        stopped = threading.Event()
        class Drip(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", "9999999")
                self.end_headers()
                try:
                    while not stopped.wait(0.01):
                        self.wfile.write(b"x")
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Drip)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        runner = Runner({"deadline_seconds": 0.2}, lambda *_args: None)
        start = time.monotonic()
        try:
            with self.assertRaises(Deadline):
                runner.fetch("negative.health", f"http://127.0.0.1:{server.server_port}/health")
            self.assertLess(time.monotonic() - start, 2)
        finally:
            stopped.set()
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)

    def test_http_status_category_retains_no_response_body(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        sentinel = os.urandom(16).hex()
        class Rejected(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_GET(self):
                self.send_response(503)
                self.end_headers()
                self.wfile.write(sentinel.encode())
        server = ThreadingHTTPServer(("127.0.0.1", 0), Rejected)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        events = []
        try:
            runner = Runner({"deadline_seconds": 5}, lambda *event: events.append(event))
            with self.assertRaises(ReleaseFault) as failed:
                runner.fetch("negative.http-status", f"http://127.0.0.1:{server.server_port}/health")
            self.assertEqual((failed.exception.category, failed.exception.code), ("http-status", 31))
            self.assertEqual(events[-1], ("negative.http-status", "failed", "http-status", 31))
            self.assertNotIn(sentinel, repr(events))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)


if __name__ == "__main__":
    unittest.main()
