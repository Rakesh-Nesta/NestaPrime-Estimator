"""JWT migration (decision D4): the password-change transaction.

Authenticate normally, stage the change, sign the re-issued token from the NEW password fingerprint BEFORE committing, roll back
explicitly on a signing failure, and release a token only after a successful commit. On any reported commit failure: attempt a
rollback, return no token, and say the change could not be confirmed -- never claiming a rollback reversed a completed commit.
Database truth is read over a SEPARATE connection, so a staged-but-uncommitted change cannot masquerade as committed."""

import pytest
from sqlalchemy import text

from app.api import auth as api_auth
from app.core.security import hash_password, password_fingerprint
from app.models.user import User, UserRole
from tests.conftest import engine

OLD_PASSWORD = "TestPass!1"
NEW_PASSWORD = "NewPass!Secure2"


@pytest.fixture()
def account(db_session):
    user = User(
        name="Change Password",
        email="changer@test.local",
        hashed_password=hash_password(OLD_PASSWORD),
        role=UserRole.SALES,
        must_change_password=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _login(client, password):
    return client.post("/auth/login", data={"username": "changer@test.local", "password": password})


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _change(client, token):
    return client.post("/auth/change-password", json={"current_password": OLD_PASSWORD, "new_password": NEW_PASSWORD}, headers=_bearer(token))


def _stored(user_id):
    """(password hash, must_change_password, audit rows for a password change) as the DATABASE has them."""
    with engine.connect() as connection:
        row = connection.execute(text("SELECT hashed_password, must_change_password FROM users WHERE id = :i"), {"i": user_id}).one()
        audits = connection.execute(text("SELECT count(*) FROM audit_log_entries WHERE field = 'password'")).scalar_one()
    return row[0], row[1], audits


def _signed_in(client):
    response = _login(client, OLD_PASSWORD)
    assert response.status_code == 200
    return response.json()["access_token"]


# ---- failure point 1: the signing step, before anything is committed -----------------------------------------------------------------


def test_a_signing_failure_at_reissuance_rolls_back_the_staged_change_and_leaves_the_old_session_usable(client, account, monkeypatch):
    from app.core import security

    token = _signed_in(client)
    before = _stored(account.id)
    assert before[1] is True and before[2] == 0

    def reissuance_fails(*args, **kwargs):
        raise security.SigningKeyUnavailable()

    # The fault is injected SPECIFICALLY at token reissuance, after normal authentication (authenticating needs the key).
    monkeypatch.setattr(api_auth, "create_access_token", reissuance_fails)
    response = _change(client, token)
    assert response.status_code == 503
    assert response.json() == {"detail": security.SIGNING_UNAVAILABLE_DETAIL}
    assert _stored(account.id) == before  # hash, must-change flag and audit row all rolled back

    monkeypatch.undo()  # remove the fault
    assert client.get("/auth/me", headers=_bearer(token)).status_code == 200  # the old token is still usable
    assert _login(client, OLD_PASSWORD).status_code == 200
    assert _login(client, NEW_PASSWORD).status_code == 401


def test_a_signing_failure_keeps_the_sanitized_503_even_when_the_rollback_also_fails(client, db_session, account, monkeypatch, caplog, capsys):
    """Authenticate normally, inject SigningKeyUnavailable at token reissuance, then make the rollback itself raise a fabricated sensitive
    diagnostic. The response must still be the fixed 503 with no token, nothing may be committed, no cleanup diagnostic may escape, and
    the plan makes no claim that the rollback succeeded (the staged changes were simply never committed)."""
    from app.core import security

    token = _signed_in(client)
    before = _stored(account.id)
    commits, rollbacks = [], []
    real_commit = db_session.commit

    def counting_commit():
        commits.append("commit")
        return real_commit()

    def rollback_fails():
        rollbacks.append("rollback")
        raise RuntimeError(FABRICATED_FAULT)

    def reissuance_fails(*args, **kwargs):
        raise security.SigningKeyUnavailable()

    monkeypatch.setattr(api_auth, "create_access_token", reissuance_fails)
    monkeypatch.setattr(db_session, "commit", counting_commit)
    monkeypatch.setattr(db_session, "rollback", rollback_fails)
    response = _change(client, token)  # an escaped diagnostic would raise out of the test client here

    assert response.status_code == 503
    assert response.json() == {"detail": security.SIGNING_UNAVAILABLE_DETAIL}  # the ORIGINAL sanitized signing error, unchanged
    assert "access_token" not in response.text
    assert rollbacks == ["rollback"]  # the rollback was attempted exactly once
    assert commits == []  # nothing was committed
    for leaked in ("leakpass", "leakuser", "leak.invalid", "connection failure"):
        assert leaked not in response.text and leaked not in caplog.text
        captured = capsys.readouterr()
        assert leaked not in captured.out and leaked not in captured.err
    assert "rolled back" not in response.text.lower()  # no claim that the rollback succeeded

    monkeypatch.undo()
    db_session.rollback()  # test hygiene only: drop the staged-but-never-committed state left by the failed rollback
    assert _stored(account.id) == before  # the database never saw the change
    assert client.get("/auth/me", headers=_bearer(token)).status_code == 200


# ---- failure point 2: the commit --------------------------------------------------------------------------------------------------


def _recording_rollback(db_session, monkeypatch):
    calls = []
    real_rollback = db_session.rollback

    def rollback():
        calls.append("rollback")
        return real_rollback()

    monkeypatch.setattr(db_session, "rollback", rollback)
    return calls


FABRICATED_FAULT = "fabricated connection failure postgresql://leakuser:leakpass@leak.invalid/leakdb"


def test_a_commit_failure_reported_before_the_database_applied_it_returns_no_token_and_says_it_could_not_be_confirmed(
    client, db_session, account, monkeypatch
):
    token = _signed_in(client)
    before = _stored(account.id)
    rollbacks = _recording_rollback(db_session, monkeypatch)

    def commit_fails_without_executing():
        raise RuntimeError(FABRICATED_FAULT)

    monkeypatch.setattr(db_session, "commit", commit_fails_without_executing)
    response = _change(client, token)
    assert response.status_code == 503
    assert response.json() == {"detail": api_auth.PASSWORD_CHANGE_UNCONFIRMED_DETAIL}
    assert "access_token" not in response.text and "leakpass" not in response.text
    assert rollbacks, "a rollback must at least be attempted"

    monkeypatch.undo()
    assert _stored(account.id) == before
    assert client.get("/auth/me", headers=_bearer(token)).status_code == 200


def test_a_failure_after_a_durable_commit_returns_no_token_and_never_claims_the_change_was_reversed(client, db_session, account, monkeypatch):
    token = _signed_in(client)
    before = _stored(account.id)
    real_commit = db_session.commit
    _recording_rollback(db_session, monkeypatch)

    def commit_then_fail():
        real_commit()  # the database really commits...
        raise RuntimeError(FABRICATED_FAULT)  # ...and then the connection reports an error

    monkeypatch.setattr(db_session, "commit", commit_then_fail)
    response = _change(client, token)
    assert response.status_code == 503
    assert response.json() == {"detail": api_auth.PASSWORD_CHANGE_UNCONFIRMED_DETAIL}  # the same "could not be confirmed" text
    assert "access_token" not in response.text and "leakpass" not in response.text

    monkeypatch.undo()
    hashed, must_change, audits = _stored(account.id)
    assert hashed != before[0] and must_change is False and audits == 1  # the change IS durable
    assert _login(client, NEW_PASSWORD).status_code == 200  # the new password signs in
    assert client.get("/auth/me", headers=_bearer(token)).status_code == 401  # and the old session ended (fingerprint changed)


# ---- success -----------------------------------------------------------------------------------------------------------------------


def test_success_releases_the_token_only_after_the_commit_and_it_carries_the_new_fingerprint(client, account):
    old_token = _signed_in(client)
    response = _change(client, old_token)
    assert response.status_code == 200, response.text
    new_token = response.json()["access_token"]
    hashed, must_change, audits = _stored(account.id)
    assert must_change is False and audits == 1
    from app.core.security import decode_access_token

    assert decode_access_token(new_token)["pwv"] == password_fingerprint(hashed)
    assert client.get("/auth/me", headers=_bearer(new_token)).status_code == 200
    assert client.get("/auth/me", headers=_bearer(old_token)).status_code == 401
