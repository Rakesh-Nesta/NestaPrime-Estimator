"""One-off dev script: creates a single Procurement test user, mirroring
seed_test_user.py, so the K.3 Procurement export role gate (Blueprint
Ledger gap #7) can be exercised end-to-end against a real dev session."""

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole

db = SessionLocal()
try:
    existing = db.query(User).filter(User.email == "procurement@nestaprime.local").first()
    if existing:
        print("Procurement test user already exists.")
    else:
        user = User(
            name="Test Procurement",
            email="procurement@nestaprime.local",
            hashed_password=hash_password("ChangeMe!1"),
            role=UserRole.PROCUREMENT,
        )
        db.add(user)
        db.commit()
        print("Created procurement@nestaprime.local / ChangeMe!1")
finally:
    db.close()
