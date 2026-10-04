"""Bounded pilot rehearsal, NOT a maximum-capacity or all-format benchmark.

Host mode samples Docker memory during real TCP HTTP requests to two Gunicorn
workers. Client mode creates synthetic records only in the named disposable DB.
No production credentials, delivery calls, migrations, or table deletion.
"""
import argparse
import concurrent.futures
import io
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time
import uuid

IMAGE = "sha256:8261e6258f5110da2cdfe98cc0616af1515e939b33ec8ecefd720f9eed7baa2a"
NETWORK = "nestaprime-rehearsal-internal"
NAMES = ["nestaprime-rehearsal-backend", "nestaprime-rehearsal-db", "nestaprime-clamav"]
CLIENT = "nestaprime-rehearsal-load-client"
BASE = "http://nestaprime-rehearsal-backend:8000"


class CheckFailure(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise CheckFailure(message)


def run_client():
    import httpx
    from PIL import Image
    from sqlalchemy import select
    from sqlalchemy.engine import make_url
    sys.path.insert(0, "/app")
    from app.config import settings
    from app.core.security import hash_password
    from app.db.session import SessionLocal
    from app.models.document import Quotation, QuotationStatus
    from app.models.user import User, UserRole

    url = make_url(settings.database_url)
    require(url.host == "nestaprime-rehearsal-db" and url.database == "nestaprime_estimator",
            "Refusing a database other than the disposable rehearsal DB")
    # Never patch a live application's settings or credentials.
    with SessionLocal() as db:
        quotation = db.execute(select(Quotation).where(Quotation.status == QuotationStatus.DRAFT).limit(1)).scalar_one()
        qid = str(quotation.id)
        password = secrets.token_urlsafe(24) + "Aa!7"
        user = User(name="Disposable load rehearsal", email=f"load-{uuid.uuid4().hex}@example.invalid",
                    hashed_password=hash_password(password), role=UserRole.DIRECTOR,
                    is_active=True, must_change_password=False)
        db.add(user)
        db.commit()
        email = user.email
    timeout = httpx.Timeout(90, connect=10)
    with httpx.Client(base_url=BASE, timeout=timeout, trust_env=False) as client:
        response = client.post("/auth/login", data={"username": email, "password": password})
        require(response.status_code == 200, f"Login HTTP {response.status_code}")
        headers = {"Authorization": "Bearer " + response.json()["access_token"]}
        check = client.get(f"/quotations/{qid}/pdf-check", headers=headers)
        require(check.status_code == 200 and check.json()["included_images"] == 0
                and check.json()["complete"], "Fixture requires a draft with no selected photos; do not blindly rerun")
    photos = []
    for i in range(2):
        # Distinct noisy RGB images prevent PDF-library deduplication. 12 Mpx each.
        with Image.effect_noise((4000, 3000), 45 + i * 10) as gray:
            with gray.convert("RGB") as rgb:
                buffer = io.BytesIO()
                rgb.save(buffer, format="JPEG", quality=85)
                photos.append(buffer.getvalue())
    print(json.dumps({"fixture": "two distinct 4000x3000 RGB JPEGs", "jpeg_bytes": list(map(len, photos)),
                      "limits": "synthetic photos; no real logo, 100MiB file, scanner update, nginx, or provider test"}), flush=True)

    def upload(index, tag):
        with httpx.Client(base_url=BASE, timeout=timeout, trust_env=False) as client:
            r = client.post("/attachments", headers=headers,
                            data={"doc_type": "quotation", "doc_id": qid, "tag": tag},
                            files={"file": (f"load-{index}.jpg", photos[index % 2], "image/jpeg")})
            require(r.status_code == 201, f"Upload HTTP {r.status_code}")
            require(bool(r.json().get("id")), "Upload response missing attachment id")
            return len(photos[index % 2])

    upload(0, "photo")
    upload(1, "photo")
    with httpx.Client(base_url=BASE, timeout=timeout, trust_env=False) as client:
        r = client.get(f"/quotations/{qid}/pdf-check", headers=headers)
        require(r.status_code == 200 and r.json()["complete"] and r.json()["included_images"] == 2,
                "Both fixture photos must be included before testing PDF generation")

    def operation(kind, index, barrier):
        barrier.wait(timeout=15)
        started = time.monotonic()
        if kind == "upload":
            size = upload(index, "reference")  # does not change the PDF's selected images
        else:
            with httpx.Client(base_url=BASE, timeout=timeout, trust_env=False) as client:
                with client.stream("GET", f"/quotations/{qid}/pdf", headers=headers) as r:
                    require(r.status_code == 200, f"PDF HTTP {r.status_code}")
                    size, prefix = 0, b""
                    for chunk in r.iter_bytes():
                        prefix = (prefix + chunk[:8])[:8]
                        size += len(chunk)
                        require(size <= 64 * 1024 * 1024, "PDF exceeds rehearsal client bound")
                    require(prefix.startswith(b"%PDF-") and size > 1024, "Incomplete PDF response")
        return {"operation": kind, "seconds": round(time.monotonic() - started, 3), "bytes": size}

    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for batch in range(4):
            barrier = threading.Barrier(4)
            futures = [pool.submit(operation, kind, batch * 4 + i, barrier)
                       for i, kind in enumerate(("pdf", "pdf", "upload", "upload"))]
            for future in futures:
                result = future.result()
                records.append(result)
                print(json.dumps(result), flush=True)
    print(f"LOAD_CHECK=PASS; requests={len(records)}; PDFs=8; concurrent_scanned_uploads=8; fixture_uploads=2", flush=True)
    print("Disposable DB and upload files contain test records; NEVER promote them.", flush=True)


def docker(*args):
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=20, check=True).stdout


