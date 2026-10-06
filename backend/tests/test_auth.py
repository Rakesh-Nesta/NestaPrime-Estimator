def test_login_with_correct_credentials_returns_token(client, director_user):
    res = client.post(
        "/auth/login",
        data={"username": "director@test.local", "password": "TestPass!1"},
    )
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_with_wrong_password_is_rejected(client, director_user):
    res = client.post(
        "/auth/login",
        data={"username": "director@test.local", "password": "wrong"},
    )
    assert res.status_code == 401


def test_login_with_unknown_email_is_rejected(client):
    res = client.post(
        "/auth/login",
        data={"username": "nobody@test.local", "password": "whatever"},
    )
    assert res.status_code == 401


def test_me_without_token_is_rejected(client):
    res = client.get("/auth/me")
    assert res.status_code == 401


def test_me_with_valid_token_returns_the_right_user(client, director_user):
    login_res = client.post(
        "/auth/login",
        data={"username": "director@test.local", "password": "TestPass!1"},
    )
    token = login_res.json()["access_token"]

    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == "director@test.local"
    assert body["role"] == "director"


def test_me_with_garbage_token_is_rejected(client):
    res = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# JWT migration (python-jose -> PyJWT[crypto]): token behaviour the migration must preserve or deliberately change.
# Decisions: D1 -- PyJWT's standard expiry boundary, no leeway; HS256 only; no new mandatory claims; the database role decides.
# ---------------------------------------------------------------------------

import base64 as _base64
import hashlib as _hashlib
import hmac as _hmac
import json as _json
import time as _time
import uuid as _uuid
from datetime import datetime as _datetime
from datetime import timezone as _timezone

import jwt as _jwt
import pytest as _pytest

from app.config import settings as _settings
from app.core import security as _security
from app.core.security import hash_password
from app.models.user import User as _User
from app.models.user import UserRole as _UserRole


def _b64(data):
    return _base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _hand_signed(header, claims, secret, digest=_hashlib.sha256):
    head, body = _b64(_json.dumps(header).encode()), _b64(_json.dumps(claims).encode())
    signature = _hmac.new(secret.encode(), f"{head}.{body}".encode(), digest).digest()
    return f"{head}.{body}.{_b64(signature)}"


def _valid_claims(**changes):
    claims = {"sub": "6f1d3c52-8a4e-4b0a-9c57-2d1e0f3a4b5c", "role": "director", "exp": int(_time.time()) + 600, "pwv": "0123456789abcdef"}
    claims.update(changes)
    return claims


def _forgeries():
    secret = _settings.secret_key
    good = _hand_signed({"alg": "HS256", "typ": "JWT"}, _valid_claims(), secret)
    return {
        "alg-none-unsigned": _b64(b'{"alg":"none","typ":"JWT"}') + "." + _b64(_json.dumps(_valid_claims()).encode()) + ".",
        "hs384-signed-with-the-real-secret": _hand_signed({"alg": "HS384", "typ": "JWT"}, _valid_claims(), secret, _hashlib.sha384),
        "rs256-header-hs256-style-signature": _hand_signed({"alg": "RS256", "typ": "JWT"}, _valid_claims(), secret),
        "tampered-signature": good[:-4] + ("AAAA" if not good.endswith("AAAA") else "BBBB"),
        "wrong-secret": _hand_signed({"alg": "HS256", "typ": "JWT"}, _valid_claims(), "another-secret-0123456789-abcdef-0123456789"),
        "malformed": "not.a.jwt",
        "empty": "",
        "numeric-sub": _hand_signed({"alg": "HS256", "typ": "JWT"}, _valid_claims(sub=123), secret),
        "non-numeric-exp": _hand_signed({"alg": "HS256", "typ": "JWT"}, _valid_claims(exp="soon"), secret),
    }


@_pytest.mark.parametrize("name", list(_forgeries().keys()))
def test_decode_access_token_refuses_every_forged_or_malformed_token(name):
    assert _security.decode_access_token(_forgeries()[name]) is None


def test_decode_access_token_accepts_a_genuine_token_with_the_unchanged_claims():
    token = _security.create_access_token("6f1d3c52-8a4e-4b0a-9c57-2d1e0f3a4b5c", "director", "stored-hash")
    payload = _security.decode_access_token(token)
    assert payload["sub"] == "6f1d3c52-8a4e-4b0a-9c57-2d1e0f3a4b5c" and payload["role"] == "director"
    assert payload["pwv"] == _security.password_fingerprint("stored-hash") and isinstance(payload["exp"], int)
    assert _jwt.get_unverified_header(token)["alg"] == "HS256"


