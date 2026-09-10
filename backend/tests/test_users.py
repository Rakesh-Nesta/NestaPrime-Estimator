"""User Management -- not one of the blueprint's 19 ranked gaps (Part O's
data model names USERS/ROLES only as a table of the six fixed roles, no
admin-UI spec at all), but a real operational gap raised directly: before
this, a user account could only be created via a raw DB script. Director-
only: create, deactivate/reactivate, change role, reset password.

Two guardrails, enforced server-side (backend/app/api/users.py):
1. Can't deactivate your own account.
2. Can't demote or deactivate the last active Director.

Plus a forced-password-change flow: any account just created or
password-reset gets must_change_password=True, and every protected
endpoint (require_roles, core/auth.py) blocks that user with a 403 until
POST /auth/change-password clears it -- real backend enforcement, not
just a frontend prompt, so a leaked token tied to a Director-issued
temporary password can't be used for anything else."""

from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _sales_headers(client, db_session):
    user = User(
        name="Test Sales", email="sales-users@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.SALES,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales-users@test.local")


def _second_director(client, headers, email="second-director@test.local"):
    res = client.post(
        "/users",
        json={"name": "Second Director", "email": email, "role": "director", "password": "TestPass!1"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------------------
# Role gate
# ---------------------------------------------------------------------------


def test_sales_cannot_list_or_create_users(client, director_user, db_session):
    sales_headers = _sales_headers(client, db_session)
    assert client.get("/users", headers=sales_headers).status_code == 403
    res = client.post(
        "/users",
        json={"name": "X", "email": "x@test.local", "role": "pm", "password": "TestPass!1"},
        headers=sales_headers,
    )
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def test_director_can_create_a_user(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/users",
        json={"name": "New PM", "email": "new-pm@test.local", "role": "pm", "password": "TestPass!1"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["role"] == "pm"
    assert body["is_active"] is True
    assert body["must_change_password"] is True
    assert "password" not in body
    assert "hashed_password" not in body


def test_creating_a_user_with_duplicate_email_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    client.post(
        "/users",
        json={"name": "First", "email": "dup@test.local", "role": "pm", "password": "TestPass!1"},
        headers=headers,
    )
    res = client.post(
        "/users",
        json={"name": "Second", "email": "dup@test.local", "role": "sales", "password": "TestPass!1"},
        headers=headers,
    )
    assert res.status_code == 409


def test_list_users_includes_created_user(client, director_user):
    headers = _director_headers(client, director_user)
    client.post(
        "/users",
        json={"name": "List Probe", "email": "list-probe@test.local", "role": "pm", "password": "TestPass!1"},
        headers=headers,
    )
    users = client.get("/users", headers=headers).json()
    assert any(u["email"] == "list-probe@test.local" for u in users)


# ---------------------------------------------------------------------------
# Forced password change -- backend-enforced, not just a frontend prompt
# ---------------------------------------------------------------------------


def test_direct_orm_construction_still_defaults_to_false(db_session):
    """The regression test that protects the existing suite: the model's
    Python-level default is False, so any of the many existing tests
    (and fixtures like conftest's director_user) that build a User(...)
    directly and immediately call other endpoints are unaffected -- only
    create_user and reset_password ever set this True."""
    user = User(name="Plain Build", email="plain-build@test.local", hashed_password=hash_password("x"), role=UserRole.PM)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    assert user.must_change_password is False


def test_admin_created_user_has_flag_true_vs_direct_construct_false(client, director_user):
    """Same guarantee, exercised end-to-end through the actual API rather
    than the ORM directly."""
    headers = _director_headers(client, director_user)
    res = client.post(
        "/users",
        json={"name": "Via API", "email": "via-api@test.local", "role": "pm", "password": "TestPass!1"},
        headers=headers,
    )
    assert res.json()["must_change_password"] is True


def test_new_user_is_blocked_from_other_endpoints_until_password_changed(client, director_user):
    headers = _director_headers(client, director_user)
    client.post(
        "/users",
        json={"name": "Gated User", "email": "gated@test.local", "role": "pm", "password": "TempPass!1"},
        headers=headers,
    )
    new_headers = _login(client, "gated@test.local", "TempPass!1")

    # /auth/me and /auth/login stay reachable -- the frontend needs /me to
    # even discover the flag.
    me = client.get("/auth/me", headers=new_headers)
    assert me.status_code == 200
    assert me.json()["must_change_password"] is True

    # Every other protected endpoint (require_roles) is blocked, 403, not
    # just hidden in a UI the caller isn't using.
    blocked = client.get("/sports", headers=new_headers)
    assert blocked.status_code == 403
    assert "Password change required" in blocked.json()["detail"]

    change_res = client.post(
        "/auth/change-password",
        json={"current_password": "TempPass!1", "new_password": "MyOwnPass!2"},
        headers=new_headers,
    )
    assert change_res.status_code == 200, change_res.text
    assert change_res.json()["must_change_password"] is False

    # Old token still carries the same user row -- must_change_password is
    # read fresh from the DB on every request, so the same token that was
    # blocked a moment ago now works.
    now_allowed = client.get("/sports", headers=new_headers)
    assert now_allowed.status_code == 200

    # Confirm login with the new password too.
    relogin = client.post("/auth/login", data={"username": "gated@test.local", "password": "MyOwnPass!2"})
    assert relogin.status_code == 200


def test_change_password_requires_correct_current_password(client, director_user):
    headers = _director_headers(client, director_user)
    client.post(
        "/users",
        json={"name": "Wrong Pass User", "email": "wrongpass@test.local", "role": "pm", "password": "TempPass!1"},
        headers=headers,
    )
    new_headers = _login(client, "wrongpass@test.local", "TempPass!1")

    res = client.post(
        "/auth/change-password",
        json={"current_password": "NotTheRealPassword", "new_password": "MyOwnPass!2"},
        headers=new_headers,
    )
    assert res.status_code == 400
    # Still blocked -- the failed attempt didn't clear the flag.
    still_blocked = client.get("/sports", headers=new_headers)
    assert still_blocked.status_code == 403


def test_reset_password_sets_must_change_password_true_again(client, director_user):
    headers = _director_headers(client, director_user)
    create_res = client.post(
        "/users",
        json={"name": "Reset User", "email": "reset-user@test.local", "role": "pm", "password": "TempPass!1"},
        headers=headers,
    )
    user_id = create_res.json()["id"]

    # Clear the flag once, like a normal onboarding.
    first_login = _login(client, "reset-user@test.local", "TempPass!1")
    client.post(
        "/auth/change-password",
        json={"current_password": "TempPass!1", "new_password": "SelfChosen!1"},
        headers=first_login,
    )
    assert client.get("/sports", headers=first_login).status_code == 200

    # Director resets it -- must_change_password flips back to True.
    reset_res = client.post(
        f"/users/{user_id}/reset-password", json={"new_password": "DirectorReset!1"}, headers=headers
    )
    assert reset_res.status_code == 200, reset_res.text
    assert reset_res.json()["must_change_password"] is True

    reset_login = _login(client, "reset-user@test.local", "DirectorReset!1")
    assert client.get("/sports", headers=reset_login).status_code == 403


# ---------------------------------------------------------------------------
# Guardrail 1: can't deactivate your own account
# ---------------------------------------------------------------------------


def test_cannot_deactivate_own_account(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.patch(f"/users/{director_user.id}", json={"is_active": False}, headers=headers)
    assert res.status_code == 400
    assert "cannot deactivate your own account" in res.json()["detail"].lower()


def test_can_deactivate_another_users_account(client, director_user):
    headers = _director_headers(client, director_user)
    create_res = client.post(
        "/users",
        json={"name": "Deactivate Me", "email": "deactivate-me@test.local", "role": "pm", "password": "TestPass!1"},
        headers=headers,
    )
    user_id = create_res.json()["id"]
    res = client.patch(f"/users/{user_id}", json={"is_active": False}, headers=headers)
    assert res.status_code == 200
    assert res.json()["is_active"] is False

    # A deactivated user can no longer log in at all (get_current_user's
    # own existing is_active check, unrelated to must_change_password).
    login_res = client.post("/auth/login", data={"username": "deactivate-me@test.local", "password": "TestPass!1"})
    assert login_res.status_code == 401


# ---------------------------------------------------------------------------
# Guardrail 2: can't demote or deactivate the last active Director
# ---------------------------------------------------------------------------


def test_cannot_demote_the_sole_director(client, director_user):
    """The fixture director is the only Director in the DB -- demoting
    themselves would leave zero, so it's blocked even though this is a
    self-role-change (guardrail 1 only covers deactivation, not role)."""
    headers = _director_headers(client, director_user)
    res = client.patch(f"/users/{director_user.id}", json={"role": "pm"}, headers=headers)
    assert res.status_code == 400
    assert "last active Director" in res.json()["detail"]


def test_can_demote_a_director_when_another_active_director_remains(client, director_user):
    headers = _director_headers(client, director_user)
    second = _second_director(client, headers)

    res = client.patch(f"/users/{second['id']}", json={"role": "pm"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["role"] == "pm"


def test_cannot_demote_the_last_active_director_even_when_not_self(client, director_user):
    headers = _director_headers(client, director_user)
    second = _second_director(client, headers)

    # `second` was created via the API, so it carries must_change_password
    # -- clear that first so the request below reaches the guardrail logic
    # rather than being blocked earlier by the password gate.
    second_headers = _login(client, second["email"])
    client.post(
        "/auth/change-password",
        json={"current_password": "TestPass!1", "new_password": "SecondOwn!1"},
        headers=second_headers,
    )

    # Demote the fixture director down to pm first (leaves `second` as the
    # only Director) -- allowed, since `second` is still active.
    demote_res = client.patch(f"/users/{director_user.id}", json={"role": "pm"}, headers=headers)
    assert demote_res.status_code == 200, demote_res.text

    # Now, as `second` (the sole remaining Director), try to demote
    # themselves -- must still be blocked.
    res = client.patch(f"/users/{second['id']}", json={"role": "pm"}, headers=second_headers)
    assert res.status_code == 400
    assert "last active Director" in res.json()["detail"]


def test_deactivating_a_non_self_director_succeeds_when_another_remains_active(client, director_user):
    """Guardrail 2's deactivation branch exists for defense-in-depth (see
    update_user's own docstring) -- in practice it's only reachable via
    self, which guardrail 1 already blocks, since the acting Director is
    always active themselves. This confirms the guard doesn't
    over-trigger: deactivating a DIFFERENT Director, with the actor's own
    active Director-ship still counted, must succeed."""
    headers = _director_headers(client, director_user)
    second = _second_director(client, headers)

    res = client.patch(f"/users/{second['id']}", json={"is_active": False}, headers=headers)
    assert res.status_code == 200
    assert res.json()["is_active"] is False


def test_active_director_count_helper_excludes_only_the_named_user(client, director_user, db_session):
    """Direct check of the counting logic guardrail 2 relies on."""
    from app.api.users import _active_director_count

    headers = _director_headers(client, director_user)
    second = _second_director(client, headers)
    import uuid

    second_id = uuid.UUID(second["id"])

    # Two active Directors: excluding either one still counts the other.
    assert _active_director_count(db_session, exclude_id=director_user.id) == 1
    assert _active_director_count(db_session, exclude_id=second_id) == 1

    # Deactivate `second` directly -- now excluding the fixture director
    # (the only one left, and it's inactive-excluded-by-id, not by
    # status) counts zero active Directors besides them.
    row = db_session.query(User).filter(User.id == second_id).first()
    row.is_active = False
    db_session.commit()
    assert _active_director_count(db_session, exclude_id=director_user.id) == 0