def memory_bytes(value):
    units = {"B": 1, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3}
    for unit in ("GiB", "MiB", "KiB", "B"):
        if value.endswith(unit):
            return float(value[:-len(unit)]) * units[unit]
    raise RuntimeError("Unrecognized Docker memory unit")


def run_host():
    require(socket.gethostname() == "ip-172-26-8-254", "Refusing an unexpected host")
    require(os.geteuid() == 0, "Host mode needs sudo for Docker sampling")
    script = Path(__file__).resolve()
    directory = Path("/home/ubuntu/nestaprime-rehearsal")
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    log = directory / f"load-{stamp}.log"
    samples = directory / f"load-{stamp}-resources.jsonl"
    before = {name: json.loads(docker("inspect", "--format", "{{json .State}}", name)) for name in NAMES}
    require(all(state["Running"] and not state["OOMKilled"] for state in before.values()), "A rehearsal service is not running normally")
    command = ["docker", "run", "--rm", "--name", CLIENT, "--network", NETWORK,
               "--memory=512m", "--memory-swap=512m", "--cpus=0.5",
               "--mount", f"type=bind,source={script},target=/app/scripts/verify_release_load.py,readonly",
               "-e", "DATABASE_URL=postgresql+psycopg://nestaprime@nestaprime-rehearsal-db/nestaprime_estimator",
               "-e", "SECRET_KEY=disposable-load-client-only", "--entrypoint", "python", IMAGE,
               "scripts/verify_release_load.py", "--client", "--confirm-disposable"]
    peak = {name: 0 for name in NAMES}
    available_min = float("inf")
    sampled = 0
    started = time.monotonic()
    with log.open("x") as output, samples.open("x") as resource_log:
        process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)
        try:
            while process.poll() is None:
                require(time.monotonic() - started < 600, "Ten-minute rehearsal deadline exceeded")
                rows = [json.loads(line) for line in docker("stats", "--no-stream", "--format", "{{json .}}", *NAMES).splitlines()]
                require({row["Name"] for row in rows} == set(NAMES), "Missing resource sample")
                for row in rows:
                    peak[row["Name"]] = max(peak[row["Name"]], memory_bytes(row["MemUsage"].split(" / ")[0]))
                available = int(next(line.split()[1] for line in Path("/proc/meminfo").read_text().splitlines()
                                     if line.startswith("MemAvailable:"))) * 1024
                available_min = min(available_min, available)
                resource_log.write(json.dumps({"elapsed": round(time.monotonic()-started, 2), "docker": rows,
                                               "host_mem_available": available}) + "\n")
                resource_log.flush()
                sampled += 1
                if sampled % 5 == 0:
                    print(f"Running: {int(time.monotonic()-started)} seconds; resource samples={sampled}", flush=True)
                time.sleep(1)
        except BaseException:
            subprocess.run(["docker", "rm", "-f", CLIENT], capture_output=True, timeout=20)
            process.wait(timeout=20)
            raise
        result = process.wait()
    print(log.read_text(), end="")
    print(f"LOAD_CLIENT_EXIT_CODE={result}; samples={sampled}; elapsed_seconds={round(time.monotonic()-started, 2)}")
    print("Sampled service memory maxima MiB:", {name: round(value / 1024**2, 1) for name, value in peak.items()})
    print("Minimum sampled host MemAvailable MiB:", round(available_min / 1024**2, 1))
    print("Logs:", log, samples)
    after = {name: json.loads(docker("inspect", "--format", "{{json .State}}", name)) for name in NAMES}
    stable = all(state["Running"] and not state["OOMKilled"] and state["StartedAt"] == before[name]["StartedAt"]
                 for name, state in after.items())
    print("SERVICE_STATE_CHECK=" + ("PASS" if stable else "FAIL"))
    require(result == 0 and sampled > 0 and stable, "Rehearsal failed; preserve logs and investigate")
    print("Bounded pilot result only. Samples can miss short peaks; worker recycling and kernel logs need separate review.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--host", action="store_true")
    mode.add_argument("--client", action="store_true")
    parser.add_argument("--confirm-disposable", action="store_true", required=True)
    args = parser.parse_args()
    try:
        run_host() if args.host else run_client()
    except Exception as exc:
        # Never print request headers, response documents, tokens, or DB URLs.
        print("REHEARSAL_FAILED:", str(exc) if isinstance(exc, CheckFailure) else type(exc).__name__, flush=True)
        sys.exit(1)
