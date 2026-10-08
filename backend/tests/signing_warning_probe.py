"""Subprocess helper for tests/test_signing_key.py -- NOT a test module.

Each mode runs in a FRESH interpreter so the process-wide warning filters and logging state are real (the production filter is
process-lifetime and must not be shared with, or reset by, the pytest process). Fabricated short secret supplied by the caller.
Usage: python signing_warning_probe.py <mode>   (prints one JSON object)"""

import base64
import hashlib
import hmac
import importlib
import json
import logging
import sys
import threading
import warnings

BACKEND = __import__("pathlib").Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

operational = []


class _Collect(logging.Handler):
    def emit(self, record):
        operational.append(record.getMessage())


logging.getLogger("app.security").addHandler(_Collect())

shown = []


def _record(message, category, filename, lineno, file=None, line=None):
    shown.append((category.__name__, str(message)))


warnings.showwarning = _record  # what actually reaches the user: an ignored warning never gets here

from app.config import settings  # noqa: E402
from app.core import security as sec  # noqa: E402

KEY_LENGTH = sec.jwt.InsecureKeyLengthWarning


def key_length_entries():
    return [f for f in warnings.filters if f[2] is KEY_LENGTH and f[1] is not None]


def key_length_shown():
    return [s for s in shown if s[0] == "InsecureKeyLengthWarning"]


def roundtrip(n=1):
    for _ in range(n):
        token = sec.create_access_token("11111111-1111-1111-1111-111111111111", "sales", "hash")
        assert sec.decode_access_token(token) is not None


def operational_count():
    return len([m for m in operational if "shorter than 32" in m])


mode = sys.argv[1]
out = {"mode": mode, "secret_bytes": len(settings.secret_key.encode())}

if mode == "repeat":  # repeated initialization, including a reload of the adapter module
    out["entries_after_import"] = len(key_length_entries())
    for _ in range(5):
        sec.require_usable_signing_key()
    sec = importlib.reload(sec)
    sec.require_usable_signing_key()
    out["entries_after_repeats"] = len(key_length_entries())
    out["operational_warnings"] = operational_count()

elif mode == "filter_stability":  # the loop neither shows the warning nor changes the filter list
    before = list(warnings.filters)
    roundtrip(300)
    out["same_filters"] = before == list(warnings.filters)
    out["key_warnings_shown"] = len(key_length_shown())

elif mode == "werror":  # run as `python -W error::UserWarning`: the key-length condition must not become an exception
    roundtrip(5)
    out["roundtrip_ok"] = True
    for label, make in (
        ("unrelated_user_warning", lambda: warnings.warn("unrelated", UserWarning)),
        ("other_key_length_wording", lambda: warnings.warn(
            "The HMAC key is 5 bytes long, which is below the minimum recommended length of 64 bytes for HS512. See RFC 7518.", KEY_LENGTH)),
    ):
        try:
            make()
            out[label + "_raises"] = False
        except UserWarning:
            out[label + "_raises"] = True

elif mode == "unrelated":  # other warnings are untouched; only the HS256 wording is ignored
    warnings.filterwarnings("always", category=DeprecationWarning)
    warnings.warn("a deprecation", DeprecationWarning)
    warnings.warn("unrelated", UserWarning)
    warnings.warn("The HMAC key is 5 bytes long, which is below the minimum recommended length of 64 bytes for HS512. See RFC 7518.", KEY_LENGTH)
    roundtrip(3)  # the real HS256 wording is ignored
    out["shown"] = [s[0] + ":" + s[1][:20] for s in shown]

elif mode == "concurrency":  # a smoke check, not a proof of race freedom
    errors, barrier = [], threading.Barrier(16)
    before = list(warnings.filters)

    def worker():
        try:
            barrier.wait()
            sec.require_usable_signing_key()
            roundtrip(60)
        except Exception as exc:  # noqa: BLE001
            errors.append(type(exc).__name__)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    out.update(errors=errors, operational_warnings=operational_count(), key_warnings_shown=len(key_length_shown()),
               same_filters=before == list(warnings.filters))

elif mode == "injected_error":  # a harness puts an `error` filter AHEAD of ours: must map to the sanitized failures
    warnings.filterwarnings("error", category=KEY_LENGTH)
    try:
        sec.create_access_token("11111111-1111-1111-1111-111111111111", "sales", "hash")
        out["create"] = "signed"
    except sec.SigningKeyUnavailable:
        out["create"] = "SigningKeyUnavailable"
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=")
    body = base64.urlsafe_b64encode(b'{"sub":"x","exp":4102444800}').rstrip(b"=")
    sig = base64.urlsafe_b64encode(hmac.new(settings.secret_key.encode(), header + b"." + body, hashlib.sha256).digest()).rstrip(b"=")
    token = (header + b"." + body + b"." + sig).decode()
    try:
        sec.decode_access_token(token)
        out["decode"] = "decoded"
    except sec.SigningKeyUnavailable:
        out["decode"] = "SigningKeyUnavailable"
    try:
        sec.require_usable_signing_key()
        out["startup"] = "accepted"
    except RuntimeError as exc:
        out["startup"] = "RuntimeError" if str(exc) == sec.STARTUP_FAILURE_MESSAGE else "RuntimeError(other text)"

else:
    raise SystemExit(f"unknown mode {mode}")

print(json.dumps(out))
