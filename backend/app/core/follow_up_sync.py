"""WP5 integration (correction plan, 2026-09-27/28): keeps a Client's or Opportunity's
legacy "next follow-up" columns and the shared FollowUp table consistent in both
directions.

Client.next_follow_up_date/follow_up_note and Opportunity.next_follow_up_date/
follow_up_note (Amendments 42/44) predate the shared /follow-ups system (WP5 backend,
PR #265) and stay in place -- every existing screen that reads them (ClientsAdmin.jsx,
Opportunities.jsx, Dashboard.jsx) keeps working unchanged.

Forward direction (a legacy Client/Opportunity endpoint is edited):
`set_primary_follow_up` upserts the one automated "primary_reminder" FollowUp row that
edit represents, then calls `mirror_legacy_columns` to derive what the legacy columns
should now show.

Reverse direction (the shared table is edited directly, through the generic
/follow-ups endpoints the central Follow-ups screen uses): call `mirror_legacy_columns`
after the change so the source screen reflects it too -- see app/api/follow_ups.py.

`mirror_legacy_columns` always derives the legacy columns from whichever open
FollowUp on that entity is due soonest (not specifically the "primary" row), which is
what makes the reverse direction correct even once a second follow-up exists on the
same entity (a replacement created alongside completing the primary one, for example):
the legacy field keeps showing a real, currently-open next action, never stale or
prematurely null while one still exists -- preserving the Director's "an open
Opportunity is never left without a future follow-up date" rule from *either* side.

Containment mode (correction-plan requirement, 2026-09-28): while the Director-level
Master Setting `follow_ups_writes_locked` is on, this module's own functions are not
what refuses the write -- every route that can write follow-up data (every /follow-ups
write endpoint, and every Client/Opportunity route that calls set_primary_follow_up)
checks `follow_up_writes_locked` itself, first, before touching anything, and returns
423 with no mutation at all. Reads are unaffected everywhere."""

from datetime import date

from sqlalchemy.orm import Session

from app.api.settings import get_current_setting_value
from app.models.client import Client
from app.models.follow_up import TERMINAL_FOLLOW_UP_STATUSES, FollowUp, FollowUpEntityType, FollowUpStatus
from app.models.opportunity import Opportunity

PRIMARY_PURPOSE_KEY = "primary_reminder"

LOCK_SETTING_KEY = "follow_ups_writes_locked"

WRITES_LOCKED_DETAIL = (
    "Follow-up writes are temporarily locked for maintenance. Existing follow-ups "
    "remain visible; try again shortly."
)


def follow_up_writes_locked(db: Session) -> bool:
    return (get_current_setting_value(db, LOCK_SETTING_KEY) or "").strip().lower() in ("on", "true", "1", "yes")


def _find_open_primary(db: Session, entity_type: FollowUpEntityType, entity_id) -> FollowUp | None:
    return (
        db.query(FollowUp)
        .filter(
            FollowUp.entity_type == entity_type,
            FollowUp.entity_id == entity_id,
            FollowUp.purpose_key == PRIMARY_PURPOSE_KEY,
            FollowUp.status.notin_(TERMINAL_FOLLOW_UP_STATUSES),
        )
        .first()
    )


def mirror_legacy_columns(db: Session, entity_type: FollowUpEntityType, entity_id) -> None:
    """Sets a Client's or Opportunity's legacy next_follow_up_date/follow_up_note from
    whichever of its own FollowUp rows is open and due soonest, or clears the date (and
    leaves the note as historical context) when none is open. A no-op for any other
    entity_type -- nothing else has legacy columns to mirror."""
    if entity_type == FollowUpEntityType.CLIENT:
        entity = db.query(Client).filter(Client.id == entity_id).first()
    elif entity_type == FollowUpEntityType.OPPORTUNITY:
        entity = db.query(Opportunity).filter(Opportunity.id == entity_id).first()
    else:
        return
    if entity is None:
        return

    soonest_open = (
        db.query(FollowUp)
        .filter(
            FollowUp.entity_type == entity_type,
            FollowUp.entity_id == entity_id,
            FollowUp.status.notin_(TERMINAL_FOLLOW_UP_STATUSES),
        )
        .order_by(FollowUp.due_date.asc())
        .first()
    )
    if soonest_open is None:
        entity.next_follow_up_date = None
    else:
        entity.next_follow_up_date = soonest_open.due_date
        entity.follow_up_note = soonest_open.next_action


def set_primary_follow_up(
    db: Session,
    entity,
    entity_type: FollowUpEntityType,
    *,
    due_date: date | None,
    note: str | None,
    current_user,
) -> None:
    """The write path a legacy Client/Opportunity follow-up endpoint calls. `entity` is
    already added to `db` (a fresh Opportunity needs `db.flush()` first so `entity.id`
    exists). Callers must check `follow_up_writes_locked` themselves before calling this
    -- see this module's own docstring. `due_date=None` completes the open primary
    FollowUp (an Opportunity's terminal-stage clear, or a Client's reminder being
    cleared) rather than leaving a stale open row -- this is a normal close, not a
    cancellation of a mistaken action, so it is logged as completed, not cancelled."""
    existing = _find_open_primary(db, entity_type, entity.id)

    if due_date is None:
        if existing is not None:
            existing.status = FollowUpStatus.COMPLETED
        # mirror_legacy_columns below leaves follow_up_note untouched once nothing is
        # open (so an Opportunity's terminal-stage clear -- which always passes its own
        # current note back -- keeps it as historical context); a Client explicitly
        # clearing both fields in the same call needs that same explicit intent honored
        # here, or its own null would otherwise be silently dropped. Whichever of these
        # this call actually is, `note` already carries the caller's real intent -- set
        # it directly; mirror_legacy_columns still gets the final say if some OTHER
        # follow-up on this entity is still open.
        entity.follow_up_note = note
    else:
        action_text = note or "Follow up"
        if existing is None:
            db.add(
                FollowUp(
                    entity_type=entity_type,
                    entity_id=entity.id,
                    purpose_key=PRIMARY_PURPOSE_KEY,
                    owner_id=entity.owner_id,
                    next_action=action_text,
                    due_date=due_date,
                    created_by_id=current_user.id,
                )
            )
        else:
            existing.due_date = due_date
            existing.next_action = action_text
            existing.owner_id = entity.owner_id

    db.flush()
    mirror_legacy_columns(db, entity_type, entity.id)
