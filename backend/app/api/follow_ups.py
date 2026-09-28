"""WP5 (correction plan, 2026-09-27): the shared follow-up API. One entity type,
Opportunity, carries a hard business rule (Director decision, 2026-09-22, previously
enforced only on the stage-change endpoint): an open Opportunity may never be left with
no open follow-up. WP5 extends that same guard to every way a follow-up can stop being
open -- completing it, cancelling it, or deleting it -- not just a stage change, and lets
the caller complete one and schedule its replacement in a single atomic call."""

import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.follow_up_entities import check_follow_up_access, resolve_entity
from app.core.follow_up_sync import WRITES_LOCKED_DETAIL, follow_up_writes_locked, mirror_legacy_columns
from app.db.session import get_db
from app.models.follow_up import (
    TERMINAL_FOLLOW_UP_STATUSES,
    FollowUp,
    FollowUpEntityType,
    FollowUpHistory,
    FollowUpStatus,
    WaitingParty,
)
from app.models.opportunity import TERMINAL_STAGES, Opportunity

router = APIRouter(prefix="/follow-ups", tags=["follow-ups"])


class ReplacementIn(BaseModel):
    next_action: str
    due_date: date
    owner_id: uuid.UUID | None = None


class FollowUpCreate(BaseModel):
    entity_type: FollowUpEntityType
    entity_id: uuid.UUID
    next_action: str
    due_date: date
    owner_id: uuid.UUID | None = None
    waiting_party: WaitingParty | None = None
    review_date: date | None = None
    purpose_key: str | None = None


class FollowUpUpdate(BaseModel):
    next_action: str | None = None
    due_date: date | None = None
    status: FollowUpStatus | None = None
    waiting_party: WaitingParty | None = None
    review_date: date | None = None
    outcome: str | None = None
    owner_id: uuid.UUID | None = None
    # Required when this update would otherwise leave an open Opportunity with no open
    # follow-up -- the replacement is created in the same transaction as this update.
    replacement: ReplacementIn | None = None


class FollowUpOut(BaseModel):
    id: uuid.UUID
    entity_type: FollowUpEntityType
    entity_id: uuid.UUID
    purpose_key: str | None
    owner_id: uuid.UUID | None
    owner_explicitly_assigned: bool
    next_action: str
    due_date: date
    status: FollowUpStatus
    waiting_party: WaitingParty | None
    review_date: date | None
    outcome: str | None
    created_at: datetime
    created_by_id: uuid.UUID
    overdue: bool

    model_config = ConfigDict(from_attributes=True)


def _to_out(row: FollowUp) -> FollowUpOut:
    today = datetime.now(UTC).date()
    overdue = row.due_date < today and row.status not in TERMINAL_FOLLOW_UP_STATUSES
    return FollowUpOut(**{c.name: getattr(row, c.name) for c in FollowUp.__table__.columns}, overdue=overdue)


def _would_leave_opportunity_with_no_open_follow_up(db: Session, row: FollowUp) -> bool:
    """True only when: this follow-up is on an Opportunity, that Opportunity is still open
    (not Won/Lost -- a closed one has no "always needs a follow-up" rule to begin with), and
    no OTHER follow-up on it is currently open/in_progress/waiting."""
    if row.entity_type != FollowUpEntityType.OPPORTUNITY:
        return False
    opportunity = db.query(Opportunity).filter(Opportunity.id == row.entity_id).first()
    if opportunity is None or opportunity.stage in TERMINAL_STAGES:
        return False
    other_open = (
        db.query(FollowUp)
        .filter(
            FollowUp.entity_type == FollowUpEntityType.OPPORTUNITY,
            FollowUp.entity_id == row.entity_id,
            FollowUp.id != row.id,
            FollowUp.status.notin_(TERMINAL_FOLLOW_UP_STATUSES),
        )
        .first()
    )
    return other_open is None


def _log_history(db: Session, follow_up_id: uuid.UUID, field: str, old, new, user_id: uuid.UUID) -> None:
    db.add(
        FollowUpHistory(
            follow_up_id=follow_up_id,
            changed_field=field,
            old_value=None if old is None else str(old),
            new_value=None if new is None else str(new),
            changed_by_id=user_id,
        )
    )


