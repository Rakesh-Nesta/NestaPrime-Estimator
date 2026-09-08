import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PriceRequestStatus(str, enum.Enum):
    """M.7.3 names four states (open / replied / closed / expired) but an
    automatic open->expired transition needs a background job runner this
    app doesn't have (the same gap left open for SLA timers/escalation) --
    so only the three states a person or a reply actually drives are
    persisted here; "no reply within N working days" is instead exposed
    as a computed `reminder_due` flag on the API response (rule 6)."""

    OPEN = "open"
    REPLIED = "replied"
    CLOSED = "closed"


class GstBasis(str, enum.Enum):
    INCLUSIVE = "inclusive"
    EXCLUSIVE = "exclusive"


class PriceRequestApplyTarget(str, enum.Enum):
    MASTER = "master"
    COST_SHEET_LINE = "cost_sheet_line"
    BOTH = "both"


class PriceRequest(Base):
    """Part O PRICE_REQUESTS / M.7.3: "From the Rate Sheet (J.1), a
    stale-rate alert, a commodity alert, or the RFQ screen, Procurement /
    PM / Director selects one or more items and one or more vendors and
    chooses Request price update." One row per such campaign; the actual
    items and vendors invited live in PriceRequestItem/PriceRequestVendor
    (Part O's items[]/vendor_ids[] arrays, normalised to child tables like
    every other []-array in this codebase's data model)."""

    __tablename__ = "price_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requested_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    required_by: Mapped[date | None] = mapped_column(Date, nullable=True)
    requested_validity_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[PriceRequestStatus] = mapped_column(
        Enum(PriceRequestStatus, name="price_request_status"), default=PriceRequestStatus.OPEN, nullable=False
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class PriceRequestItem(Base):
    """One requested item within a PriceRequest -- "item, specification,
    quantity band" (M.7.3 rule 2). rate_item_id links back to J.1's
    RATES_MASTER row this request is trying to get a fresher price for;
    spec_override/quantity_band let the request be more specific than the
    rate item's own catalog spec for this particular ask."""

    __tablename__ = "price_request_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    price_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_requests.id"), nullable=False
    )
    rate_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rate_items.id"), nullable=False)
    spec_override: Mapped[str | None] = mapped_column(String(300), nullable=True)
    quantity_band: Mapped[str | None] = mapped_column(String(100), nullable=True)


class PriceRequestVendor(Base):
    """Which vendor(s) a PriceRequest was sent to -- kept as its own
    table (rather than inferred from Message recipients) so "no reply
    within 2 working days" (rule 6) can be computed per invited vendor
    even before any Message-send bookkeeping is consulted."""

    __tablename__ = "price_request_vendors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    price_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_requests.id"), nullable=False
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False)


class VendorReply(Base):
    """M.7.3 rule 3-4: "The vendor replies on WhatsApp or email. The app
    captures the reply in the same thread and parses rate, unit, GST
    basis and validity (the parser proposes; a human confirms)... The
    captured price is created as an Unverified rate proposal in
    RATES_MASTER." No inbound WhatsApp/email webhook exists in this build
    (see Message's own docstring), so Procurement/PM/Director manually
    types in what the vendor replied; raw_reply_text preserves that
    original text, parsed_* holds the values a human has confirmed (a
    lightweight regex assist in the API pre-fills these from raw_reply_text
    when the caller doesn't supply them explicitly -- see
    _parse_vendor_reply in app/api/price_requests.py -- but nothing here
    is written to RATES_MASTER until a person picks "use this rate";
    unlike J.1's RateItem, a reply that is never used is not itself a
    RateHistory row, since several vendors' replies must coexist for the
    side-by-side comparison rule 5 describes, and RateItem only ever holds
    one live rate at a time."""

    __tablename__ = "vendor_replies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    price_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_requests.id"), nullable=False
    )
    price_request_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_request_items.id"), nullable=False
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False)

    raw_reply_text: Mapped[str] = mapped_column(String(1000), nullable=False)
    parsed_rate: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    parsed_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    parsed_gst_basis: Mapped[GstBasis | None] = mapped_column(Enum(GstBasis, name="gst_basis"), nullable=True)
    parsed_validity_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    attachment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attachments.id"), nullable=True
    )

    # "Use this rate" (rule 5) -- set once, the first time this reply is
    # applied to the master rate and/or a Cost Sheet line. A reply can be
    # captured and compared without ever being used.
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confirmed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    applied_as: Mapped[PriceRequestApplyTarget | None] = mapped_column(
        Enum(PriceRequestApplyTarget, name="price_request_apply_target"), nullable=True
    )

    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
