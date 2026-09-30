import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketplaceLeadImportStatus:
    """P3 contract (revision 4), Section 2. Plain string constants, not a SQLAlchemy/Postgres
    Enum type -- the contract's own wire schema specifies `status VARCHAR(20)`, and this status
    set is expected to keep growing (quarantined/expired were both added in revision 4 alone), so
    a plain column avoids the ALTER TYPE ceremony every native enum change in this codebase needs."""

    PENDING = "pending"
    QUARANTINED = "quarantined"
    CONVERTED = "converted"
    DUPLICATE_DELIVERY = "duplicate_delivery"
    REJECTED = "rejected"
    EXPIRED = "expired"


class MarketplaceLeadImport(Base):
    """P3 contract (revision 4), Section 2: the import ledger. One row per lead delivered by a
    marketplace Pull/Push adapter, `platform` first so a future TradeIndia adapter (Section 10,
    explicitly not designed yet) can reuse this same table without a schema change.

    external_id/enquiry_time are nullable on purpose (revision 4 fix): Capture only attempts a
    structural extraction of them, never full validation, so a malformed item can still get a
    durable `quarantined` row instead of being silently dropped or blocking its whole window.

    sender_company/.../query_type are durable copies made at Process time (or, for a quarantined
    row, whatever could be extracted) -- they must never depend on raw_payload still existing,
    since raw_payload is nulled by the 90-day retention purge (retention.py) while these are not.
    """

    __tablename__ = "marketplace_lead_imports"
    __table_args__ = (
        UniqueConstraint("platform", "account_id", "external_id", name="uq_marketplace_lead_imports_identity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    account_id: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    enquiry_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    received_via: Mapped[str] = mapped_column(String(10), nullable=False)

    # NULL once the 90-day retention purge (anchored to received_at, revision 4 fix) removes it.
    # NOT NULL while the row is within its retention window.
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    sender_company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sender_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sender_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sender_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sender_pincode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sender_country_iso: Mapped[str | None] = mapped_column(String(5), nullable=True)
    query_type: Mapped[str | None] = mapped_column(String(5), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default=MarketplaceLeadImportStatus.PENDING, nullable=False)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id"), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # AUTOMATIC retries only -- Section 2's cap applies here, never to a manual retry.
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    manually_retried_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    manually_retried_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )


class MarketplaceLeadImportDuplicateDelivery(Base):
    """P3 contract, Section 2: 'the new delivery attempt is logged as a duplicate_delivery event
    in a separate, lightweight log (count and last-seen timestamp only) -- the original row ...
    is never opened for a write at all.' One row per original ledger row that has ever received a
    repeat delivery; delivery_count/last_seen_at are upserted, the original row itself is untouched."""

    __tablename__ = "marketplace_lead_import_duplicate_deliveries"

    ledger_row_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_lead_imports.id"), primary_key=True
    )
    delivery_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class MarketplaceApiRateGate(Base):
    """P3 contract, Section 3: 'a single shared gate -- one row recording the timestamp of the
    last IndiaMART API call of any kind ... is checked by all three callers: the scheduled Pull
    job, each backfill chunk, and Verify key now.' One singleton row per platform, acquired via
    `SELECT ... FOR UPDATE` before any outbound HTTP call, released automatically on commit."""

    __tablename__ = "marketplace_api_rate_gates"

    platform: Mapped[str] = mapped_column(String(20), primary_key=True)
    last_call_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MarketplacePullCheckpoint(Base):
    """P3 contract, Section 3: the Pull adapter's own stored checkpoint. The contract's own text
    proposed reusing the Director-facing Master Settings table (`app.models.setting.Setting`) for
    this -- found, during implementation, to be a poor fit: that table is versioned/audited/
    human-editable specifically for business-policy values a Director sets occasionally, while this
    value is machine-written on every successful Capture pass (every 10-15 minutes) and carries no
    business decision at all. Using it would mean either a growing, meaningless "history" of
    machine writes attributed to a system user, or writing around `create_setting_version`'s own
    request-scoped audit-logging entirely -- both worse than a small dedicated table. Flagged here,
    not silently substituted: functionally this still satisfies the contract's own requirement
    ("a timestamp, not a secret") using this codebase's existing "small singleton state table"
    pattern (see MarketplaceApiRateGate above) instead of the versioned-settings mechanism."""

    __tablename__ = "marketplace_pull_checkpoints"

    platform: Mapped[str] = mapped_column(String(20), primary_key=True)
    last_captured_end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
