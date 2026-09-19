"""Amendment 18 (Section 24): login rate limiting / lockout."""

from datetime import UTC, datetime, timedelta

from app.api.auth import LOGIN_ATTEMPT_THRESHOLD
from app.models.user import User, UserRole
from app.core.security import hash_password


def _login(client, email="director@test.local", password="TestPass!1"):
    return client.post("/auth/login", data={"username": email, "password": password})


def test_five_failed_attempts_lock_the_account_even_against_the_correct_password(client, director_user):
    for _ in range(LOGIN_ATTEMPT_THRESHOLD):
        res = _login(client, password="wrong")
        assert res.status_code == 401

    # 6th attempt -- correct password, but the account is now locked.
    res = _login(client, password="TestPass!1")
    assert res.status_code == 401


def test_fewer_than_threshold_failed_attempts_do_not_lock_the_account(client, director_user):
    for _ in range(LOGIN_ATTEMPT_THRESHOLD - 1):
        res = _login(client, password="wrong")
        assert res.status_code == 401

    res = _login(client, password="TestPass!1")
    assert res.status_code == 200


def test_a_successful_login_resets_the_failed_attempt_counter(client, director_user):
    for _ in range(LOGIN_ATTEMPT_THRESHOLD - 1):
        _login(client, password="wrong")

    ok = _login(client, password="TestPass!1")
    assert ok.status_code == 200

    # The counter reset on that success -- another (threshold - 1) failed
    # attempts still shouldn't lock the account.
    for _ in range(LOGIN_ATTEMPT_THRESHOLD - 1):
        res = _login(client, password="wrong")
        assert res.status_code == 401
    res = _login(client, password="TestPass!1")
    assert res.status_code == 200


def test_lockout_is_per_account_not_global(client, director_user, db_session):
    other = User(
        name="Other User", email="other@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.SALES,
    )
    db_session.add(other)
    db_session.commit()

    for _ in range(LOGIN_ATTEMPT_THRESHOLD):
        _login(client, email="director@test.local", password="wrong")

    # director@test.local is now locked; other@test.local is unaffected.
    res = _login(client, email="other@test.local", password="TestPass!1")
    assert res.status_code == 200


def test_unknown_email_never_counts_toward_any_lockout(client, director_user):
    for _ in range(LOGIN_ATTEMPT_THRESHOLD * 2):
        res = _login(client, email="nobody@test.local", password="whatever")
        assert res.status_code == 401

    # The real account is completely unaffected by all those attempts.
    res = _login(client, password="TestPass!1")
    assert res.status_code == 200


def test_lockout_clears_after_the_window_elapses(client, director_user, db_session):
    for _ in range(LOGIN_ATTEMPT_THRESHOLD):
        _login(client, password="wrong")

    locked = _login(client, password="TestPass!1")
    assert locked.status_code == 401

    # Simulate the 15-minute window having already elapsed.
    db_user = db_session.query(User).filter(User.email == "director@test.local").first()
    db_user.locked_until = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)
    db_session.commit()

    res = _login(client, password="TestPass!1")
    assert res.status_code == 200


def test_deactivated_account_does_not_accumulate_lockout_state(client, director_user, db_session):
    """A deactivated account already can't log in -- it shouldn't also
    burn through lockout attempts, since there's nothing left for a
    lockout to protect there."""
    director_user.is_active = False
    db_session.commit()

    for _ in range(LOGIN_ATTEMPT_THRESHOLD):
        res = _login(client, password="TestPass!1")
        assert res.status_code == 401

    reactivated = db_session.query(User).filter(User.email == "director@test.local").first()
    reactivated.is_active = True
    db_session.commit()

    res = _login(client, password="TestPass!1")
    assert res.status_code == 200
