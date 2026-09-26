import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserRole(str, enum.Enum):
    """The six roles fixed in the blueprint (Part O USERS / ROLES, M.4), plus ADMIN (Amendment 59, Section 62):
    the person who runs the system -- people, access, technical settings -- without approving, pricing or seeing
    cost and margin. Not one of the blueprint's six; added at the Director's instruction."""

    SALES = "sales"
    PM = "pm"
    DIRECTOR = "director"
    PROCUREMENT = "procurement"
    SITE_ENGINEER = "site_engineer"
    CA_TAX = "ca_tax"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Defaults False -- set True explicitly only by the two places that
    # hand someone a Director-chosen password they didn't pick themselves
    # (users.py's create_user and reset_password). Every other User(...)
    # construction anywhere else in the codebase (the many existing
    # tests that build a user directly and call other endpoints right
    # away included) is unaffected, since they never touch this field.
    # Enforced server-side: require_roles (core/auth.py) blocks any
    # request from a user with this flag set, except POST
    # /auth/change-password and GET /auth/me, which must stay reachable
    # so the frontend can detect the flag and let the user actually
    # clear it. This is real enforcement, not just a frontend prompt --
    # a leaked or stolen token tied to a Director-issued temporary
    # password can't be used for anything else until the real recipient
    # changes it.
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    # Amendment 18 (Section 24): login lockout. failed_login_attempts
    # resets to 0 on any successful login; once it reaches the threshold
    # (auth.py's own constant), locked_until is set and the counter
    # resets. Persisted on the User row rather than kept in worker
    # memory -- production runs 2 gunicorn workers, and in-memory state
    # wouldn't be visible to both.
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, default=None, nullable=True)
