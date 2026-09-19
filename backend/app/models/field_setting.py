import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FieldSettingState(str, enum.Enum):
    COMPULSORY = "compulsory"
    OPTIONAL = "optional"
    HIDDEN = "hidden"


class FieldSetting(Base):
    """Amendment 5 Phase 2 (Section 6, extended by Section 22): "admin sets
    each field compulsory/optional/hidden from Master Settings." Scoped to
    New Project Setup's own B.1 fields that Amendment 2 already made a
    one-time hardcoded call about (soil type, distance, court count, site
    access, power, water) -- see Section-6-phase2-specs.md and
    Section-22-specs.md for the field list and why building_status/
    site_condition stay deliberately excluded (building_status is
    nullable=False at the DB level and D.4 logic branches directly on it;
    site_condition was never named as a T&C candidate by Amendment 2).
    water_available joined the governed set in Section 22 -- originally
    excluded only because a plain boolean checkbox had no dropdown to put
    a real "None" on, now rendered as a Select like every other governed
    field here.

    One row per governed field_key; a field with no row here defaults to
    COMPULSORY (today's actual behavior, unchanged until a Director
    deliberately opts it down) -- see get_field_state in app/api/
    field_settings.py."""

    __tablename__ = "field_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    field_key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    state: Mapped[FieldSettingState] = mapped_column(
        Enum(FieldSettingState, name="field_setting_state"), default=FieldSettingState.COMPULSORY, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False
    )
