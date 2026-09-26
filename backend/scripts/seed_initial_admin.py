"""One-time bootstrap (Amendment 59, Section 62): creates the first Admin account.

An Admin runs the system -- people, access, company identity -- so the Director does not have to. Only an Admin
creates another Admin, so the very first one has to come from outside the app. Run this once, on the server:

    docker compose -f docker-compose.prod.yml exec -T \\
      -e PYTHONPATH=/app -e INITIAL_ADMIN_EMAIL=admin@example.com -e INITIAL_ADMIN_PASSWORD='a long temporary password' \\
      backend python scripts/seed_initial_admin.py

It refuses to run if an active Admin already exists (from then on an Admin creates Admins), refuses a password
under 10 characters or equal to the email, reads the details from the environment rather than hardcoding them, and
sets must_change_password so the real person picks their own password at first sign-in -- the same guarantee every
account created through the app gets."""

import os
import sys

from app.core.security import MIN_PASSWORD_LENGTH, hash_password, password_problem
from app.db.session import SessionLocal
from app.models.user import User, UserRole

email = os.environ.get("INITIAL_ADMIN_EMAIL")
password = os.environ.get("INITIAL_ADMIN_PASSWORD")
name = os.environ.get("INITIAL_ADMIN_NAME", "Admin")

if not email or not password:
    print("Set INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD before running this.", file=sys.stderr)
    sys.exit(1)
if len(password) < MIN_PASSWORD_LENGTH:
    print(f"The password needs at least {MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
    sys.exit(1)
problem = password_problem(password, email)
if problem:
    print(problem, file=sys.stderr)
    sys.exit(1)

db = SessionLocal()
try:
    if db.query(User).filter(User.role == UserRole.ADMIN, User.is_active.is_(True)).first():
        print("An active Admin already exists -- not creating another. An Admin creates Admins from the app.")
    elif db.query(User).filter(User.email == email).first():
        print(f"{email} already exists as a different account -- not creating a duplicate.", file=sys.stderr)
        sys.exit(1)
    else:
        db.add(
            User(
                name=name,
                email=email,
                hashed_password=hash_password(password),
                role=UserRole.ADMIN,
                must_change_password=True,
            )
        )
        db.commit()
        print(f"Created the first Admin, {email} -- must change password on first login.")
finally:
    db.close()
