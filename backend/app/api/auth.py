from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.core.auth import get_current_user
from app.core.identifiers import InvalidMobileNumber, normalize_mobile
from app.core.security import (
    MIN_PASSWORD_LENGTH,
    SigningKeyUnavailable,
    create_access_token,
    hash_password,
    password_problem,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

LOGIN_ATTEMPT_THRESHOLD = 5
LOGIN_LOCKOUT_DURATION = timedelta(minutes=15)


def _incorrect_credentials() -> HTTPException:
    # Amendment 18 (Section 24): the same generic 401 covers every
    # failure case (unknown email, wrong password, locked account) --
    # never a different message that would let an attacker distinguish
    # "wrong password" from "this account is locked," which would
    # itself leak which emails are real accounts.
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")


class UserOut(BaseModel):
    id: str
    name: str
    email: str | None
    mobile: str | None
    role: str
    # User Management (users.py): true for any account just created or
    # password-reset by a Director. require_roles (core/auth.py) blocks
    # every other protected endpoint while this is true; the frontend
    # uses this field (from GET /auth/me, which stays reachable) to show
    # a mandatory change-password form before the block is ever hit in
    # normal use.
    must_change_password: bool

    model_config = ConfigDict(from_attributes=True)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenOut)
def login(
    request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    # Amendment 61 (Section 64) item 3: the one field takes either -- an email (it contains "@") or a
    # mobile number (it does not). A value that cannot even be parsed as a number is unrecognised, exactly
    # like an unknown email: same message, no lockout, since no real account was ever found.
    identifier = form_data.username.strip()
    if "@" in identifier:
        user = db.query(User).filter(User.email == identifier).first()
    else:
        try:
            mobile = normalize_mobile(identifier)
        except InvalidMobileNumber:
            mobile = None
        user = db.query(User).filter(User.mobile == mobile).first() if mobile else None
    # Amendment 18: an unknown identifier never counts toward any account's
    # lockout -- counting it would let an attacker lock out an arbitrary
    # real account just by guessing emails/numbers, a denial-of-service angle a
    # real-account-only counter avoids.
    if user is None:
        raise _incorrect_credentials()

    # locked_until is a plain (timezone-naive) DateTime column, like
    # every other timestamp column in this codebase -- compare against a
    # naive UTC "now" rather than datetime.now(UTC) directly, which
    # would raise TypeError against a value just loaded back from the DB.
    now = datetime.now(UTC).replace(tzinfo=None)
    if user.locked_until is not None and user.locked_until > now:
        # Locked accounts stay locked for the full window, even against
        # the correct password -- that's the whole point of a lockout.
        raise _incorrect_credentials()

    if not user.is_active or not verify_password(form_data.password, user.hashed_password):
        if user.is_active:
            # is_active=False accounts (deactivated, not a password
            # failure) don't consume lockout attempts -- there's nothing
            # a lockout protects here that deactivation doesn't already.
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= LOGIN_ATTEMPT_THRESHOLD:
                user.locked_until = now + LOGIN_LOCKOUT_DURATION
                user.failed_login_attempts = 0
                # Amendment 58 (Section 61) item 6: a lockout is worth a record; individual wrong
                # passwords are not written (a guessing run must not be able to fill the table).
                write_audit_log_entry(
                    db, user, "user", user.id, "account_lock",
                    old_value=None,
                    new_value=f"locked for {int(LOGIN_LOCKOUT_DURATION.total_seconds() // 60)} minutes "
                    f"after {LOGIN_ATTEMPT_THRESHOLD} wrong passwords",
                    request=request,
                )
            db.commit()
        raise _incorrect_credentials()

    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()

    token = create_access_token(subject=str(user.id), role=user.role.value, password_hash=user.hashed_password)
    return TokenOut(access_token=token)


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return UserOut(
        id=str(current_user.id),
        name=current_user.name,
        email=current_user.email,
        mobile=current_user.mobile,
        role=current_user.role.value,
        must_change_password=current_user.must_change_password,
    )


PASSWORD_CHANGE_UNCONFIRMED_DETAIL = (
    "The password change could not be confirmed. Try signing in with your new password first, then your current password."
)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH)


class ChangePasswordOut(UserOut):
    # Amendment 58 (Section 61) item 5: changing the password ends the sessions opened with the old one,
    # including this one, so the caller is handed a fresh token and carries on without signing in again.
    access_token: str


@router.post("/change-password", response_model=ChangePasswordOut)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Self-service -- requires the current password even though the
    caller is already authenticated by a valid JWT, so a leaked/stolen
    token alone can't lock the real owner out by changing it. Clears
    must_change_password, which is the only real effect of this
    endpoint beyond the password itself."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    problem = password_problem(
        payload.new_password, current_user.email, current_user.mobile, current_user.hashed_password
    )
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    new_hash = hash_password(payload.new_password)
    current_user.hashed_password = new_hash
    current_user.must_change_password = False
    # Amendment 58 item 6: that a change happened, never the password itself.
    write_audit_log_entry(
        db, current_user, "user", current_user.id, "password",
        old_value="(self-service change)", new_value="(self-service change)", request=request,
    )
    # JWT migration (decision D4): the re-issued token is signed from the NEW fingerprint BEFORE the commit, so a signing failure aborts the
    # whole change (the staged password, flag and audit entry are explicitly rolled back) instead of leaving a changed password and no
    # token. The token is only released after the commit succeeds.
    try:
        reissued = ChangePasswordOut(
            id=str(current_user.id),
            name=current_user.name,
            email=current_user.email,
            mobile=current_user.mobile,
            role=current_user.role.value,
            must_change_password=False,
            access_token=create_access_token(
                subject=str(current_user.id), role=current_user.role.value, password_hash=new_hash
            ),
        )
    except SigningKeyUnavailable:
        # Attempt the rollback, but never let a failing rollback replace the sanitized signing-failure response: whatever it raises is
        # discarded. Nothing was committed either way, and no claim is made that the rollback succeeded.
        try:
            db.rollback()
        except Exception:
            pass
        raise  # the shared handler answers 503; nothing was committed and the old session still works
    try:
        db.commit()
    except Exception:
        # Any reported commit failure: try to clean the session up, release NO token, and say only that the change could not be confirmed.
        # The database may already have committed before the error reached us, so a rollback is never claimed to have undone anything.
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=503, detail=PASSWORD_CHANGE_UNCONFIRMED_DETAIL) from None
    return reissued
