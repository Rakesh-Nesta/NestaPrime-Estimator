"""Focused controller probes with modeled Docker/HTTP and a deterministic clock."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from host_release import Deadline, Interrupted, Release, ReleaseFault


class ReplacementTests(unittest.TestCase):
    image = "sha256:" + "a" * 64
    container = "b" * 64

    def exercise(self, states, *, missing=False, healthy=True, wrong_image=False, interruption=None):
        clock = [0.0]
        calls = []
        owner = self

        class FakeRunner:
            def __init__(self, cfg, event):
                self.event = event

            def remaining(self):
                if interruption:
                    raise interruption()
                return 30

            def run(self, step, args, **kwargs):
                calls.append((step, args, kwargs["timeout"]))
                owner.assertGreater(kwargs["timeout"], 0)
                owner.assertLessEqual(kwargs["timeout"], 3 - clock[0])
                self.event(step, "started")
                if step == "backend.running-container":
                    owner.assertEqual(args[-4:], ["ps", "-a", "-q", "backend"])
                    value = b"" if missing else owner.container.encode()
                else:
                    owner.assertEqual(args[-1], owner.container)
                    state = states.pop(0) if len(states) > 1 else states[0]
                    value = json.dumps(["sha256:" + "c" * 64 if wrong_image else owner.image,
                        state, state == "running", state == "restarting", 42 if state != "running" else 0,
                        False, 1 if state == "restarting" else 0]).encode()
                self.event(step, "completed")
                return value

            def fetch(self, step, url, *, timeout):
                calls.append((step, [], timeout))
                self.event(step, "started")
                if not healthy:
                    raise ReleaseFault("http-status", 31)
                return b'{"status":"ok"}'

        with tempfile.TemporaryDirectory() as tmp:
            cfg = {"release_root": tmp, "health_seconds": 3, "backend_url": "http://fixture/health",
                "compose_project": "fixture", "env_file": "fixture.env", "compose_files": []}
            release = Release(cfg, "1-1", github=object(), runner_type=FakeRunner)
            release.root.mkdir()
            def advance(seconds):
                clock[0] += seconds
            with patch("host_release.time.monotonic", side_effect=lambda: clock[0]), patch("host_release.time.sleep", side_effect=advance):
                try:
                    result = release.replacement_ready(self.image)
                except (ReleaseFault, Deadline, Interrupted) as error:
                    result = error
            return result, release.record, calls, clock[0]

    def test_exited_no_restart_is_readiness_failure(self):
        result, record, calls, elapsed = self.exercise(["exited"])
        self.assertEqual(result.category, "backend-readiness")
        self.assertEqual(record["backend_state"], {"status": "exited", "running": False, "restarting": False,
            "exit_code": 42, "oom_killed": False, "restart_count": 0})
        self.assertEqual(elapsed, 3)
        self.assertFalse(any(step == "backend.http" for step, _, _ in calls))

    def test_missing_id_never_inspected(self):
        result, record, calls, elapsed = self.exercise([], missing=True)
        self.assertEqual(result.category, "backend-readiness")
        self.assertEqual(record["backend_state"], {"status": "missing"})
        self.assertTrue(all(step == "backend.running-container" for step, _, _ in calls))
        self.assertEqual(elapsed, 3)

    def test_running_never_ready_is_bounded(self):
        result, record, calls, elapsed = self.exercise(["running"], healthy=False)
        self.assertEqual(result.category, "backend-readiness")
        self.assertEqual(record["backend_state"]["status"], "running")
        self.assertEqual(record["last_probe_failure"]["category"], "http-status")
        self.assertEqual(elapsed, 3)

    def test_restart_then_healthy_is_accepted(self):
        result, record, calls, elapsed = self.exercise(["exited", "restarting", "running"])
        self.assertEqual(result, self.container)
        self.assertEqual(elapsed, 2)
        self.assertEqual(record["events"][-1], {"step": "backend.ready", "result": "completed"})

    def test_wrong_image_still_rejected(self):
        result, _, _, _ = self.exercise(["running"], wrong_image=True)
        self.assertEqual(result.category, "backend-identity")

    def test_deadline_and_interrupt_are_not_reclassified(self):
        for signal in (Deadline, Interrupted):
            result, _, _, _ = self.exercise(["running"], interruption=signal)
            self.assertIsInstance(result, signal)


if __name__ == "__main__":
    unittest.main()
