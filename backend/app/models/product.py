import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Product(Base):
    """Amendment 7 (Annexure 2): "products with approximate pricing under
    each vendor; feeds rate sheet and price-update requests." A vendor's
    own catalog reference -- distinct from RateItem (the estimator's own
    master rate card, one flat rate per item, vendor-agnostic): this is
    "vendor A sells X at ~Rs Y," several vendors can each carry their own
    Product row for a broadly similar item, and approx_price is
    explicitly a reference figure, not a locked quote (see RateHistory /
    a real RFQ reply for that)."""

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    spec: Mapped[str | None] = mapped_column(String(300), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    approx_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
