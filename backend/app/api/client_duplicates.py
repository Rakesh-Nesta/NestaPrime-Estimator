import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.core import ownership
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.client import Client
from app.models.duplicate_client_pair import DismissedDuplicatePair

router = APIRouter(prefix="/clients/{client_id}/duplicates", tags=["client-duplicates"])

# Same role set as Client's own write endpoints -- dismissing/restoring a suggestion is treated
# as editing shared data about the client pair, not a read-only action.
DISMISS_ROLES = ("sales", "pm", "director")
RESTORE_ROLES = ("pm", "director")  # P2 contract, approved: a narrower bar than dismissal itself.

MAX_SUGGESTIONS = 5


class DuplicateCandidateOut(BaseModel):
    client_id: uuid.UUID
    name: str
    matched_field: str  # "phone" | "email" | "name"

    model_config = ConfigDict(from_attributes=True)


class DuplicatePairAction(BaseModel):
    other_client_id: uuid.UUID


class DismissedPairOut(BaseModel):
    client_id_a: uuid.UUID
    client_id_b: uuid.UUID
    dismissed_by_id: uuid.UUID
    dismissed_at: datetime

    model_config = ConfigDict(from_attributes=True)


def _visible_client_or_404(db: Session, user, target_id: uuid.UUID) -> Client:
    """P2 (Client 360 contract): the concealed-record pattern -- whether target_id names a
    Client that doesn't exist, or one that exists but this viewer cannot read under Amendment 60
    scoping, the answer is identical (404, 'Not found'). A distinguishable response (e.g. 403)
    would itself disclose that the other client exists."""
    client = db.query(Client).filter(Client.id == target_id).first()
    if client is None:
        raise HTTPException(status_code=404, detail=ownership.NOT_FOUND)
    if ownership.scoping_applies(db, user) and client.owner_id != user.id:
        raise HTTPException(status_code=404, detail=ownership.NOT_FOUND)
    return client


def _normalise_pair(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (a, b) if str(a) < str(b) else (b, a)


@router.get("", response_model=list[DuplicateCandidateOut])
def list_duplicate_candidates(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("sales", "pm", "director", "procurement")),
):
    """P2 (Client 360 contract), Section 6: suggest-only, never auto-merge. The candidate query
    runs through the same scoping as any Client list for this viewer BEFORE matching, so an
    inaccessible client can never surface as a suggestion. Matched field only is shown -- not
    the candidate's other details."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    dismissed = {
        (row.client_id_a, row.client_id_b)
        for row in db.query(DismissedDuplicatePair).filter(
            or_(DismissedDuplicatePair.client_id_a == client_id, DismissedDuplicatePair.client_id_b == client_id)
        )
    }

    query = db.query(Client).filter(Client.id != client_id)
    if ownership.scoping_applies(db, current_user):
        query = query.filter(Client.owner_id == current_user.id)

    email = (client.email or "").strip().lower()
    digits = re.sub(r"[^0-9]", "", client.phone or "")[-10:]
    name = (client.name or "").strip().lower()
    conditions = []
    if email:
        conditions.append((func.lower(Client.email) == email, "email"))
    if len(digits) >= 7:
        conditions.append((func.regexp_replace(Client.phone, "[^0-9]", "", "g").like(f"%{digits}"), "phone"))
    if name:
        conditions.append((func.lower(Client.name).like(f"%{name}%"), "name"))
    if not conditions:
        return []

    query = query.filter(or_(*(c for c, _ in conditions)))
    results: list[DuplicateCandidateOut] = []
    for candidate in query.order_by(Client.name).limit(50).all():
        pair = _normalise_pair(client_id, candidate.id)
        if pair in dismissed:
            continue
        matched_field = "name"
        c_email = (candidate.email or "").strip().lower()
        c_digits = re.sub(r"[^0-9]", "", candidate.phone or "")[-10:]
        if email and c_email == email:
            matched_field = "email"
        elif digits and len(digits) >= 7 and c_digits.endswith(digits):
            matched_field = "phone"
        results.append(DuplicateCandidateOut(client_id=candidate.id, name=candidate.name, matched_field=matched_field))
        if len(results) >= MAX_SUGGESTIONS:
            break
    return results


@router.post("/dismiss", response_model=DismissedPairOut, status_code=201)
def dismiss_duplicate(
    client_id: uuid.UUID,
    payload: DuplicatePairAction,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DISMISS_ROLES)),
):
    if client_id == payload.other_client_id:
        raise HTTPException(status_code=400, detail="A client cannot be a duplicate of itself")
    # client_id's own visibility is already enforced by the global enforce_own_records
    # dependency (client_id is a covered path param); other_client_id is not a path param, so
    # it needs the same concealed check applied explicitly here.
    _visible_client_or_404(db, current_user, client_id)
    _visible_client_or_404(db, current_user, payload.other_client_id)

    id_a, id_b = _normalise_pair(client_id, payload.other_client_id)
    existing = db.query(DismissedDuplicatePair).filter(
        DismissedDuplicatePair.client_id_a == id_a, DismissedDuplicatePair.client_id_b == id_b
    ).first()
    if existing:
        return existing

    row = DismissedDuplicatePair(client_id_a=id_a, client_id_b=id_b, dismissed_by_id=current_user.id)
    db.add(row)
    write_audit_log_entry(
        db, current_user, "duplicate_client_pair", None, "dismissed",
        old_value=None, new_value=f"{id_a}:{id_b}", request=request,
    )
    db.commit()
    db.refresh(row)
    return row


@router.post("/restore", status_code=204)
def restore_duplicate(
    client_id: uuid.UUID,
    payload: DuplicatePairAction,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*RESTORE_ROLES)),
):
    if client_id == payload.other_client_id:
        raise HTTPException(status_code=400, detail="A client cannot be a duplicate of itself")
    id_a, id_b = _normalise_pair(client_id, payload.other_client_id)
    row = db.query(DismissedDuplicatePair).filter(
        DismissedDuplicatePair.client_id_a == id_a, DismissedDuplicatePair.client_id_b == id_b
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Dismissed pair not found")
    db.delete(row)
    write_audit_log_entry(
        db, current_user, "duplicate_client_pair", None, "restored",
        old_value=f"{id_a}:{id_b}", new_value=None, request=request,
    )
    db.commit()
