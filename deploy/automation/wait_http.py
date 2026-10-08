"""Bounded HTTP readiness for disposable services; never accept wrong content."""
import argparse
import hashlib
import http.client
import json
from pathlib import Path
import time
import urllib.error
import urllib.request


def wait_http(url, *, kind, expected=None, timeout=60, interval=1, request_timeout=2):
    deadline = time.monotonic() + timeout
    attempts = 0
    last_error = "no response"
    while time.monotonic() < deadline:
        attempts += 1
        remaining = deadline - time.monotonic()
        try:
            with urllib.request.urlopen(url, timeout=min(request_timeout, remaining)) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP {response.status}; expected 200")
                chunks = []
                size = 0
                limit = len(expected) if kind == "frontend" and expected is not None else 65536
                while True:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("deadline reached while reading response")
                    chunk = response.read1(65536)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > limit:
                        raise ValueError("response exceeds expected content size")
                    chunks.append(chunk)
                body = b"".join(chunks)
            if kind == "health":
                if json.loads(body).get("status") != "ok":
                    raise ValueError("health response did not report status=ok")
            elif kind == "frontend":
                if body != expected:
                    raise ValueError("frontend content mismatch: received sha256=" + hashlib.sha256(body).hexdigest())
            else:
                raise ValueError("unknown readiness kind")
            print(f"READY: {kind}, {attempts} attempt(s), verified response")
            return body
        except (OSError, urllib.error.URLError, http.client.HTTPException, ValueError, AttributeError) as error:
            # No response body, environment or credentials in diagnostics.
            last_error = f"{type(error).__name__}: {error}"
            if isinstance(error, urllib.error.HTTPError):
                error.close()
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(interval, remaining))
    raise TimeoutError(f"{kind} readiness deadline ({timeout}s) expired after {attempts} attempt(s); last failure: {last_error}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--kind", choices=["health", "frontend"], required=True)
    parser.add_argument("--expected-file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()
    assert args.timeout > 0
    assert args.kind != "frontend" or args.expected_file is not None
    try:
        result = wait_http(args.url, kind=args.kind,
            expected=args.expected_file.read_bytes() if args.expected_file else None, timeout=args.timeout)
        args.output.write_bytes(result)
    except TimeoutError as error:
        parser.exit(1, f"FAIL: {error}\n")
