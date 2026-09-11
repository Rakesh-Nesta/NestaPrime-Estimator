"""Production bootstrap: creates exactly one initial Director account so
someone can log in and use the real User Management screen (Master
Settings > User management) to create every other account from there --
unlike seed_test_user.py (a dev-only stand-in predating that screen),
this is meant to run once against a real database.

Reads INITIAL_DIRECTOR_EMAIL / INITIAL_DIRECTOR_PASSWORD from the
environment rather than hardcoding them, and sets must_change_password
so the real owner is forced to pick their own password on first login --
the same guarantee every other account created through the app gets."""

import os
import sys

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole

email = os.environ.get("INITIAL_DIRECTOR_EMAIL")
password = os.environ.get("INITIAL_DIRECTOR_PASSWORD")

if not email or not password:
    print("Set INITIAL_DIRECTOR_EMAIL and INITIAL_DIRECTOR_PASSWORD before running this.", file=sys.stderr)
    sys.exit(1)

db = SessionLocal()
try:
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        print(f"{email} already exists -- not creating a duplicate.")
    else:
        user = User(
            name="Director",
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.DIRECTOR,
            must_change_password=True,
        )
        db.add(user)
        db.commit()
        print(f"Created {email} -- must change password on first login.")
finally:
    db.close()
