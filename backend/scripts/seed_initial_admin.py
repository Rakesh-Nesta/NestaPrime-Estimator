"""One-time bootstrap (Amendment 59, Section 62): creates the first Admin account.

An Admin runs the system -- people, access, company identity -- so the Director does not have to. Only an Admin
creates another Admin, so the very first one has to come from outside the app. Run this once, on the server, with
the REAL email address of the person who will be the Admin:

    docker compose -f docker-compose.prod.yml exec -T \\
      -e PYTHONPATH=/app -e INITIAL_ADMIN_EMAIL=the-real-address@theircompany.in \\
      backend python scripts/seed_initial_admin.py

The temporary password is generated and printed once, on your terminal only -- give it to the person privately; they
must change it at first sign-in. (INITIAL_ADMIN_PASSWORD can be set to choose one instead; it must be at least 10
characters.) It refuses anything that does not look like a real email address, refuses obvious placeholder domains,
and refuses if an active Admin already exists.

The rules live in app/services/admin_bootstrap.py, where they are tested."""

import os
import sys

from app.db.session import SessionLocal
from app.services.admin_bootstrap import BootstrapError, create_first_admin

email = os.environ.get("INITIAL_ADMIN_EMAIL")
if not email:
    print("Set INITIAL_ADMIN_EMAIL to the real email address of the person who will be the Admin.", file=sys.stderr)
    sys.exit(1)

db = SessionLocal()
try:
    user, generated = create_first_admin(
        db,
        email,
        password=os.environ.get("INITIAL_ADMIN_PASSWORD"),
        name=os.environ.get("INITIAL_ADMIN_NAME", "Admin"),
    )
    print(f"Created the first Admin, {user.email} -- must change password on first login.")
    if generated:
        print(f"Temporary password (shown once, give it to them privately): {generated}")
except BootstrapError as error:
    print(str(error), file=sys.stderr)
    sys.exit(1)
finally:
    db.close()
