"""JWT migration: an UNUSABLE verification/signing key is a server configuration fault, never a credential fault.

One shared handler turns `SigningKeyUnavailable` into a fixed, sanitized HTTP 503 for every caller -- authentication, the global
ownership gate, login. Invalid TOKENS keep their existing behaviour (401 / pass-through). The unusable key is injected into settings
AFTER a valid token has been obtained with the usable key. All values are fabricated."""

import base64
import hashlib
import hmac
import json
import time

import jwt
import pytest

from app.config import settings
from app.models.user import UserRole
from tests.test_attachments import _director_headers
from tests.test_own_records import _switch
from tests.test_quotations_admin import _create_client_record, _role_headers

PEM_PUBLIC_KEY = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MCowBQYDK2VwAyEAWGZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmY=\n"
    "-----END PUBLIC KEY-----\n"
)
KEY_FRAGMENTS = ("MCowBQYD", "BEGIN PUBLIC")


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _hand_forged(header, claims, secret, digest=hashlib.sha256):
    head, body = _b64(json.dumps(header).encode()), _b64(json.dumps(claims).encode())
    return f"{head}.{body}.{_b64(hmac.new(secret.encode(), f'{head}.{body}'.encode(), digest).digest())}"


@pytest.fixture()
def break_the_key(monkeypatch):
    def apply():
        monkeypatch.setattr(settings, "secret_key", PEM_PUBLIC_KEY)

    return apply


def _assert_fixed_503(response, caplog):
    from app.core import security

    assert response.status_code == 503
    assert response.json() == {"detail": security.SIGNING_UNAVAILABLE_DETAIL}
    for fragment in KEY_FRAGMENTS:
        assert fragment not in response.text
        assert fragment not in caplog.text


def test_a_valid_token_with_an_unusable_key_gives_the_fixed_503_on_an_authenticated_route(client, director_user, break_the_key, caplog):
    headers = _director_headers(client, director_user)
    assert client.get("/auth/me", headers=headers).status_code == 200
    break_the_key()
    _assert_fixed_503(client.get("/auth/me", headers=headers), caplog)


def test_the_ownership_gate_does_not_turn_an_unusable_key_into_a_pass_through(client, director_user, db_session, break_the_key, caplog):
    director = _director_headers(client, director_user)
    client_id = _create_client_record(client, director, "Gate Client")
    _switch(client, director, True)
    sales = _role_headers(client, db_session, UserRole.SALES, "gate-sales@test.local")
    # sanity with the usable key: a Sales user does not own the record, so the gate answers 404
    assert client.get(f"/clients/{client_id}", headers=sales).status_code == 404
    break_the_key()
    _assert_fixed_503(client.get(f"/clients/{client_id}", headers=sales), caplog)  # not 404, not 200, not a skipped gate


def test_login_with_correct_credentials_and_an_unusable_key_is_503_not_incorrect_credentials(client, director_user, db_session, break_the_key, caplog):
    break_the_key()
    response = client.post("/auth/login", data={"username": "director@test.local", "password": "TestPass!1"})
    _assert_fixed_503(response, caplog)
    assert "Incorrect" not in response.text
    db_session.refresh(director_user)
    assert director_user.failed_login_attempts == 0 and director_user.locked_until is None  # not counted as a failed attempt


def test_a_malformed_token_is_rejected_before_the_key_is_used_even_with_an_unusable_key(client, director_user, break_the_key):
    break_the_key()
    assert client.get("/auth/me", headers=_bearer("not.a.jwt")).status_code == 401


def test_a_disallowed_algorithm_is_rejected_before_the_key_is_used_even_with_an_unusable_key(client, director_user, break_the_key):
    claims = {"sub": str(director_user.id), "role": "director", "exp": int(time.time()) + 600}
    token = _hand_forged({"alg": "HS384", "typ": "JWT"}, claims, "any-secret-at-all-0123456789-abcdef-xyz", hashlib.sha384)
    break_the_key()
    assert client.get("/auth/me", headers=_bearer(token)).status_code == 401


def test_a_well_formed_expired_token_with_an_unusable_key_gives_503_because_the_signature_step_comes_first(client, director_user, break_the_key, caplog):
    """Pins an ordering rather than assuming it: signature verification (which needs the key) precedes the expiry check."""
    expired = jwt.encode({"sub": str(director_user.id), "role": "director", "exp": int(time.time()) - 600}, settings.secret_key, algorithm="HS256")
    break_the_key()
    _assert_fixed_503(client.get("/auth/me", headers=_bearer(expired)), caplog)


def test_an_expired_token_is_rejected_with_the_existing_401_when_the_key_is_usable(client, director_user):
    from app.core.security import decode_access_token

    expired = jwt.encode(
        {"sub": str(director_user.id), "role": "director", "exp": int(time.time()) - 600, "pwv": "x"}, settings.secret_key, algorithm="HS256"
    )
    assert decode_access_token(expired) is None
    assert client.get("/auth/me", headers=_bearer(expired)).status_code == 401
