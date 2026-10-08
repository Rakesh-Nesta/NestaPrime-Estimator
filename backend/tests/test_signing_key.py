"""JWT migration (python-jose -> PyJWT[crypto]): the signing key must be USABLE.

A public key's bytes -- DER, PEM -- are refused as an HMAC secret (the CVE-2026-85394 condition), an empty key is a configuration
failure, startup refuses to serve with an unusable key using a fixed message, and a usable key shorter than 32 bytes only warns.
Every value here is fabricated. The DER below is the fabricated Ed25519 SubjectPublicKeyInfo from the independent review: its bytes
are ASCII apart from NULs, so it is valid UTF-8 text and can be loaded as a `str` secret through a `.env` file."""

import base64
import hashlib
import hmac
import json
import os
import subprocess
import sys
from pathlib import Path

import jwt
import pytest

from app.config import settings

BACKEND = Path(__file__).resolve().parents[1]
PROBE = Path(__file__).resolve().parent / "signing_warning_probe.py"
FABRICATED_DER = bytes.fromhex("302a300506032b65700321005866666666666666666666666666666666666666666666666666666666666666")
assert len(FABRICATED_DER) == 44
CLAIMS = {"sub": "6f1d3c52-8a4e-4b0a-9c57-2d1e0f3a4b5c", "role": "director", "exp": 4102444800, "pwv": "0123456789abcdef"}
PEM_PUBLIC_KEY = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MCowBQYDK2VwAyEAWGZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmY=\n"
    "-----END PUBLIC KEY-----\n"
)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def forge_hs256(key: bytes, claims: dict) -> str:
    """Built by hand, INDEPENDENTLY of jwt.encode: a refusal to encode with this key cannot stop the decode test from running."""
    head = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64(json.dumps(claims).encode())
    signature = hmac.new(key, f"{head}.{body}".encode(), hashlib.sha256).digest()
    return f"{head}.{body}.{_b64(signature)}"


# ---- the DER regression: three separate tests, so none depends on another ------------------------------------------------------------


def test_cryptography_support_is_installed_and_enabled():
    """Without the `crypto` extra PyJWT cannot recognise a public key and accepts its bytes as a secret (see the DER tests)."""
    assert jwt.algorithms.has_crypto


@pytest.mark.parametrize("as_text", [False, True], ids=["bytes", "str"])
def test_decode_refuses_a_der_public_key_as_the_hmac_secret(as_text):
    forged = forge_hs256(FABRICATED_DER, CLAIMS)
    key = FABRICATED_DER.decode("utf-8") if as_text else FABRICATED_DER
    with pytest.raises(jwt.InvalidKeyError):
        jwt.decode(forged, key, algorithms=["HS256"])


@pytest.mark.parametrize("as_text", [False, True], ids=["bytes", "str"])
def test_encode_refuses_a_der_public_key_as_the_hmac_secret(as_text):
    key = FABRICATED_DER.decode("utf-8") if as_text else FABRICATED_DER
    with pytest.raises(jwt.InvalidKeyError):
        jwt.encode({"sub": "x"}, key, algorithm="HS256")


def test_startup_validation_refuses_a_der_secret(monkeypatch):
    from app.core import security

    monkeypatch.setattr(settings, "secret_key", FABRICATED_DER.decode("utf-8"))
    with pytest.raises(RuntimeError) as failure:
        security.require_usable_signing_key()
    assert str(failure.value) == security.STARTUP_FAILURE_MESSAGE


# ---- the validator -----------------------------------------------------------------------------------------------------------------


def test_the_test_secret_is_at_least_32_bytes():
    """A guard on the CI/dev placeholder: PyJWT warns on a shorter HS256 secret (31 bytes warns, 32 does not)."""
    assert len(settings.secret_key.encode("utf-8")) >= 32


def test_a_usable_key_passes_startup_validation():
    from app.core import security

    assert security.require_usable_signing_key() is None


@pytest.mark.parametrize(
    "unusable", ["", "   ", PEM_PUBLIC_KEY, FABRICATED_DER.decode("utf-8")], ids=["empty", "blank", "pem-public-key", "der-public-key"]
)
def test_an_unusable_key_fails_startup_validation_with_the_fixed_message_only(monkeypatch, unusable):
    from app.core import security

    monkeypatch.setattr(settings, "secret_key", unusable)
    with pytest.raises(RuntimeError) as failure:
        security.require_usable_signing_key()
    assert str(failure.value) == security.STARTUP_FAILURE_MESSAGE
    assert failure.value.__cause__ is None and failure.value.__suppress_context__  # the original exception is not carried
    for fragment in (unusable.strip(), "BEGIN PUBLIC", "MCowBQYD"):
        if fragment:
            assert fragment not in str(failure.value)