@router.post("", response_model=FollowUpOut, status_code=201)
def create_follow_up(
    payload: FollowUpCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if follow_up_writes_locked(db):
        raise HTTPException(status_code=423, detail=WRITES_LOCKED_DETAIL)
    resolved = check_follow_up_access(db, current_user, payload.entity_type, payload.entity_id, need="write")

    if payload.purpose_key is not None:
        existing = (
            db.query(FollowUp)
            .filter(
                FollowUp.entity_type == payload.entity_type,
                FollowUp.entity_id == payload.entity_id,
                FollowUp.purpose_key == payload.purpose_key,
                FollowUp.status.notin_(TERMINAL_FOLLOW_UP_STATUSES),
            )
            .first()
        )
        if existing is not None:
            # Idempotent: an automated caller retrying the same action gets the same row
            # back, not a duplicate.
            return _to_out(existing)

    owner_id = payload.owner_id if payload.owner_id is not None else resolved.owner_id
    owner_explicitly_assigned = payload.owner_id is not None and payload.owner_id != resolved.owner_id

    row = FollowUp(
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        purpose_key=payload.purpose_key,
        owner_id=owner_id,
        owner_explicitly_assigned=owner_explicitly_assigned,
        next_action=payload.next_action,
        due_date=payload.due_date,
        waiting_party=payload.waiting_party,
        review_date=payload.review_date,
        created_by_id=current_user.id,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # A purpose_key that already has an open row for this entity -- idempotent no-op
        # for an automated caller retrying the same action, not an error.
        db.rollback()
        if payload.purpose_key is None:
            raise
        existing = (
            db.query(FollowUp)
            .filter(
                FollowUp.entity_type == payload.entity_type,
                FollowUp.entity_id == payload.entity_id,
                FollowUp.purpose_key == payload.purpose_key,
                FollowUp.status.notin_(TERMINAL_FOLLOW_UP_STATUSES),
            )
            .first()
        )
        if existing is None:
            raise
        return _to_out(existing)
    # WP5 integration: the reverse direction of follow_up_sync.set_primary_follow_up --
    # a follow-up created directly through this API (the central Follow-ups screen) may
    # be the soonest-due one on a Client/Opportunity, so its own legacy column needs to
    # reflect that (see follow_up_sync.mirror_legacy_columns).
    mirror_legacy_columns(db, row.entity_type, row.entity_id)
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.get("", response_model=list[FollowUpOut])
def list_follow_ups(
    entity_type: FollowUpEntityType | None = None,
    entity_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
    status: FollowUpStatus | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    per_row_check = True
    if entity_type is not None and entity_id is not None:
        check_follow_up_access(db, current_user, entity_type, entity_id, need="read")
        query = db.query(FollowUp).filter(FollowUp.entity_type == entity_type, FollowUp.entity_id == entity_id)
        per_row_check = False
    elif owner_id is not None:
        # "My follow-ups": every row this user is entitled to see across every entity
        # type, narrowed to one owner. A Sales user may only ask for their own id here --
        # this list intentionally does not become a way to browse everyone else's
        # follow-ups one owner at a time.
        if current_user.role.value == "sales" and owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Sales may only list their own follow-ups")
        query = db.query(FollowUp).filter(FollowUp.owner_id == owner_id)
    else:
        # WP5 integration: the central Follow-ups screen's org-wide view -- no filter at
        # all means "everything this user is entitled to see". A Sales user is ALWAYS
        # narrowed to their own here -- unlike list_opportunities/list_clients, this is
        # not conditional on the Director's own-records switch (Amendment 60): browsing
        # every other Sales rep's follow-up notes org-wide in one screen is a bigger
        # exposure than seeing an unowned record in a filtered list, so this list stays
        # narrow for Sales regardless of that switch's state. Every other role sees the
        # full set, still re-checked per row below.
        query = db.query(FollowUp)
        if current_user.role.value == "sales":
            query = query.filter(FollowUp.owner_id == current_user.id)

    if status is not None:
        query = query.filter(FollowUp.status == status)
    rows = query.order_by(FollowUp.due_date.asc()).all()

    if per_row_check:
        # Re-check access per row rather than trusting the owner_id/no-filter query alone,
        # since a follow-up's current owner and its entity's own permission gate can
        # diverge (an explicitly-assigned specialist may not otherwise have write access to
        # the parent record) -- read access on the entity is still required to see it here.
        visible = []
        for row in rows:
            try:
                check_follow_up_access(db, current_user, row.entity_type, row.entity_id, need="read")
            except HTTPException:
                continue
            visible.append(row)
        rows = visible

    return [_to_out(row) for row in rows]


@router.patch("/{follow_up_id}", response_model=FollowUpOut)
def update_follow_up(
    follow_up_id: uuid.UUID,
    payload: FollowUpUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if follow_up_writes_locked(db):
        raise HTTPException(status_code=423, detail=WRITES_LOCKED_DETAIL)
    row = db.query(FollowUp).filter(FollowUp.id == follow_up_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    check_follow_up_access(db, current_user, row.entity_type, row.entity_id, need="write")

    changes = payload.model_dump(exclude_unset=True, exclude={"replacement"})

    if "status" in changes and changes["status"] in TERMINAL_FOLLOW_UP_STATUSES:
        if _would_leave_opportunity_with_no_open_follow_up(db, row):
            if payload.replacement is None:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "This is the Opportunity's last open follow-up -- completing or cancelling it "
                        "would leave the Opportunity with none. Include 'replacement' to schedule the "
                        "next one in the same request, or move the Opportunity to Won/Lost instead."
                    ),
                )

    if "waiting_party" not in changes and changes.get("status") == FollowUpStatus.WAITING:
        raise HTTPException(status_code=400, detail="waiting_party is required when status is 'waiting'")

    for field in ("due_date", "owner_id", "status", "next_action"):
        if field in changes and changes[field] != getattr(row, field):
            _log_history(db, row.id, field, getattr(row, field), changes[field], current_user.id)
            if field == "owner_id":
                row.owner_explicitly_assigned = True

    for field, value in changes.items():
        setattr(row, field, value)

    if payload.replacement is not None:
        resolved = resolve_entity(db, row.entity_type, row.entity_id)
        replacement_owner = payload.replacement.owner_id if payload.replacement.owner_id is not None else (
            resolved.owner_id if resolved else None
        )
        db.add(
            FollowUp(
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                owner_id=replacement_owner,
                owner_explicitly_assigned=payload.replacement.owner_id is not None,
                next_action=payload.replacement.next_action,
                due_date=payload.replacement.due_date,
                created_by_id=current_user.id,
            )
        )

    # autoflush is off for this app's sessions (app/db/session.py) -- without an
    # explicit flush here, mirror_legacy_columns' own query would still see the
    # pre-update DB state (the status change above, and any new replacement row,
    # not yet visible), and mirror the wrong follow-up onto the legacy columns.
    db.flush()
    mirror_legacy_columns(db, row.entity_type, row.entity_id)
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.delete("/{follow_up_id}", status_code=204)
def delete_follow_up(
    follow_up_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if follow_up_writes_locked(db):
        raise HTTPException(status_code=423, detail=WRITES_LOCKED_DETAIL)
    row = db.query(FollowUp).filter(FollowUp.id == follow_up_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    check_follow_up_access(db, current_user, row.entity_type, row.entity_id, need="write")

    if row.status not in TERMINAL_FOLLOW_UP_STATUSES and _would_leave_opportunity_with_no_open_follow_up(db, row):
        raise HTTPException(
            status_code=400,
            detail=(
                "This is the Opportunity's last open follow-up -- deleting it would leave the "
                "Opportunity with none. Create its replacement first, then delete this one."
            ),
        )

    entity_type, entity_id = row.entity_type, row.entity_id
    db.query(FollowUpHistory).filter(FollowUpHistory.follow_up_id == row.id).delete()
    db.delete(row)
    db.flush()
    mirror_legacy_columns(db, entity_type, entity_id)
    db.commit()
