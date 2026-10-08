"""Real helper + actual Docker/Postgres/nginx. GitHub control plane is modeled.

CI uses real GitHub/Sigstore attestation verification. Explicit local simulation
injects only that unavailable signing boundary and is reported separately.
"""
import contextlib
import copy
import errno
import fcntl
import io
import json
import os
from pathlib import Path
import secrets
import signal
import shutil
import socket
import ssl
import subprocess
import tempfile
import time
import unittest

from host_release import Release, ReleaseFault, Runner, extract_frontend
from package_release import FILES, digest, pack


def run(args, **kwargs):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=90, **kwargs).stdout


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class FixturePolicy:
    def __init__(self, sha):
        self.sha, self.checks, self.stale, self.approved = sha, 0, False, True

    def tip(self):
        return self.sha

    def check(self, sha, slot):
        self.checks += 1
        if self.stale and self.checks == 2:
            raise ReleaseFault("eligibility-stale")
        if not self.approved:
            raise ReleaseFault("eligibility-or-approval")
        if sha != self.sha:
            raise ReleaseFault("eligibility-stale")


@unittest.skipUnless(os.environ.get("HOST_FIXTURE_DIR"), "real helper fixtures are generated in disposable CI")
class HostOrchestration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = Path(os.environ["HOST_FIXTURE_DIR"]).resolve()
        cls.meta = json.loads((cls.fixtures / "fixture.json").read_text())
        cls.real_crypto = os.environ.get("HOST_REAL_PROVENANCE") == "1"
        cls.reports = []
        cls.certs = tempfile.TemporaryDirectory()
        root = Path(cls.certs.name)
        run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(root / "ca.key"), "-out", str(root / "ca.pem"),
            "-days", "1", "-subj", "/CN=Disposable release CA", "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign"])
        run(["openssl", "req", "-newkey", "rsa:2048", "-nodes", "-keyout", str(root / "server.key"), "-out", str(root / "server.csr"), "-subj", "/CN=localhost"])
        (root / "ext").write_text("subjectAltName=DNS:localhost,IP:127.0.0.1\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n")
        run(["openssl", "x509", "-req", "-in", str(root / "server.csr"), "-CA", str(root / "ca.pem"), "-CAkey", str(root / "ca.key"),
            "-CAcreateserial", "-out", str(root / "server.pem"), "-days", "1", "-extfile", str(root / "ext")])
        system_ca = Path(ssl.get_default_verify_paths().cafile or "/etc/ssl/cert.pem")
        (root / "trust.pem").write_bytes(system_ca.read_bytes() + (root / "ca.pem").read_bytes())

    @classmethod
    def tearDownClass(cls):
        report = os.environ.get("HOST_TEST_REPORT")
        if report:
            Path(report).write_text(json.dumps({"real_provenance": cls.real_crypto, "cases": cls.reports}, indent=2))
            Path(report).chmod(0o644)  # Sanitized test report is readable by the CI artifact uploader.
        cls.certs.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.root.chmod(0o755)
        self.project = "np-helper-" + secrets.token_hex(5)
        self.slot = self.meta["run_id"] + "-" + self.meta["run_attempt"]
        self.incoming = self.root / "incoming" / self.slot
        self.incoming.mkdir(parents=True)
        self.bundle("success")
        password = secrets.token_hex(24)
        self.env = self.root / "app.env"
        self.env.write_text("POSTGRES_PASSWORD=" + password + "\nDATABASE_URL=postgresql+psycopg://nestaprime:" + password + "@db:5432/nestaprime_estimator\nSECRET_KEY=" + secrets.token_hex(32) + "\n")
        old = (self.fixtures / "previous-image").read_text().strip()
        compose = self.root / "compose.yml"
        compose.write_text("services:\n  db:\n    image: postgres:16\n    environment:\n      POSTGRES_USER: nestaprime\n      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}\n      POSTGRES_DB: nestaprime_estimator\n    volumes: ['dbdata:/var/lib/postgresql/data']\n    healthcheck:\n      test: [CMD-SHELL, 'pg_isready -U nestaprime']\n      interval: 1s\n      timeout: 2s\n      retries: 30\n  backend:\n    image: " + old + "\n    depends_on:\n      db:\n        condition: service_healthy\n    environment:\n      DATABASE_URL: ${DATABASE_URL}\n      SECRET_KEY: ${SECRET_KEY}\n      ENVIRONMENT: production\n    ports: ['0.0.0.0:" + str(free_port()) + ":8000']\n    volumes: ['uploads:/app/uploads']\nvolumes:\n  dbdata: {}\n  uploads: {}\n")
        active = self.root / "active.yml"
        active.write_text("services: {}\n")
        self.compose = ["docker", "compose", "-p", self.project, "--env-file", str(self.env), "-f", str(compose), "-f", str(active)]
        try:
            run(self.compose + ["up", "-d", "--no-build", "--pull", "never"])
            self.db = run(self.compose + ["ps", "-q", "db"]).decode().strip()
            self.backend = run(self.compose + ["ps", "-q", "backend"]).decode().strip()
            self.previous_id = run(["docker", "inspect", "-f", "{{.Image}}", self.backend]).decode().strip()
            self.previous_uploads = json.loads(run(["docker", "inspect", "-f", "{{json .Mounts}}", self.backend]))[0]["Name"]
            port = run(["docker", "port", self.backend, "8000"]).decode().splitlines()[0].rsplit(":", 1)[1]
            self.backend_url = "http://" + os.environ.get("TEST_DOCKER_HOST", "127.0.0.1") + ":" + port + "/health"
            # Require actual schema startup before testing the existing host state.
            for _attempt in range(60):
                try:
                    run(["docker", "exec", self.db, "psql", "-U", "nestaprime", "-d", "nestaprime_estimator", "-Atc", "SELECT version_num FROM alembic_version"])
                    marker = run(["docker", "exec", self.db, "psql", "-U", "nestaprime", "-d", "nestaprime_estimator", "-Atc", "SELECT id FROM p5_migration_marker"])
                    if marker.strip() == b"1":
                        break
                except subprocess.CalledProcessError:
                    pass
                time.sleep(1)
            self.sql("CREATE TABLE release_test_probe (id integer PRIMARY KEY); INSERT INTO release_test_probe VALUES (297)")
            previous = self.root / "bootstrap"
            previous.mkdir()
            previous.chmod(0o755)
            (previous / "index.html").write_text("previous frontend")
            (previous / "index.html").chmod(0o644)
            self.link = self.root / "served"
            self.link.symlink_to(previous)
            certs = Path(self.certs.name)
            nginx_config = self.root / "nginx.conf"
            public_port = free_port()
            nginx_config.write_text("pid " + str(self.root / "nginx.pid") + ";\nerror_log /dev/null;\nevents {}\nhttp { access_log off; server { listen 127.0.0.1:" + str(public_port) + " ssl; ssl_certificate " + str(certs / "server.pem") + "; ssl_certificate_key " + str(certs / "server.key") + "; root " + str(self.link) + "; location /api/ { proxy_pass " + self.backend_url.removesuffix("health") + "; } } }\n")
            run(["nginx", "-c", str(nginx_config)])
            self.cfg = {"enabled": True, "repository": self.meta["repository"], "workflow": self.meta["workflow"], "source_ref": self.meta["source_ref"],
                "release_root": str(self.root / "releases"), "incoming_root": str(self.root / "incoming"), "lock_file": str(self.root / "release.lock"),
                "compose_project": self.project, "env_file": str(self.env), "compose_files": [str(compose), str(active)], "active_override": str(active),
                "frontend_link": str(self.link), "public_url": "https://localhost:" + str(public_port), "backend_url": self.backend_url,
                "nginx_config": str(nginx_config), "tls_ca_file": str(certs / "trust.pem"), "docker": shutil.which("docker"), "gh": shutil.which("gh") or "/usr/bin/gh",
                "nginx": shutil.which("nginx"), "min_disk_bytes": 1, "deadline_seconds": 300, "health_seconds": 60}
            Path(self.cfg["release_root"]).mkdir(mode=0o755)
            Path(self.cfg["release_root"]).chmod(0o755)
            self.policy = FixturePolicy(self.meta["commit"])
            self.hook = None
        except BaseException:
            self.clean()
            raise

    def sql(self, statement):
        return run(["docker", "exec", self.db, "psql", "-U", "nestaprime", "-d", "nestaprime_estimator", "-Atc", statement])

    def bundle(self, kind):
        shutil.copyfile(self.fixtures / (kind + ".tar"), self.incoming / "release.tar")
        if self.real_crypto:
            shutil.copyfile(self.fixtures / "attestation.json", self.incoming / "attestation.json")
        else:
            (self.incoming / "attestation.json").write_text("local signing-boundary simulation")

    def release(self, category=None):
        owner = self
        class TestRunner(Runner):
            def run(self, step, args, **kwargs):
                if owner.hook:
                    self.event(step, "started")
                    owner.hook(step, args)
                if step == "provenance.verify" and not owner.real_crypto:
                    # Test-only dependency injection. Production CLI always uses Runner.
                    self.event(step, "started")
                    statement = {"subject": [{"digest": {"sha256": digest(owner.incoming / "release.tar")}}], "predicate": {"runDetails": {"metadata": {
                        "invocationId": "https://github.com/" + owner.meta["repository"] + "/actions/runs/" + owner.slot.replace("-", "/attempts/")}}}}
                    return json.dumps([{"verificationResult": {"statement": statement}}]).encode()
                return super().run(step, args, **kwargs)
        controller = Release(self.cfg, self.slot, github=self.policy, runner_type=TestRunner)
        with contextlib.redirect_stdout(io.StringIO()) as console:
            result = controller.run()
        record = json.loads((controller.root / "record.json").read_text())
        self.reports.append({"case": self._testMethodName, "status": record["status"], "failure_category": record.get("failure_category"),
            "mutation_started": record["mutation_started"], "events": record["events"], "cleanup": record.get("cleanup", []),
            "last_probe_failure": record.get("last_probe_failure"), "backend_state": record.get("backend_state")})
        self.assertEqual(result, 1 if category else 0, console.getvalue())
        if category:
            self.assertIn(record["failure_category"], (category,) if isinstance(category, str) else category, record)
        else:
            self.assertEqual(record["status"], "healthy")
            self.assertTrue(record["backup_readable"] and record["backup_restore_rehearsed"] and record["migration_rehearsed"])
            self.assertTrue(all(item["completed"] for item in record["cleanup"]))
        return controller, record

    def unchanged(self, record):
        self.assertFalse(record["mutation_started"])
        self.assertEqual(self.link.resolve(), self.root / "bootstrap")
        current = run(self.compose + ["ps", "-q", "backend"]).decode().strip()
        self.assertEqual(run(["docker", "inspect", "-f", "{{.Image}}", current]).decode().strip(), self.previous_id)

    def deployment_snapshot(self):
        """Observable deployment state, before or after a successful first use."""
        containers = run(self.compose + ["ps", "-q"]).decode().split()
        return {
            "containers": sorted((item["Id"], item["Image"], item["State"]["StartedAt"],
                json.dumps(item["Mounts"], sort_keys=True))
                for item in json.loads(run(["docker", "inspect", *containers]))),
            "override": Path(self.cfg["active_override"]).read_bytes(),
            "frontend": str(self.link.resolve()),
            "files": {str(path.relative_to(self.link.resolve())): digest(path)
                for path in self.link.resolve().rglob("*") if path.is_file()},
            "database": self.sql("SELECT version_num FROM alembic_version ORDER BY version_num; "
                "SELECT id, deployed_at FROM p5_migration_marker ORDER BY id; SELECT id FROM release_test_probe ORDER BY id"),
        }

    def assert_provenance_rejection(self, record, before, *, verified):
        self.unchanged(record)
        self.assertEqual(record["step"], "provenance.verify")
        results = [event["result"] for event in record["events"] if event["step"] == "provenance.verify"]
        self.assertIn("completed" if verified else "failed", results)
        if not verified:
            self.assertNotIn("completed", results)
        self.assertFalse(any(event["step"] in ("bundle.integrity", "eligibility.after-approval", "backend.load", "backup.dump")
            for event in record["events"]))
        self.assertEqual(self.policy.checks, 0)
        self.assertEqual(self.deployment_snapshot(), before)

    def test_signed_bundle_wrong_slot_real_provenance(self):
        if not self.real_crypto:
            self.skipTest("Authenticity negative control requires real CI attestation")
        before = self.deployment_snapshot()
        original = self.incoming
        self.slot = self.meta["run_id"] + "-" + str(int(self.meta["run_attempt"]) + 1)
        self.incoming = original.parent / self.slot
        shutil.copytree(original, self.incoming)
        _, record = self.release("provenance-run-or-digest")
        # Real signature verification succeeds; the signed invocation/slot guard rejects.
        self.assert_provenance_rejection(record, before, verified=True)

    def test_duplicate_slot_after_success_real_provenance(self):
        if not self.real_crypto:
            self.skipTest("Authenticity negative control requires real CI attestation")
        controller, record = self.release()
        self.assertTrue(record["mutation_started"] and record["frontend_switched"])
        self.assertEqual(self.link.resolve(), controller.root / "dist")
        self.assertEqual(self.policy.checks, 2)
        before = self.deployment_snapshot()
        original_record = (controller.root / "record.json").read_bytes()
        retry = Release(self.cfg, self.slot, github=self.policy)
        # The exclusive directory reservation rejects before any event/command,
        # preserving the successful record instead of overwriting it on reuse.
        with self.assertRaises(FileExistsError) as rejected:
            retry.run()
        self.assertEqual(rejected.exception.errno, errno.EEXIST)
        self.assertEqual(Path(rejected.exception.filename), controller.root)
        self.assertEqual(retry.record["step"], "initialization")
        self.assertEqual(retry.record["events"], [])
        self.assertFalse(retry.record["mutation_started"])
        self.assertEqual(self.policy.checks, 2)
        self.assertEqual((controller.root / "record.json").read_bytes(), original_record)
        self.assertEqual(self.deployment_snapshot(), before)
        self.reports.append({"case": self._testMethodName, "phase": "reuse", "guard": "exclusive-slot-reservation",
            "exception": "FileExistsError", "errno": errno.EEXIST, "events": [], "mutation_started": False,
            "prior_success_record_preserved": True, "deployment_snapshot_unchanged": True})

    def test_valid_attestation_wrong_tarball_real_provenance(self):
        if not self.real_crypto:
            self.skipTest("Authenticity negative control requires real CI attestation")
        before = self.deployment_snapshot()
        proof = (self.incoming / "attestation.json").read_bytes()
        # All generated fixture tarballs share one signed subject set. Append a
        # legal tar end-padding block to create a readable, unsigned outer archive
        # with identical inner contents, rather than selecting another signed subject.
        with (self.incoming / "release.tar").open("ab") as archive:
            archive.write(bytes(512))
        self.assertNotIn(digest(self.incoming / "release.tar"), {digest(path) for path in self.fixtures.glob("*.tar")})
        payload = self.root / "wrong-tar-readable"
        extract_frontend(self.incoming / "release.tar", payload, FILES | {"SHA256SUMS"})
        original = self.root / "original-readable"
        extract_frontend(self.fixtures / "success.tar", original, FILES | {"SHA256SUMS"})
        self.assertEqual({p.name: digest(p) for p in payload.iterdir()}, {p.name: digest(p) for p in original.iterdir()})
        self.assertEqual((self.incoming / "attestation.json").read_bytes(), proof)
        _, record = self.release("authenticity")
        self.assert_provenance_rejection(record, before, verified=False)

    def test_success_real_orchestration_and_restore(self):
        def check_probe(step, args):
            if step == "migration.rehearsal":
                db = self.project + "-trial-" + self.slot + "-db"
                self.assertEqual(run(["docker", "exec", db, "psql", "-U", "nestaprime", "-d", "nestaprime_estimator", "-Atc", "SELECT id FROM release_test_probe"]).strip(), b"297")
        self.hook = check_probe
        controller, record = self.release()
        self.assertNotEqual(record["image_id"], self.previous_id)
        self.assertEqual(self.link.resolve(), controller.root / "dist")
        current = run(self.compose + ["ps", "-q", "backend"]).decode().strip()
        self.assertEqual(json.loads(run(["docker", "inspect", "-f", "{{json .Mounts}}", current]))[0]["Name"], self.previous_uploads)
        self.assertEqual(self.sql("SELECT id FROM release_test_probe").strip(), b"297")
        self.assertEqual(self.policy.checks, 2)

    def test_disabled_before_any_commands(self):
        self.cfg["enabled"] = False
        _, record = self.release("disabled")
        self.unchanged(record)

    def test_lock_contended(self):
        with open(self.cfg["lock_file"], "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _, record = self.release("lock-contended")
            self.unchanged(record)

    def test_signed_extra_file_rejected(self):
        self.bundle("extra")
        _, record = self.release("frontend-file-set")
        self.unchanged(record)

    def test_signed_missing_file_rejected(self):
        self.bundle("missing")
        _, record = self.release("frontend-file-set")
        self.unchanged(record)

    def test_signed_altered_file_rejected(self):
        self.bundle("altered")
        _, record = self.release("frontend-digest")
        self.unchanged(record)

    def test_stale_after_backup_before_mutation(self):
        self.policy.stale = True
        _, record = self.release("eligibility-stale")
        self.assertTrue(record["backup_restore_rehearsed"])
        self.unchanged(record)

    def test_missing_approval(self):
        self.policy.approved = False
        _, record = self.release("eligibility-or-approval")
        self.unchanged(record)

    def test_migration_unknown_revision(self):
        self.sql("UPDATE alembic_version SET version_num='unknown_revision'")
        _, record = self.release("migration-compatibility")
        self.unchanged(record)

    def test_candidate_migration_failure(self):
        self.bundle("migration-failure")
        _, record = self.release("migration-rehearsal")
        self.assertTrue(record["backup_restore_rehearsed"])
        self.unchanged(record)

    def test_backup_dump_failure(self):
        def stop_db(step, args):
            if step == "backup.dump":
                run(["docker", "stop", "-t", "0", self.db])
        self.hook = stop_db
        _, record = self.release("backup-dump")
        self.unchanged(record)

    def test_readable_dump_cannot_restore(self):
        def readonly_rehearsal(step, args):
            if step == "backup.restore":
                db = self.project + "-trial-" + self.slot + "-db"
                run(["docker", "exec", db, "psql", "-U", "nestaprime", "-d", "nestaprime_estimator", "-c", "ALTER DATABASE nestaprime_estimator SET default_transaction_read_only=on"])
        self.hook = readonly_rehearsal
        _, record = self.release("backup-restore")
        self.assertTrue(record["backup_readable"])
        self.assertFalse(record.get("backup_restore_rehearsed", False))
        self.unchanged(record)

    def test_backend_replacement_failure(self):
        self.cfg["health_seconds"] = 10
        self.bundle("backend-failure")
        _, record = self.release("backend-readiness")
        self.assertTrue(record["mutation_started"])
        self.assertEqual(record["status"], "failed-needs-recovery")
        self.assertEqual(self.link.resolve(), self.root / "bootstrap")
        self.assertEqual(record["backend_state"]["status"], "exited")
        self.assertEqual(record["backend_state"]["exit_code"], 42)
        self.assertEqual(record["backend_state"]["restart_count"], 0)
        backend = run(self.compose + ["ps", "-a", "-q", "backend"]).decode().strip()
        self.assertEqual(run(["docker", "inspect", "-f", "{{.HostConfig.RestartPolicy.Name}}", backend]).strip(), b"no")
        self.assertFalse(record.get("frontend_switched", False))

    def test_replacement_missing_container_id(self):
        self.cfg["health_seconds"] = 3
        removed = []
        def remove_replacement(step, args):
            if step == "backend.running-container" and not removed:
                backend = run(self.compose + ["ps", "-a", "-q", "backend"]).decode().strip()
                self.assertTrue(backend)
                run(["docker", "rm", "-f", backend])
                removed.append(True)
        self.hook = remove_replacement
        _, record = self.release("backend-readiness")
        self.assertTrue(removed and record["mutation_started"])
        self.assertEqual(record["backend_state"], {"status": "missing"})
        self.assertFalse(any(e["step"] == "backend.running-image" for e in record["events"]))
        self.assertEqual(record["status"], "failed-needs-recovery")
        self.assertEqual(self.link.resolve(), self.root / "bootstrap")
        self.assertFalse(record.get("frontend_switched", False))

    def test_running_replacement_never_ready(self):
        self.cfg["health_seconds"] = 5
        self.bundle("backend-unready")
        _, record = self.release("backend-readiness")
        self.assertTrue(record["mutation_started"])
        self.assertEqual(record["backend_state"]["status"], "running")
        self.assertTrue(record["backend_state"]["running"])
        self.assertEqual(record["backend_state"]["exit_code"], 0)
        self.assertEqual(record["status"], "failed-needs-recovery")
        self.assertEqual(self.link.resolve(), self.root / "bootstrap")
        self.assertFalse(record.get("frontend_switched", False))

    def test_static_health_without_database_not_ready(self):
        # Let real backend startup reach its healthy response before injecting
        # the DB fault. The DB negative control remains separately bounded.
        self.cfg["health_seconds"] = 60
        done = []
        def stop_db(step, args):
            if step == "backend.http" and not hasattr(self, "diagnostic"):
                backend = run(self.compose + ["ps", "-q", "backend"]).decode().strip()
                self.diagnostic = {"backend_running": run(["docker", "inspect", "-f", "{{.State.Running}}", backend]).strip() == b"true",
                    "published_port_matches": run(["docker", "port", backend, "8000"]).decode().splitlines()[0].rsplit(":", 1)[1] == self.backend_url.split(":")[-1].split("/")[0]}
            if step == "database.backend-query" and not done:
                done.append(True)
                run(["docker", "stop", "-t", "0", self.db])
        self.hook = stop_db
        # A stalled connection may hit the process bound before the readiness
        # window. Require the exact DB step in that case; unrelated timeouts
        # cannot satisfy this negative control and timeout signals stay visible.
        _, record = self.release(("database-readiness", "command-timeout"))
        self.assertTrue(done and self.diagnostic["backend_running"] and self.diagnostic["published_port_matches"])
        self.assertTrue(record["mutation_started"])
        self.assertEqual(record["step"], "database.backend-query" if record["failure_category"] == "command-timeout" else "database.ready")
        self.assertEqual(self.link.resolve(), self.root / "bootstrap")

    def test_served_frontend_failure_recorded_after_switch(self):
        def wrong_file(step, args):
            if step == "public.file":
                (self.link / "app.js").write_text("corrupted after switch")
        self.hook = wrong_file
        _, record = self.release("served-frontend")
        self.assertTrue(record["frontend_switched"])
        self.assertEqual(record["status"], "failed-needs-recovery")

    def test_deadline_during_real_backup(self):
        def expire(step, args):
            if step == "backup.dump":
                signal.raise_signal(signal.SIGALRM)
        self.hook = expire
        _, record = self.release("deadline")
        self.unchanged(record)

    def test_termination_during_health_is_not_retried(self):
        def interrupt(step, args):
            if step == "backend.http":
                signal.raise_signal(signal.SIGTERM)
        self.hook = interrupt
        _, record = self.release("interrupted")
        self.assertTrue(record["mutation_started"])
        self.assertEqual(record["status"], "failed-needs-recovery")
        self.assertEqual(self.link.resolve(), self.root / "bootstrap")

    def test_wrong_repository_real_provenance(self):
        if not self.real_crypto:
            self.skipTest("Authenticity negative control requires real CI attestation")
        self.cfg["repository"] = "different/repository"
        _, record = self.release("authenticity")
        self.unchanged(record)

    def test_wrong_workflow_real_provenance(self):
        if not self.real_crypto:
            self.skipTest("Authenticity negative control requires real CI attestation")
        self.cfg["workflow"] = ".github/workflows/lightsail-release.yml"
        _, record = self.release("authenticity")
        self.unchanged(record)

    def test_wrong_commit_real_provenance(self):
        if not self.real_crypto:
            self.skipTest("Authenticity negative control requires real CI attestation")
        self.policy.sha = "a" * 40
        _, record = self.release("authenticity")
        self.unchanged(record)

    def test_tamper_even_with_recomputed_checksums(self):
        if not self.real_crypto:
            self.skipTest("Authenticity negative control requires real CI attestation")
        payload = self.root / "forged"
        extract_frontend(self.incoming / "release.tar", payload, FILES | {"SHA256SUMS"})
        (payload / "backend-packages.txt").write_text("changed and checksums recomputed")
        pack(payload, self.incoming / "release.tar")
        _, record = self.release("authenticity")
        self.unchanged(record)

    def clean(self):
        pid = self.root / "nginx.pid"
        if pid.exists():
            try:
                os.kill(int(pid.read_text()), 15)
            except ProcessLookupError:
                pass
        if hasattr(self, "compose"):
            subprocess.run(self.compose + ["down", "-v", "--remove-orphans"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        self.temp.cleanup()

    def tearDown(self):
        self.clean()


if __name__ == "__main__":
    unittest.main()
