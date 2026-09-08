import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SettingScope(str, enum.Enum):
    GLOBAL = "global"
    CITY = "city"
    CLIENT_TYPE = "client_type"
    SPORT = "sport"
    PACKAGE = "package"


class DocumentType(str, enum.Enum):
    COST_SHEET = "cost_sheet"
    ESTIMATE = "estimate"
    QUOTATION = "quotation"
    # Part O: "WORK_ORDERS ... client work order attachment" -- Attachment
    # previously couldn't reference a Work Order (no backing entity
    # existed); now that app.models.work_order.WorkOrder does, this closes
    # that gap. Not used for Override/K1-constants scoping (no K.1
    # percentage lives at the work-order level), only for Attachment.
    WORK_ORDER = "work_order"
    # Part L "Documents" row: "Technical bid checklist (GST, PAN,
    # turnover, past work certificates, ISO)" -- each checklist item can
    # carry a supporting document via the same generic Attachment system.
    TECHNICAL_BID_CHECKLIST_ITEM = "technical_bid_checklist_item"
    # M.7.3: "Attachments (vendor quotation PDF/photo) are stored as
    # vendor_quote attachments with hash" -- lets a vendor's price-update
    # reply carry a supporting file via the same generic Attachment system.
    PRICE_REQUEST = "price_request"
    # Appendix C: "photos (min 4)" -- a Site Survey's own photos ride the
    # same generic Attachment system, tagged `photo`.
    SITE_SURVEY = "site_survey"
    # M.6: "product options table (Budget/Standard/Premium with images)" --
    # a product image belongs to one specific EstimateOption row (a
    # sport+package combination), not the whole Estimate, so it needs its
    # own doc_type rather than riding ESTIMATE's.
    ESTIMATE_OPTION = "estimate_option"


class Setting(Base):
    """Q.1/Q.2 — Master Settings. Covers the [confirm] values that don't
    already have a dedicated strongly-typed table elsewhere in this build
    (MarginPolicy covers target/floor margin, RegionalMultiplier covers
    city multipliers, RateItem covers material rates, LabourCategory
    covers labour %) -- things like GST rate, estimate/quotation validity
    days, the price-range %, and the schedule-estimator duration defaults,
    which were otherwise Python constants.

    Q.2 rule 1: 'every setting has an effective-from date and history...
    changing a setting never alters an existing document.' Implemented by
    versioning: editing a setting inserts a new row rather than mutating
    the old one, so a document that already read a value keeps it, and the
    full history stays queryable."""

    __tablename__ = "settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    scope: Mapped[SettingScope] = mapped_column(
        Enum(SettingScope, name="setting_scope"), default=SettingScope.GLOBAL, nullable=False
    )
    # e.g. city="Mumbai" for a CITY-scoped setting, sport key for SPORT --
    # null for GLOBAL. Combined with key, identifies one setting "line".
    scope_value: Mapped[str | None] = mapped_column(String(100), nullable=True)

    value: Mapped[str] = mapped_column(String(200), nullable=False)  # stored as text, parsed by the caller
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)

    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    changed_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )


class Override(Base):
    """Part O OVERRIDES / Q.2 rule 2: 'An override changes only that
    document ... and is logged with user, reason and the master value it
    replaced; the master value is untouched.'"""

    __tablename__ = "overrides"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="override_document_type"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    setting_key: Mapped[str] = mapped_column(String(100), nullable=False)
    master_value: Mapped[str] = mapped_column(String(200), nullable=False)
    override_value: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
