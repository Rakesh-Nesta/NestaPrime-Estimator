import hashlib
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# Argon2 per the blueprint's security baseline (Part P.1) — not bcrypt.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

ALGORITHM = "HS256"

# Amendment 58 (Section 61) item 7: wherever a password is set.
MIN_PASSWORD_LENGTH = 10


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def password_fingerprint(hashed_password: str) -> str:
    """Amendment 58 (Section 61) item 5: a short fingerprint of the stored password hash. It rides in
    the sign-in token ("pwv"); get_current_user refuses a token whose fingerprint no longer matches,
    so changing or resetting a password ends every session that was opened with the old one. It is
    derived from the hash, never the password, and reveals nothing usable."""
    return hashlib.sha256(hashed_password.encode("utf-8")).hexdigest()[:16]


def password_problem(
    new_password: str, email: str | None, mobile: str | None = None, current_hash: str | None = None
) -> str | None:
    """Amendment 58 item 7: beyond the minimum length, a new password may not be the person's email
    address, mobile number (Amendment 61 -- a mobile-only account has no email to check against), or the
    password they have now. Returns a plain sentence, or None when it is acceptable."""
    if email and new_password.strip().lower() == email.strip().lower():
        return "The password can't be the same as the email address"
    if mobile and new_password.strip() == mobile.strip():
        return "The password can't be the same as the mobile number"
    if current_hash and verify_password(new_password, current_hash):
        return "The new password must be different from the current one"
    return None


def create_access_token(subject: str, role: str, password_hash: str) -> str:
    # Amendment 61 (Section 64) item 4: `subject` is the user's id (a string), not their email --
    # an account may have no email at all now. Every token issued before this names an email instead;
    # get_current_user (core/auth.py) and enforce_own_records (core/ownership.py) only understand an id,
    # so an old token is simply invalid and its holder signs in once more, the same as after Amendment 58.
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "role": role, "exp": expire, "pwv": password_fingerprint(password_hash)}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None
