from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise credentials_error

    user = db.query(User).filter(User.email == payload["sub"]).first()
    if user is None or not user.is_active:
        raise credentials_error
    return user


def require_roles(*allowed_roles: str):
    """Server-side role gate — the same principle as K.3: role checks happen
    at the API, not the browser, so a field can never leak to a role that
    shouldn't see it just because the UI didn't render it.

    Also enforces User.must_change_password here, for the same reason:
    every protected endpoint in this app goes through require_roles, so
    checking it once here blocks a Director-issued temporary password
    from being used for anything else, server-side, not just withheld
    by the frontend. GET /auth/me and POST /auth/change-password
    deliberately don't use require_roles (they depend on get_current_user
    directly) specifically so they stay reachable while this flag is
    set — otherwise the very endpoint that clears it would itself be
    blocked."""

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.must_change_password:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Password change required before continuing -- use POST /auth/change-password",
            )
        if current_user.role.value not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role.value}' is not permitted to perform this action",
            )
        return current_user

    return dependency