def _start_the_application(tmp_path, env_extra=None, dotenv=None):
    env = {k: v for k, v in os.environ.items() if k.upper() not in ("SECRET_KEY", "DATABASE_URL")}
    env.update(DATABASE_URL="postgresql+psycopg://fabricated:fabricated@127.0.0.1:1/fabricated", PYTHONPATH=str(BACKEND), PYTHONUTF8="1")
    env.update(env_extra or {})
    if dotenv is not None:
        (tmp_path / ".env").write_text(dotenv, encoding="utf-8", newline="")
    return subprocess.run([sys.executable, "-c", "import app.main"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=180)


@pytest.mark.parametrize(
    "case",
    ["empty-env", "pem-env", "der-dotenv"],
)
def test_the_application_refuses_to_start_with_an_unusable_key_and_prints_no_key_text(tmp_path, case):
    """Subprocess. A framework traceback MAY remain; what is asserted is a non-zero exit, the fixed message, and no key text."""
    from app.core import security

    secret_text = {"empty-env": "", "pem-env": PEM_PUBLIC_KEY, "der-dotenv": FABRICATED_DER.decode("utf-8")}[case]
    if case == "der-dotenv":
        proc = _start_the_application(tmp_path, dotenv='SECRET_KEY="' + secret_text + '"\n')
    else:
        proc = _start_the_application(tmp_path, env_extra={"SECRET_KEY": secret_text})
    assert proc.returncode != 0
    assert security.STARTUP_FAILURE_MESSAGE in proc.stderr
    combined = proc.stdout + proc.stderr
    for fragment in ("MCowBQYD", "BEGIN PUBLIC", FABRICATED_DER.hex(), "X" + "f" * 10):
        assert fragment not in combined
    assert secret_text.strip() == "" or secret_text.strip() not in combined


def test_the_application_starts_with_a_usable_key(tmp_path):
    proc = _start_the_application(tmp_path, env_extra={"SECRET_KEY": "start-ok-fabricated-secret-0123456789-abcdef"})
    assert proc.returncode == 0, proc.stderr


# ---- the short-key warning (decision D3): one fixed operational warning; PyJWT's own warning narrowly ignored ---------------------------
# Each in a fresh subprocess: the production filter is process-lifetime, so these must not share or reset the pytest process's state.


def _probe(mode, python_flags=()):
    env = {k: v for k, v in os.environ.items() if k.upper() not in ("SECRET_KEY", "DATABASE_URL")}
    env.update(DATABASE_URL="postgresql+psycopg://fabricated:fabricated@127.0.0.1:1/fabricated", SECRET_KEY="short-secret!", PYTHONUTF8="1")
    proc = subprocess.run([sys.executable, *python_flags, str(PROBE), mode], capture_output=True, text=True, env=env, timeout=180)
    assert proc.returncode == 0, proc.stderr
    assert proc.stderr == "", proc.stderr  # nothing reaches the real stderr either
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_repeated_initialization_warns_once_and_adds_one_filter_entry():
    result = _probe("repeat")
    assert result["secret_bytes"] < 32
    assert result["entries_after_import"] == 1 and result["entries_after_repeats"] == 1  # idempotent, including a module reload
    assert result["operational_warnings"] == 1


def test_the_filter_is_stable_and_the_short_key_warning_is_not_shown():
    result = _probe("filter_stability")
    assert result["same_filters"] is True and result["key_warnings_shown"] == 0


def test_a_short_key_still_signs_and_verifies_under_a_warnings_as_errors_setting():
    result = _probe("werror", python_flags=("-W", "error::UserWarning"))
    assert result["roundtrip_ok"] is True
    assert result["unrelated_user_warning_raises"] is True  # unrelated warnings still raise
    assert result["other_key_length_wording_raises"] is True  # a different key-length message is not swallowed


def test_unrelated_warnings_and_other_key_length_messages_are_preserved():
    shown = _probe("unrelated")["shown"]
    assert any(s.startswith("DeprecationWarning:") for s in shown)
    assert any(s.startswith("UserWarning:") for s in shown)
    assert sum(s.startswith("InsecureKeyLengthWarning:") for s in shown) == 1  # only the different (HS512) wording; the HS256 one is ignored


def test_concurrent_use_is_clean_a_smoke_check_not_a_proof_of_race_freedom():
    """The thread-safety argument rests on the lock around the once-flag and on there being no per-call mutation of global warning
    state; passing runs of this test do not prove the absence of races."""
    result = _probe("concurrency")
    assert result["errors"] == [] and result["operational_warnings"] == 1
    assert result["key_warnings_shown"] == 0 and result["same_filters"] is True


def test_an_error_filter_placed_ahead_of_ours_maps_to_the_sanitized_failures_not_a_raw_error():
    result = _probe("injected_error")
    assert result["create"] == "SigningKeyUnavailable"
    assert result["decode"] == "SigningKeyUnavailable"
    assert result["startup"] == "RuntimeError"
