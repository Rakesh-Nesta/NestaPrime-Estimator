import hashlib
import logging
import threading
import warnings
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.config import settings

# Argon2 per the blueprint's security baseline (Part P.1) — not bcrypt.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

ALGORITHM = "HS256"

# Amendment 58 (Section 61) item 7: wherever a password is set.
MIN_PASSWORD_LENGTH = 10

# JWT migration (python-jose -> PyJWT[crypto]; CVE-2026-85394): the signing key must be USABLE. The `crypto` extra is REQUIRED, not
# optional: without `cryptography` PyJWT cannot recognise a public key and accepts its bytes (DER or PEM) as an HMAC secret.
MIN_SECRET_BYTES = 32
_log = logging.getLogger("app.security")

# Fixed texts: nothing in them can carry a key, a length or an exception message.
SIGNING_UNAVAILABLE_DETAIL = (
    "The service cannot verify or issue sign-in tokens because of a server configuration problem. "
    "Please contact the administrator."
)
STARTUP_FAILURE_MESSAGE = "SECRET_KEY cannot be used to sign tokens; fix the server configuration (details withheld)"
_SHORT_KEY_WARNING = "SECRET_KEY is shorter than 32 bytes; use a longer random secret"


class SigningKeyUnavailable(Exception):
    """The configured key cannot sign or verify tokens: a server CONFIGURATION fault, never a credential fault. Deliberately carries no
    message, key text, length or chained cause; one handler in app.main turns it into the fixed 503 for every caller."""


# PyJWT errors that mean "the key/configuration is unusable" (InvalidKeyError is a PyJWTError but NOT an InvalidTokenError), plus
# its short-key warning when a harness has turned warnings into errors.
_KEY_FAULTS = (jwt.PyJWTError, jwt.InsecureKeyLengthWarning)

# PyJWT warns on EVERY encode/decode while the HS256 secret is under 32 bytes. Decision D3 (migration): a usable short key only warns --
# once per process, below -- so that PyJWT message is ignored by ONE filter, installed once at import and kept for the process lifetime.
# It is limited to that category AND that wording (PyJWT names the hash, `SHA256`, for HS256), so every other warning is untouched. It is deliberately not a per-call
# `warnings.catch_warnings()`: that swaps the global filter list and is not thread-safe, and sync routes run in a threadpool.
_KEY_LENGTH_MESSAGE = r"The HMAC key is \d+ bytes long, which is below the minimum recommended length of \d+ bytes for SHA256\."
_lock = threading.Lock()


def _install_key_length_filter() -> None:
    with _lock:
        for action, message, category, _module, _lineno in warnings.filters:
            if action == "ignore" and category is jwt.InsecureKeyLengthWarning and message is not None and message.pattern == _KEY_LENGTH_MESSAGE:
                return  # idempotent: a re-import adds nothing
        warnings.filterwarnings("ignore", message=_KEY_LENGTH_MESSAGE, category=jwt.InsecureKeyLengthWarning)


_install_key_length_filter()


def _warn_short_key_once() -> None:
    with _lock:  # the check-and-set is atomic: two threads can never both see "not yet warned"
        if getattr(_log, "_short_key_warned", False):  # kept on the logger so it also survives a module reload
            return
        _log._short_key_warned = True
    _log.warning(_SHORT_KEY_WARNING)


def require_usable_signing_key() -> None:
    """Called at application import: refuse to serve with a key that cannot sign. Empty/blank keys, and public-key material that PyJWT
    refuses as an HMAC secret, are configuration failures raised with ONE fixed message (the original exception is discarded, never
    chained or formatted). A usable key under 32 bytes only warns, once per process (decision D3)."""
    key = settings.secret_key
    try:
        if not isinstance(key, str) or not key.strip():
            raise ValueError
        probe = jwt.encode({"probe": True, "exp": datetime.now(timezone.utc) + timedelta(seconds=60)}, key, algorithm=ALGORITHM)
        jwt.decode(probe, key, algorithms=[ALGORITHM])
        short = len(key.encode("utf-8")) < MIN_SECRET_BYTES
    except (*_KEY_FAULTS, ValueError, TypeError):
        raise RuntimeError(STARTUP_FAILURE_MESSAGE) from None
    if short:
        _warn_short_key_once()



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
    try:
        return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    except _KEY_FAULTS:
        raise SigningKeyUnavailable() from None


def decode_access_token(token: str) -> dict | None:
    """The payload of a genuine, unexpired token, or None for ANY token fault (malformed, bad signature, wrong algorithm, expired, ...).
    A key/configuration fault is NOT a token fault: it raises SigningKeyUnavailable, so it can never read as "incorrect credentials"
    and never lets a request through. Expiry follows PyJWT's standard boundary (rejected from the instant `exp`), with no leeway."""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        return None
    except _KEY_FAULTS:
        raise SigningKeyUnavailable() from None
