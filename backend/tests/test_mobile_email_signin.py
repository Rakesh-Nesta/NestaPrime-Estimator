"""Amendment 61 (Section 64): an account with a mobile number, an email, or both -- sign-in by either."""

import uuid

import pytest

from app.core.security import decode_access_token, hash_password
from app.models.user import User, UserRole


def _login(client, username, password="TestPass!1"):
    return client.post("/auth/login", data={"username": username, "password": password})


def _director_headers(client, director_user):
    res = _login(client, "director@test.local")
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


# ---------------------------------------------------------------------------
# The token now names the user by id
# ---------------------------------------------------------------------------


def test_the_issued_token_names_the_user_by_id_not_by_email(client, director_user):
    res = _login(client, "director@test.local")
    token = res.json()["access_token"]
    payload = decode_access_token(token)
    assert payload["sub"] == str(director_user.id)
    uuid.UUID(payload["sub"])  # does not raise


def test_a_token_naming_an_email_the_old_way_is_now_refused(client, director_user):
    from app.core.security import create_access_token

    old_style_token = create_access_token(
        subject=director_user.email, role=director_user.role.value, password_hash=director_user.hashed_password
    )
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {old_style_token}"})
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Creating and signing in with a mobile-only, email-only, or both account
# ---------------------------------------------------------------------------