def test_the_expiry_boundary_is_pyjwts_standard_one_without_leeway(monkeypatch):
    """D1: a token is rejected from the instant `exp` is reached (RFC 7519), where python-jose still accepted it for the whole second.
    The clock is frozen half a second into second NOW; the token is signed with the usable test secret."""
    NOW = 1900000000

    class Clock(_datetime):
        @classmethod
        def now(cls, tz=None):
            return _datetime.fromtimestamp(NOW + 0.5, tz=_timezone.utc)

    monkeypatch.setattr(_jwt.api_jwt, "datetime", Clock)

    def token(exp):
        return _jwt.encode({"sub": "x", "exp": exp}, _settings.secret_key, algorithm="HS256")

    assert _security.decode_access_token(token(NOW - 1)) is None
    assert _security.decode_access_token(token(NOW)) is None  # exp == now: rejected (python-jose accepted this)
    assert _security.decode_access_token(token(NOW + 1)) is not None


# A token minted BY PYTHON-JOSE 3.5.0 (fabricated secret and account), committed as a constant: it must keep working after the swap.
INTEROP_USER_ID = "6f1d3c52-8a4e-4b0a-9c57-2d1e0f3a4b5c"
INTEROP_SECRET = "interop-fixed-secret-0123456789abcdef-NOT-REAL"
INTEROP_PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$HUNo7T0H4Fwrxfh/D+E8Jw$+bvqXPG8u+uVO4jDNJZpD3AKW4DF6KDutSvcdQGj45g"
INTEROP_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2ZjFkM2M1Mi04YTRlLTRiMGEtOWM1Ny0yZDFlMGYzYTRiNWMiLCJyb2xlIjoiZGlyZWN0b3IiLCJleHAiOjQxMDI0NDQ4MDAsInB3diI6IjY1YzdjM2Q4ZDI1MjRkNzYifQ"
    ".hxIGruOIgidvQTW363ABCuqAS2w57y-0QV4Gk65j_iE"
)


def _interop_user(db_session, **changes):
    user = _User(
        id=_uuid.UUID(INTEROP_USER_ID), name="Interop", email="interop@test.local", hashed_password=INTEROP_PASSWORD_HASH,
        role=_UserRole.DIRECTOR,
    )
    for key, value in changes.items():
        setattr(user, key, value)
    db_session.add(user)
    db_session.commit()
    return user


def test_a_token_minted_by_python_jose_still_reaches_the_account(client, db_session, monkeypatch):
    monkeypatch.setattr(_settings, "secret_key", INTEROP_SECRET)
    _interop_user(db_session)
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {INTEROP_TOKEN}"})
    assert response.status_code == 200 and response.json()["id"] == INTEROP_USER_ID


def test_a_python_jose_token_is_still_refused_when_the_password_fingerprint_no_longer_matches(client, db_session, monkeypatch):
    monkeypatch.setattr(_settings, "secret_key", INTEROP_SECRET)
    user = _interop_user(db_session)
    user.hashed_password = hash_password("Another!Pass99")
    db_session.commit()
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {INTEROP_TOKEN}"}).status_code == 401


def test_a_python_jose_token_is_still_refused_for_a_deactivated_account(client, db_session, monkeypatch):
    monkeypatch.setattr(_settings, "secret_key", INTEROP_SECRET)
    _interop_user(db_session, is_active=False)
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {INTEROP_TOKEN}"}).status_code == 401


def test_the_database_role_not_the_token_claim_decides_authorization(client, db_session):
    """Authentication returns the DATABASE user and `require_roles` checks the database role; the token's `role` claim is never read.
    A token claiming `director` for a database-`sales` user is therefore not rejected: it authenticates as that sales user."""
    sales = _User(name="Sales", email="claimant@test.local", hashed_password=hash_password("TestPass!1"), role=_UserRole.SALES)
    db_session.add(sales)
    db_session.commit()
    claimed = _jwt.encode(
        {"sub": str(sales.id), "role": "director", "exp": int(_time.time()) + 600, "pwv": _security.password_fingerprint(sales.hashed_password)},
        _settings.secret_key, algorithm="HS256",
    )
    headers = {"Authorization": f"Bearer {claimed}"}
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200 and me.json()["role"] == "sales"  # the database role, not the claimed one
    assert client.get("/users", headers=headers).status_code == 403  # a director-only route: refused by the DATABASE role
    assert client.get("/clients", headers=headers).status_code == 200  # a route the database role allows
