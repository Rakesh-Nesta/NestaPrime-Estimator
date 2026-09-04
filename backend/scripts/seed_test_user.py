"""One-off dev script: creates a single Director test user so the auth flow
can be exercised end-to-end before a real Users admin screen exists."""

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole

db = SessionLocal()
try:
    existing = db.query(User).filter(User.email == "director@nestaprime.local").first()
    if existing:
        print("Test user already exists.")
    else:
        user = User(
            name="Test Director",
            email="director@nestaprime.local",
            hashed_password=hash_password("ChangeMe!1"),
            role=UserRole.DIRECTOR,
        )
        db.add(user)
        db.commit()
        print("Created director@nestaprime.local / ChangeMe!1")
finally:
    db.close()
