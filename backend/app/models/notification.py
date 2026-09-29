"""WP8 (correction plan, 2026-09-29): in-app notification inbox + the record of every daily
reminder/escalation email attempted. One row per (recipient, follow-up, calendar day), unique
on that triple, which is both the duplicate-prevention mechanism (DB-enforced, matching WP5's
own partial-unique-index precedent for FollowUp itself) and the retry ledger (email_status/
email_attempts/email_last_error let a later cron run safely retry only what didn't send,
without ever double-sending what already did). No separate "system actor" audit trail is
needed for the cron job's own writes -- this table already IS the honest record of what was
communicated to whom and when, more specific than a generic AuditLogEntry would be, and it
avoids inventing either a phantom system User row or a schema change to AuditLogEntry.user_id
(which is NOT NULL, with no existing precedent for a non-human actor anywhere in this
codebase)."""

import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.follow_up import FollowUpEntityType


class NotificationKind(str, enum.Enum):
    # Daily digest item to the follow-up's own owner: "this is due/overdue."
    FOLLOW_UP_REMINDER = "follow_up_reminder"
    # To active Directors: a follow-up has been overdue at least the configured threshold.
    FOLLOW_UP_OVERDUE_ESCALATION = "follow_up_overdue_escalation"
    # To active Directors: the follow-up's own assigned owner cannot currently access it
    # (the confirmed WP5 gap -- see app/core/follow_up_entities.py's own docstring). Never
    # sent to the assignee themselves, since that would be exactly the "unusable link" this
    # is meant to avoid.
    ACCESS_MISMATCH_ESCALATION = "access_mismatch_escalation"


class NotificationEmailStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        # The actual duplicate-prevention guarantee under a genuine race between two
        # overlapping cron ticks -- the app also checks-before-insert (belt), this index is
        # the real one (braces), same two-layer pattern as FollowUp's own unique index.
        Index(
            "uq_notifications_recipient_follow_up_kind_date",
            "user_id", "follow_up_id", "kind", "notification_date",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Recipient -- who sees this in their own in-app inbox and (if email_status ends up SENT)
    # whose mailbox it was addressed to. Always a real User, never a raw email string (unlike
    # Message.recipient) -- a notification only ever exists because a real account needed to
    # know something, matching the in-app-inbox half of this feature.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    kind: Mapped[NotificationKind] = mapped_column(Enum(NotificationKind, name="notification_kind"), nullable=False)

    # What calendar day (IST, matching the 9am Asia/Kolkata digest) this notification belongs
    # to -- the idempotency/duplicate-prevention key, not a UI-facing field.
    notification_date: Mapped[date] = mapped_column(Date, nullable=False)

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # The FollowUp this notification is about -- nullable because a FollowUp row is never
    # deleted in this codebase (matching every other entity here), so this is always
    # populated in practice, but kept nullable rather than assuming that invariant forever.
    follow_up_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("follow_ups.id"), nullable=True)
    # Copied from the FollowUp at creation time so the frontend can navigate straight to the
    # source record without a second lookup -- mirrors FollowUp's own polymorphic pair.
    entity_type: Mapped[FollowUpEntityType | None] = mapped_column(
        Enum(FollowUpEntityType, name="follow_up_entity_type", create_type=False), nullable=True
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # In-app read/unread -- the inbox's own half of this feature.
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Email delivery bookkeeping for the SAME notification. PENDING until a send is actually
    # attempted (an escalation notification with no configured recipient email, for instance,
    # never leaves PENDING -- it's still visible in-app either way). email_attempts caps how
    # many times a later run will retry a FAILED send (see app/core/reminders.py).
    email_status: Mapped[NotificationEmailStatus] = mapped_column(
        Enum(NotificationEmailStatus, name="notification_email_status"),
        default=NotificationEmailStatus.PENDING, nullable=False,
    )
    email_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    email_last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
