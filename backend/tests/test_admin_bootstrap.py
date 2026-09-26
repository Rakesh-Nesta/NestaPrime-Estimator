"""Amendment 59 (Section 62): the first Admin is created safely.

Found on the day it shipped: the script was run with the placeholder words from the instructions and created an Admin
called THEIR-EMAIL with a password written in the chat. It should have refused."""

import pytest

from app.core.security import verify_password
from app.models.user import User, UserRole
from app.services.admin_bootstrap import BootstrapError, create_first_admin


@pytest.mark.parametrize(
    "email",
    ["THEIR-EMAIL", "", "   ", "nobody", "a b@c.in", "x@y", "@nowhere.in", "person@", "two@@signs.in"],
)
def test_something_that_is_not_an_email_address_is_refused(db_session, email):
    with pytest.raises(BootstrapError, match="does not look like an email"):
        create_first_admin(db_session, email)
    assert db_session.query(User).count() == 0


@pytest.mark.parametrize(
    "email",
    ["admin@example.com", "admin@yourcompany.com", "me@YourDomain.com", "a@example.invalid", "who@test.com"],
)
def test_a_placeholder_domain_is_refused(db_session, email):
    with pytest.raises(BootstrapError, match="placeholder"):
        create_first_admin(db_session, email)
    assert db_session.query(User).count() == 0


def test_with_no_password_supplied_one_is_generated_shown_once_and_works(db_session):
    user, generated = create_first_admin(db_session, "  real.person@nestaprime.in  ")
    assert user.email == "real.person@nestaprime.in"  # trimmed
    assert user.role == UserRole.ADMIN and user.must_change_password is True and user.is_active is True
    assert generated and len(generated) >= 16
    assert verify_password(generated, user.hashed_password)
    assert generated not in user.hashed_password  # only the hash is stored


def test_two_runs_generate_different_passwords(db_session):
    _, first = create_first_admin(db_session, "one@nestaprime.in")
    db_session.query(User).delete()
    db_session.commit()
    _, second = create_first_admin(db_session, "one@nestaprime.in")
    assert first != second


def test_an_explicit_password_is_used_and_returns_nothing_to_print(db_session):
    user, generated = create_first_admin(db_session, "chosen@nestaprime.in", password="A-chosen-pass-2026")
    assert generated is None and verify_password("A-chosen-pass-2026", user.hashed_password)


@pytest.mark.parametrize("password", ["short", "9chars!!!"])
def test_an_explicit_password_still_needs_ten_characters(db_session, password):
    with pytest.raises(BootstrapError, match="at least 10"):
        create_first_admin(db_session, "chosen@nestaprime.in", password=password)
    assert db_session.query(User).count() == 0


def test_an_explicit_password_may_not_be_the_email(db_session):
    with pytest.raises(BootstrapError, match="same as the email"):
        create_first_admin(db_session, "same.value@nestaprime.in", password="same.value@nestaprime.in")


def test_it_refuses_when_an_active_admin_already_exists(db_session):
    create_first_admin(db_session, "first@nestaprime.in")
    with pytest.raises(BootstrapError, match="active Admin already exists"):
        create_first_admin(db_session, "second@nestaprime.in")
    assert db_session.query(User).filter(User.role == UserRole.ADMIN).count() == 1


def test_it_will_start_again_when_the_only_admin_is_inactive(db_session):
    first, _ = create_first_admin(db_session, "first@nestaprime.in")
    first.is_active = False
    db_session.commit()
    user, _ = create_first_admin(db_session, "second@nestaprime.in")
    assert user.is_active is True


def test_it_never_creates_a_duplicate_email(db_session):
    db_session.add(User(name="Existing", email="taken@nestaprime.in", hashed_password="x", role=UserRole.PM))
    db_session.commit()
    with pytest.raises(BootstrapError, match="already exists as a different account"):
        create_first_admin(db_session, "taken@nestaprime.in")
