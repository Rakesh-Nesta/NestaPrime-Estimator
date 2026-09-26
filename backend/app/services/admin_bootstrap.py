"""Amendment 59 (Section 62): creating the very first Admin, safely.

An Admin can create every other account, so the first one is the most valuable account in the system -- and it
has to be created from outside the app (only an Admin creates an Admin). The first attempt at this, on 26 September
2026, was run with the placeholder words from the instructions instead of real values and created an Admin called
THEIR-EMAIL whose password was written in the chat. It was deleted within minutes, but the script should have
refused. So:

- the email must look like an email address (not a placeholder word) and not use an obvious placeholder domain;
- the password is **generated here and shown once** unless one is deliberately supplied, so there is no password to
  copy from anywhere and none written in a message;
- an explicit password still has to meet the normal rules (10 characters, not the email);
- it refuses when an active Admin already exists, and never creates a duplicate email."""

import re
import secrets

from sqlalchemy.orm import Session

from app.core.security import MIN_PASSWORD_LENGTH, hash_password, password_problem
from app.models.user import User, UserRole

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
# The domains instructions and examples use. An account on one of them is a copy-and-paste mistake, not a person.
_PLACEHOLDER_DOMAINS = {
    "example.com", "example.org", "example.net", "example.invalid", "yourcompany.com", "yourdomain.com",
    "company.com", "domain.com", "test.com", "email.com",
}


class BootstrapError(Exception):
    """A plain-language reason the first Admin was not created."""


def create_first_admin(
    db: Session, email: str, password: str | None = None, name: str = "Admin"
) -> tuple[User, str | None]:
    """Create the first Admin and commit. Returns (user, generated_password) -- the second item is the temporary
    password to hand to the person (shown once, never stored in the clear), or None when one was supplied."""
    email = (email or "").strip()
    if not _EMAIL.match(email):
        raise BootstrapError(
            f"'{email}' does not look like an email address. Use the real address of the person who will be the Admin."
        )
    if email.rsplit("@", 1)[1].lower() in _PLACEHOLDER_DOMAINS:
        raise BootstrapError(
            f"'{email}' looks like a placeholder from the instructions, not a real person. Use their real address."
        )
    if db.query(User).filter(User.role == UserRole.ADMIN, User.is_active.is_(True)).first():
        raise BootstrapError("An active Admin already exists. An Admin creates other Admins from the app.")
    if db.query(User).filter(User.email == email).first():
        raise BootstrapError(f"{email} already exists as a different account -- not creating a duplicate.")

    generated = None
    if password is None or password == "":
        generated = password = secrets.token_urlsafe(15)
    else:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise BootstrapError(f"The password needs at least {MIN_PASSWORD_LENGTH} characters.")
        problem = password_problem(password, email)
        if problem:
            raise BootstrapError(problem)

    user = User(
        name=name,
        email=email,
        hashed_password=hash_password(password),
        role=UserRole.ADMIN,
        must_change_password=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, generated
