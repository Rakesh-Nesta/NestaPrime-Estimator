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
    """Amendment 5 Phase 2 (Section 6): "admin sets each field compulsory/
    optional/hidden from Master Settings." Scoped this wave to New Project
    Setup's own B.1 fields that Amendment 2 already made a one-time
    hardcoded call about (soil type, distance, court count, site access,
    power) -- see Section-6-phase2-specs.md for the field list and why
    building_status/water_available/site_condition are deliberately left
    out (building_status is one of Amendment 2's own "kept 5" required
    fields; water_available is boolean and doesn't fit the None-option
    model; site_condition was never named as a T&C candidate by Amendment
    2 either).

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