def test_create_a_mobile_only_user_and_sign_in_with_it(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/users",
        json={"name": "Mobile Sales", "mobile": "98765 43210", "role": "sales", "password": "TestPass!1"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["email"] is None
    assert body["mobile"] == "+919876543210"

    login_res = _login(client, "+919876543210")
    assert login_res.status_code == 200, login_res.text


def test_the_same_number_written_four_ways_all_sign_in(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/users",
        json={"name": "Mobile Sales 2", "mobile": "098765-43211", "role": "sales", "password": "TestPass!1"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    for form in ("9876543211", "98765 43211", "919876543211", "+919876543211"):
        assert _login(client, form).status_code == 200, form


def test_create_a_user_with_both_email_and_mobile_signs_in_with_either(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/users",
        json={
            "name": "Both Ways", "email": "both@test.local", "mobile": "9876543212",
            "role": "sales", "password": "TestPass!1",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert _login(client, "both@test.local").status_code == 200
    assert _login(client, "+919876543212").status_code == 200


def test_creating_a_user_with_neither_email_nor_mobile_is_refused(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/users", json={"name": "Nobody", "role": "sales", "password": "TestPass!1"}, headers=headers
    )
    assert res.status_code == 400
    assert "email" in res.json()["detail"].lower()


def test_creating_a_user_with_a_malformed_mobile_number_is_refused(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/users",
        json={"name": "Bad Number", "mobile": "12345", "role": "sales", "password": "TestPass!1"},
        headers=headers,
    )
    assert res.status_code == 400


def test_a_mobile_number_cannot_be_used_twice(client, director_user):
    headers = _director_headers(client, director_user)
    first = client.post(
        "/users",
        json={"name": "First", "mobile": "9876543213", "role": "sales", "password": "TestPass!1"},
        headers=headers,
    )
    assert first.status_code == 201, first.text
    second = client.post(
        "/users",
        # a different way of writing the exact same number
        json={"name": "Second", "mobile": "+91 98765 43213", "role": "sales", "password": "TestPass!1"},
        headers=headers,
    )
    assert second.status_code == 409
    assert "mobile" in second.json()["detail"].lower()


def test_a_mobile_only_password_cannot_equal_the_mobile_number(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/users",
        json={"name": "Bad Password", "mobile": "9876543214", "role": "sales", "password": "+919876543214"},
        headers=headers,
    )
    assert res.status_code == 400


def test_an_unrecognised_username_gives_the_same_message_as_a_wrong_password(client, director_user):
    by_bad_mobile = _login(client, "12345")
    by_unknown_email = _login(client, "nobody@test.local")
    assert by_bad_mobile.status_code == by_unknown_email.status_code == 401
    assert by_bad_mobile.json()["detail"] == by_unknown_email.json()["detail"]


# ---------------------------------------------------------------------------
# A mobile-only account still goes through the forced-password-change flow
# ---------------------------------------------------------------------------


def test_a_mobile_only_account_changes_its_password_and_keeps_working_on_the_fresh_token(client, director_user):
    headers = _director_headers(client, director_user)
    client.post(
        "/users",
        json={"name": "New Mobile Sales", "mobile": "9876543215", "role": "sales", "password": "TempPass!1"},
        headers=headers,
    )
    login_res = _login(client, "+919876543215", password="TempPass!1")
    assert login_res.status_code == 200
    temp_headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # blocked until the password is changed
    assert client.get("/users", headers=temp_headers).status_code == 403

    change_res = client.post(
        "/auth/change-password",
        json={"current_password": "TempPass!1", "new_password": "FreshPass!1"},
        headers=temp_headers,
    )
    assert change_res.status_code == 200, change_res.text
    fresh_token = change_res.json()["access_token"]
    fresh_headers = {"Authorization": f"Bearer {fresh_token}"}

    me = client.get("/auth/me", headers=fresh_headers)
    assert me.status_code == 200
    assert me.json()["must_change_password"] is False
    assert me.json()["mobile"] == "+919876543215"


# ---------------------------------------------------------------------------
# Wrong passwords by mobile count toward the same lockout as by email
# ---------------------------------------------------------------------------


def test_five_wrong_passwords_by_mobile_lock_the_account_and_the_email_path_too(client, db_session):
    user = User(
        name="Both Locked",
        email="lockable@test.local",
        mobile="+919876543216",
        hashed_password=hash_password("TestPass!1"),
        role=UserRole.SALES,
    )
    db_session.add(user)
    db_session.commit()

    for _ in range(5):
        assert _login(client, "+919876543216", password="wrong").status_code == 401

    # locked now, even against the correct password, by either identifier
    assert _login(client, "+919876543216", password="TestPass!1").status_code == 401
    assert _login(client, "lockable@test.local", password="TestPass!1").status_code == 401


def test_an_unknown_mobile_number_locks_nothing(client, director_user):
    for _ in range(10):
        assert _login(client, "9876500000", password="wrong").status_code == 401
    # still fine -- no account was ever found to lock
    assert _login(client, "director@test.local").status_code == 200


# ---------------------------------------------------------------------------
# Editing identifiers (PATCH /users/{id})
# ---------------------------------------------------------------------------


def test_director_can_add_a_mobile_number_to_an_email_only_user(client, director_user):
    headers = _director_headers(client, director_user)
    created = client.post(
        "/users",
        json={"name": "Add Mobile", "email": "add-mobile@test.local", "role": "sales", "password": "TestPass!1"},
        headers=headers,
    ).json()
    res = client.patch(f"/users/{created['id']}", json={"mobile": "9876543217"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["mobile"] == "+919876543217"
    assert res.json()["email"] == "add-mobile@test.local"
    assert _login(client, "+919876543217").status_code == 200


def test_director_can_clear_a_users_email_if_they_have_a_mobile_number(client, director_user):
    headers = _director_headers(client, director_user)
    created = client.post(
        "/users",
        json={
            "name": "Clearable", "email": "clearable@test.local", "mobile": "9876543218",
            "role": "sales", "password": "TestPass!1",
        },
        headers=headers,
    ).json()
    res = client.patch(f"/users/{created['id']}", json={"email": ""}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["email"] is None
    assert res.json()["mobile"] == "+919876543218"


def test_clearing_both_identifiers_at_once_is_refused(client, director_user):
    headers = _director_headers(client, director_user)
    created = client.post(
        "/users",
        json={"name": "Only Email", "email": "only-email@test.local", "role": "sales", "password": "TestPass!1"},
        headers=headers,
    ).json()
    res = client.patch(f"/users/{created['id']}", json={"email": ""}, headers=headers)
    assert res.status_code == 400
    assert "email" in res.json()["detail"].lower()


def test_leaving_role_and_is_active_alone_while_editing_an_identifier(client, director_user):
    headers = _director_headers(client, director_user)
    created = client.post(
        "/users",
        json={"name": "Untouched Role", "email": "untouched@test.local", "role": "sales", "password": "TestPass!1"},
        headers=headers,
    ).json()
    res = client.patch(f"/users/{created['id']}", json={"mobile": "9876543219"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["role"] == "sales"
    assert res.json()["is_active"] is True


# ---------------------------------------------------------------------------
# Every existing (email-only) account keeps working exactly as before
# ---------------------------------------------------------------------------


def test_an_existing_email_only_account_still_signs_in_normally(client, director_user):
    assert _login(client, "director@test.local").status_code == 200


def test_list_users_still_works_and_includes_mobile_field(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.get("/users", headers=headers)
    assert res.status_code == 200
    row = next(u for u in res.json() if u["email"] == "director@test.local")
    assert row["mobile"] is None


# ---------------------------------------------------------------------------
# A61 mobile-normalization corrections: the one shared normalizer, seen from create, edit and sign-in
# ---------------------------------------------------------------------------

MALFORMED_MOBILES = ["+915123456789", "+91987654321", "+91 98765 432101", "abc9876543210xyz", "+91 98765 43210 ext"]
APPROVED_FORMS = ["98765 43210", "098765-43210", "+91 98765 43210", "91 9876543210"]


def _mobile_user(db_session, mobile="+919876543210", email=None):
    user = User(
        name="A61 Mobile", email=email, mobile=mobile, hashed_password=hash_password("TestPass!1"), role=UserRole.SALES
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.mark.parametrize("bad", MALFORMED_MOBILES)
def test_create_refuses_a_malformed_mobile_with_the_existing_validation_response(client, director_user, db_session, bad):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/users", json={"name": "Bad Mobile", "mobile": bad, "role": "sales", "password": "TestPass!1"}, headers=headers
    )
    assert res.status_code == 400, res.text
    assert isinstance(res.json()["detail"], str) and res.json()["detail"]
    assert db_session.query(User).filter(User.name == "Bad Mobile").count() == 0


@pytest.mark.parametrize("bad", MALFORMED_MOBILES)
def test_edit_refuses_a_malformed_mobile_and_leaves_the_account_unchanged(client, director_user, db_session, bad):
    headers = _director_headers(client, director_user)
    created = client.post(
        "/users",
        json={"name": "Edit Target", "email": "edit-target-a61@test.local", "mobile": "9876543299", "role": "sales", "password": "TestPass!1"},
        headers=headers,
    ).json()
    res = client.patch(f"/users/{created['id']}", json={"mobile": bad}, headers=headers)
    assert res.status_code == 400, res.text
    assert db_session.get(User, uuid.UUID(created["id"])).mobile == "+919876543299"


@pytest.mark.parametrize("bad", MALFORMED_MOBILES)
def test_sign_in_with_a_malformed_number_gives_the_generic_failure_even_with_the_right_password(client, db_session, bad):
    _mobile_user(db_session)
    res = _login(client, bad)  # the correct password for the account whose number the bad input resembles
    unknown = _login(client, "nobody@test.local")
    assert res.status_code == unknown.status_code == 401
    assert res.json()["detail"] == unknown.json()["detail"]


def test_malformed_look_alikes_cannot_be_used_to_lock_a_real_account(client, db_session):
    """Before the fix 'abc9876543210xyz' was erased to the real number, so wrong passwords typed that way counted toward the
    real account's lockout. A value that identifies nobody must lock nothing."""
    _mobile_user(db_session)
    for bad in ("abc9876543210xyz", "+91 98765 43210 ext"):
        for _ in range(6):
            assert _login(client, bad, password="wrong").status_code == 401
    assert _login(client, "+919876543210").status_code == 200  # not locked


@pytest.mark.parametrize("form", APPROVED_FORMS)
def test_the_approved_forms_identify_the_same_account(client, db_session, form):
    user = _mobile_user(db_session)
    res = _login(client, form)
    assert res.status_code == 200, (form, res.text)
    assert decode_access_token(res.json()["access_token"])["sub"] == str(user.id)


def test_wrong_passwords_by_an_approved_form_still_count_toward_the_same_lockout(client, db_session):
    _mobile_user(db_session)
    for _ in range(5):
        assert _login(client, "098765-43210", password="wrong").status_code == 401
    assert _login(client, "+919876543210").status_code == 401  # locked, whichever form is typed


# ---------------------------------------------------------------------------
# Compatibility through the callers: benign formatting and a previously accepted Unicode identifier
# ---------------------------------------------------------------------------

BENIGN_FORMS = ["98765.43210", "(98765) 43210", "98765 43210", "98765‑43210", "+91 (98765) 43210"]
UNICODE_STORED = "+91९876543210"  # accepted before the corrections (+91 then a Devanagari 9), stored as written


@pytest.mark.parametrize("form", BENIGN_FORMS)
def test_create_accepts_benign_formatting_and_stores_the_canonical_number(client, director_user, db_session, form):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/users", json={"name": "Benign Create", "mobile": form, "role": "sales", "password": "TestPass!1"}, headers=headers
    )
    assert res.status_code == 201, (form, res.text)
    assert res.json()["mobile"] == "+919876543210"
    assert _login(client, "98765 43210").status_code == 200


@pytest.mark.parametrize("form", BENIGN_FORMS)
def test_edit_accepts_benign_formatting_and_stores_the_canonical_number(client, director_user, db_session, form):
    headers = _director_headers(client, director_user)
    created = client.post(
        "/users", json={"name": "Benign Edit", "email": "benign-edit@test.local", "role": "sales", "password": "TestPass!1"},
        headers=headers,
    ).json()
    res = client.patch(f"/users/{created['id']}", json={"mobile": form}, headers=headers)
    assert res.status_code == 200, (form, res.text)
    assert res.json()["mobile"] == "+919876543210"


@pytest.mark.parametrize("form", BENIGN_FORMS)
def test_sign_in_by_a_benign_form_identifies_the_same_account(client, db_session, form):
    user = _mobile_user(db_session)
    res = _login(client, form)
    assert res.status_code == 200, (form, res.text)
    assert decode_access_token(res.json()["access_token"])["sub"] == str(user.id)


def test_wrong_passwords_by_a_benign_form_count_toward_the_same_lockout(client, db_session):
    _mobile_user(db_session)
    for _ in range(5):
        assert _login(client, "(98765) 43210", password="wrong").status_code == 401
    assert _login(client, "+919876543210").status_code == 401  # locked, whichever form is typed


def test_a_previously_accepted_unicode_identifier_still_signs_in_by_the_same_text(client, db_session):
    """A fixture account stored as '+91' + a Devanagari 9 + 876543210 (the normalizer used to accept and store it). Whether
    production holds any such account is NOT assumed. The correction must not turn that identifier into a refusal."""
    user = _mobile_user(db_session, mobile=UNICODE_STORED)
    res = _login(client, UNICODE_STORED)
    assert res.status_code == 200, res.text
    assert decode_access_token(res.json()["access_token"])["sub"] == str(user.id)
    assert _login(client, "+91 ९876543210").status_code == 200   # same number, formatted


def test_wrong_passwords_by_a_stored_unicode_identifier_lock_it_like_any_account(client, db_session):
    """The lock is proved through the account's EMAIL, so a refused identifier (which identifies nobody and locks nothing)
    cannot make this pass by accident."""
    _mobile_user(db_session, mobile=UNICODE_STORED, email="unicode-lock@test.local")
    for _ in range(5):
        assert _login(client, UNICODE_STORED, password="wrong").status_code == 401
    assert _login(client, "unicode-lock@test.local").status_code == 401  # locked, so the right password by email fails too


def test_creating_the_same_unicode_identifier_twice_is_a_conflict(client, director_user, db_session):
    _mobile_user(db_session, mobile=UNICODE_STORED)
    headers = _director_headers(client, director_user)
    res = client.post(
        "/users", json={"name": "Dup Unicode", "mobile": UNICODE_STORED, "role": "sales", "password": "TestPass!1"}, headers=headers
    )
    assert res.status_code == 409, res.text


# ---------------------------------------------------------------------------
# Approved Unicode policy through the callers: malformed Unicode-containing Indian numbers are refused, valid ones keep
# their spelling, refused identifiers give the generic failure and lock nothing
# ---------------------------------------------------------------------------

UNICODE_MALFORMED = ["+91512345678९", "+9198765432९", "+919876543210९", "+９１5123456789", "+९१5123456789"]


@pytest.mark.parametrize("bad", UNICODE_MALFORMED)
def test_create_refuses_a_malformed_unicode_containing_indian_number_with_the_existing_validation_response(
    client, director_user, db_session, bad
):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/users", json={"name": "Bad Unicode", "mobile": bad, "role": "sales", "password": "TestPass!1"}, headers=headers
    )
    assert res.status_code == 400, res.text
    assert "Indian mobile" in res.json()["detail"]
    assert db_session.query(User).filter(User.name == "Bad Unicode").count() == 0


@pytest.mark.parametrize("bad", UNICODE_MALFORMED)
def test_edit_refuses_a_malformed_unicode_containing_indian_number_and_leaves_the_account_unchanged(
    client, director_user, db_session, bad
):
    headers = _director_headers(client, director_user)
    created = client.post(
        "/users",
        json={"name": "Edit Unicode", "email": "edit-unicode@test.local", "mobile": "9876543277", "role": "sales", "password": "TestPass!1"},
        headers=headers,
    ).json()
    res = client.patch(f"/users/{created['id']}", json={"mobile": bad}, headers=headers)
    assert res.status_code == 400, res.text
    assert db_session.get(User, uuid.UUID(created["id"])).mobile == "+919876543277"


def test_create_accepts_a_valid_unicode_spelled_number_and_stores_its_existing_spelling(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/users", json={"name": "Valid Unicode", "mobile": "+91 ९876543210", "role": "sales", "password": "TestPass!1"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["mobile"] == UNICODE_STORED
    assert _login(client, UNICODE_STORED).status_code == 200


@pytest.mark.parametrize("bad", UNICODE_MALFORMED)
def test_sign_in_with_a_malformed_unicode_containing_number_gives_the_generic_failure(client, db_session, bad):
    _mobile_user(db_session)
    res = _login(client, bad)
    unknown = _login(client, "nobody@test.local")
    assert res.status_code == unknown.status_code == 401
    assert res.json()["detail"] == unknown.json()["detail"]


def test_malformed_unicode_look_alikes_lock_nothing(client, db_session):
    _mobile_user(db_session)
    for bad in UNICODE_MALFORMED:
        for _ in range(2):
            assert _login(client, bad, password="wrong").status_code == 401
    assert _login(client, "+919876543210").status_code == 200  # the real account was never counted against
