"""Deterministic HTTP fault injection, no Docker or live endpoint required."""
import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import socket
import threading
import time
import unittest
from unittest.mock import patch

from wait_http import wait_http


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.server.attempts += 1
        if self.path == "/reset" or (self.path == "/recover" and self.server.attempts <= 2):
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
            return
        if self.path == "/stall":
            self.server.stop_event.wait(1)
            return
        status = 503 if self.path == "/unavailable" else 200
        body = {
            "/recover": b"built frontend",
            "/wrong": b"nginx welcome",
            "/health": b'{"status":"ok"}',
            "/bad-health": b'{"status":"starting"}',
        }.get(self.path, b"unavailable")
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.attempts = 0
        self.server.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.stop_event.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)

    def check(self, path, timeout=0.15, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return wait_http(self.base + path, timeout=timeout, interval=0.01, request_timeout=0.03, **kwargs)

    def test_reset_then_ready_requires_exact_frontend(self):
        self.assertEqual(self.check("/recover", timeout=2, kind="frontend", expected=b"built frontend"), b"built frontend")
        self.assertEqual(self.server.attempts, 3)

    def test_wrong_frontend_never_passes(self):
        with self.assertRaisesRegex(TimeoutError, "frontend content mismatch.*sha256"):
            self.check("/wrong", kind="frontend", expected=b"built frontend")

    def test_health_must_report_ok(self):
        self.assertEqual(self.check("/health", timeout=2, kind="health"), b'{"status":"ok"}')
        with self.assertRaisesRegex(TimeoutError, "status=ok"):
            self.check("/bad-health", kind="health")

    def test_reset_and_http_error_report_deadline(self):
        for path, failure in [("/reset", "RemoteDisconnected"), ("/unavailable", "503")]:
            with self.subTest(path=path), self.assertRaisesRegex(TimeoutError, failure):
                self.check(path, kind="frontend", expected=b"built frontend")

    def test_stalled_service_is_bounded(self):
        started = time.monotonic()
        with self.assertRaisesRegex(TimeoutError, "deadline.*last failure"):
            self.check("/stall", kind="health")
        self.assertLess(time.monotonic() - started, 0.5)

    def test_deadline_timeout_preserves_last_rejected_response(self):
        # Force the exact CI boundary deterministically: wrong bytes, then a
        # request timeout at the deadline. No scheduling-dependent assertion.
        clock = [0.0]
        response = io.BytesIO(b"nginx welcome")
        response.status = 200
        with patch("wait_http.time.monotonic", side_effect=lambda: clock[0]), \
             patch("wait_http.time.sleep", side_effect=lambda delay: clock.__setitem__(0, clock[0] + delay)), \
             patch("wait_http.urllib.request.urlopen", side_effect=[response, TimeoutError("deadline read")]) as request:
            with self.assertRaisesRegex(TimeoutError, "frontend content mismatch.*sha256"):
                wait_http(self.base, kind="frontend", expected=b"built frontend", timeout=0.2, interval=0.1)
            self.assertEqual(request.call_count, 2)


if __name__ == "__main__":
    unittest.main()
