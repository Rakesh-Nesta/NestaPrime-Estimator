import re
import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.api.documents import _EDITABLE_COST_SHEET_STATUSES
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import CostSheet, CostSheetLine
from app.models.message import Message, MessageChannel, MessageStatus
from app.models.price_request import (
    GstBasis,
    PriceRequest,
    PriceRequestApplyTarget,
    PriceRequestItem,
    PriceRequestStatus,
    PriceRequestVendor,
    VendorReply,
)
from app.models.rate_history import RateHistory
from app.models.rate_item import RateItem, RateSource
from app.models.setting import DocumentType
from app.models.vendor import Vendor

price_requests_router = APIRouter(tags=["price-requests"])

# M.7.5: send / capture-a-reply-as-proposal are Procurement (proposes) /
# PM / Director, never Sales -- same cost-side visibility rule as
# rate_items.py, whose WRITE_ROLES this mirrors exactly.
READ_ROLES = ("pm", "director", "procurement")
WRITE_ROLES = ("pm", "director", "procurement")

# Appendix D: "Communications: ... follow-up days ... 2 working days" --
# a Director-configurable Master Setting, same [confirm]-default pattern
# as rate_items.py's own thresholds.
FOLLOWUP_DAYS_DEFAULT = 2


def _followup_days(db: Session) -> int:
    from app.api.settings import get_current_setting_value

    value = get_current_setting_value(db, "vendor_price_request_followup_days")
    return int(value) if value is not None else FOLLOWUP_DAYS_DEFAULT


def _working_days_elapsed(since: datetime) -> int:
    """M.7.3 rule 6: "no reply within 2 working days [confirm]." Counts
    Mon-Fri days strictly between `since` and now -- no public-holiday
    calendar exists anywhere in this app, so only weekends are excluded."""
    start = since.date()
    today = datetime.now(UTC).date()
    days = 0
    d = start
    while d < today:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days += 1
    return days


_RATE_RE = re.compile(r"(?:rs\.?|inr)\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)
_UNIT_RE = re.compile(r"[\d,]+(?:\.\d+)?\s*/\s*([a-zA-Z]+)")
_VALIDITY_RE = re.compile(r"valid(?:ity)?(?:\s+for)?\s+(\d+)\s*days?", re.IGNORECASE)


def _parse_vendor_reply(text: str) -> dict:
    """M.7.3 rule 3: "The app captures the reply ... and parses rate,
    unit, GST basis and validity (the parser proposes; a human
    confirms)." A lightweight regex assist over the blueprint's own
    example format ("SHS 75x75x2.5 -- Rs 68/kg ex-GST, valid 15 days") --
    no NLP or vendor-reply-format grammar is specified anywhere, so this
    is deliberately simple. Every field it finds is only a *proposal*:
    the caller (a human, per the endpoint below) can override any of
    them, and an unmatched field is left None rather than guessed."""
    parsed: dict = {"parsed_rate": None, "parsed_unit": None, "parsed_gst_basis": None, "parsed_validity_days": None}

    rate_match = _RATE_RE.search(text)
    if rate_match:
        parsed["parsed_rate"] = float(rate_match.group(1).replace(",", ""))

    unit_match = _UNIT_RE.search(text)
    if unit_match:
        parsed["parsed_unit"] = unit_match.group(1)

    lowered = text.lower()
    if "ex-gst" in lowered or "exclusive" in lowered or "excl-gst" in lowered or "excl gst" in lowered:
        parsed["parsed_gst_basis"] = GstBasis.EXCLUSIVE
    elif "incl-gst" in lowered or "inclusive" in lowered or "including gst" in lowered or "incl gst" in lowered:
        parsed["parsed_gst_basis"] = GstBasis.INCLUSIVE

    validity_match = _VALIDITY_RE.search(text)
    if validity_match:
        parsed["parsed_validity_days"] = int(validity_match.group(1))

    return parsed


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PriceRequestItemCreate(BaseModel):
    rate_item_id: uuid.UUID
    spec_override: str | None = None
    quantity_band: str | None = None


class PriceRequestCreate(BaseModel):
    items: list[PriceRequestItemCreate] = Field(min_length=1)
    vendor_ids: list[uuid.UUID] = Field(min_length=1)
    channels: list[MessageChannel] = Field(min_length=1)
    required_by: date | None = None
    requested_validity_days: int | None = None


class PriceRequestItemOut(BaseModel):
    id: uuid.UUID
    rate_item_id: uuid.UUID
    item_name: str
    category: str
    unit: str
    spec_override: str | None
    quantity_band: str | None

    model_config = ConfigDict(from_attributes=True)


class PriceRequestVendorOut(BaseModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    vendor_name: str
    replied: bool
    reminder_due: bool


class PriceRequestOut(BaseModel):
    id: uuid.UUID
    requested_by_id: uuid.UUID
    required_by: date | None
    requested_validity_days: int | None
    status: PriceRequestStatus
    sent_at: datetime
    created_at: datetime
    items: list[PriceRequestItemOut]
    vendors: list[PriceRequestVendorOut]
    reminder_due: bool


def _price_request_to_out(db: Session, pr: PriceRequest) -> PriceRequestOut:
    items = db.query(PriceRequestItem).filter(PriceRequestItem.price_request_id == pr.id).all()
    item_out = []
    for it in items:
        rate_item = db.query(RateItem).filter(RateItem.id == it.rate_item_id).first()
        item_out.append(
            PriceRequestItemOut(
                id=it.id,
                rate_item_id=it.rate_item_id,
                item_name=rate_item.item_name if rate_item else "(deleted rate item)",
                category=rate_item.category if rate_item else "",
                unit=rate_item.unit if rate_item else "",
                spec_override=it.spec_override,
                quantity_band=it.quantity_band,
            )
        )

    replied_vendor_ids = {
        row[0]
        for row in db.query(VendorReply.vendor_id).filter(VendorReply.price_request_id == pr.id).distinct().all()
    }
    followup_days = _followup_days(db)
    elapsed = _working_days_elapsed(pr.sent_at)

    prvs = db.query(PriceRequestVendor).filter(PriceRequestVendor.price_request_id == pr.id).all()
    vendor_out = []
    any_reminder_due = False
    for prv in prvs:
        vendor = db.query(Vendor).filter(Vendor.id == prv.vendor_id).first()
        replied = prv.vendor_id in replied_vendor_ids
        reminder_due = (not replied) and pr.status != PriceRequestStatus.CLOSED and elapsed >= followup_days
        any_reminder_due = any_reminder_due or reminder_due
        vendor_out.append(
            PriceRequestVendorOut(
                id=prv.id,
                vendor_id=prv.vendor_id,
                vendor_name=vendor.name if vendor else "(deleted vendor)",
                replied=replied,
                reminder_due=reminder_due,
            )
        )

    return PriceRequestOut(
        id=pr.id,
        requested_by_id=pr.requested_by_id,
        required_by=pr.required_by,
        requested_validity_days=pr.requested_validity_days,
        status=pr.status,
        sent_at=pr.sent_at,
        created_at=pr.created_at,
        items=item_out,
        vendors=vendor_out,
        reminder_due=any_reminder_due,
    )


class VendorReplyCreate(BaseModel):
    vendor_id: uuid.UUID
    raw_reply_text: str = Field(min_length=1, max_length=1000)
    parsed_rate: float | None = Field(default=None, gt=0)
    parsed_unit: str | None = None
    parsed_gst_basis: GstBasis | None = None
    parsed_validity_days: int | None = None
    attachment_id: uuid.UUID | None = None


class VendorReplyOut(BaseModel):
    id: uuid.UUID
    price_request_id: uuid.UUID
    price_request_item_id: uuid.UUID
    vendor_id: uuid.UUID
    vendor_name: str
    vendor_reliability_score: float | None
    raw_reply_text: str
    parsed_rate: float | None
    parsed_unit: str | None
    parsed_gst_basis: GstBasis | None
    parsed_validity_days: int | None
    attachment_id: uuid.UUID | None
    confirmed: bool
    confirmed_by_id: uuid.UUID | None
    confirmed_at: datetime | None
    applied_as: PriceRequestApplyTarget | None
    created_by_id: uuid.UUID
    created_at: datetime


def _vendor_reply_to_out(db: Session, reply: VendorReply) -> VendorReplyOut:
    vendor = db.query(Vendor).filter(Vendor.id == reply.vendor_id).first()
    return VendorReplyOut(
        id=reply.id,
        price_request_id=reply.price_request_id,
        price_request_item_id=reply.price_request_item_id,
        vendor_id=reply.vendor_id,
        vendor_name=vendor.name if vendor else "(deleted vendor)",
        vendor_reliability_score=float(vendor.reliability_score) if vendor and vendor.reliability_score is not None else None,
        raw_reply_text=reply.raw_reply_text,
        parsed_rate=float(reply.parsed_rate) if reply.parsed_rate is not None else None,
        parsed_unit=reply.parsed_unit,
        parsed_gst_basis=reply.parsed_gst_basis,
        parsed_validity_days=reply.parsed_validity_days,
        attachment_id=reply.attachment_id,
        confirmed=reply.confirmed,
        confirmed_by_id=reply.confirmed_by_id,
        confirmed_at=reply.confirmed_at,
        applied_as=reply.applied_as,
        created_by_id=reply.created_by_id,
        created_at=reply.created_at,
    )


# ---------------------------------------------------------------------------
# Price requests
# ---------------------------------------------------------------------------


def _vendor_recipient_or_400(vendor: Vendor, channel: MessageChannel) -> str:
    """M.7.2 rule 5: WhatsApp only to opted-in numbers; email opt-out is
    honoured (default opt-in, since ordinary business email is opt-out by
    nature -- see Vendor's own docstring note)."""
    if channel == MessageChannel.WHATSAPP:
        if not vendor.whatsapp_opt_in:
            raise HTTPException(
                status_code=400, detail=f"Vendor '{vendor.name}' has not opted in to WhatsApp messages"
            )
        if not vendor.phone:
            raise HTTPException(status_code=400, detail=f"Vendor '{vendor.name}' has no phone number on file")
        return vendor.phone
    if not vendor.email_opt_in:
        raise HTTPException(status_code=400, detail=f"Vendor '{vendor.name}' has opted out of email")
    if not vendor.email:
        raise HTTPException(status_code=400, detail=f"Vendor '{vendor.name}' has no email address on file")
    return vendor.email


def _reply_format_example() -> str:
    return 'Reply with rate, unit, GST inclusive/exclusive, validity, e.g. "SHS 75x75x2.5 -- Rs 68/kg ex-GST, valid 15 days"'


@price_requests_router.post("/price-requests", response_model=PriceRequestOut, status_code=201)
def create_price_request(
    payload: PriceRequestCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """M.7.3 rules 1-2: Procurement/PM/Director picks item(s) and
    vendor(s) and the app sends a templated WhatsApp and/or email per
    vendor -- item, spec, quantity band, delivery location, required-by
    date, requested validity and the reply-format example. Vendors never
    see NestaPrime's current rate, other vendors' rates or any cost/margin
    figure -- the generated message body below only ever contains what
    this endpoint's own payload supplies about the item and the ask."""
    rate_items = []
    for item in payload.items:
        rate_item = db.query(RateItem).filter(RateItem.id == item.rate_item_id).first()
        if not rate_item:
            raise HTTPException(status_code=404, detail=f"Rate item {item.rate_item_id} not found")
        rate_items.append(rate_item)

    vendors = []
    for vendor_id in payload.vendor_ids:
        vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
        if not vendor:
            raise HTTPException(status_code=404, detail=f"Vendor {vendor_id} not found")
        vendors.append(vendor)

    # Validate every vendor is reachable on every requested channel before
    # writing anything -- an all-or-nothing create, matching this
    # codebase's other multi-row creation endpoints.
    for vendor in vendors:
        for channel in payload.channels:
            _vendor_recipient_or_400(vendor, channel)

    price_request = PriceRequest(
        requested_by_id=current_user.id,
        required_by=payload.required_by,
        requested_validity_days=payload.requested_validity_days,
        status=PriceRequestStatus.OPEN,
    )
    db.add(price_request)
    db.commit()
    db.refresh(price_request)

    for item, rate_item in zip(payload.items, rate_items):
        db.add(
            PriceRequestItem(
                price_request_id=price_request.id,
                rate_item_id=rate_item.id,
                spec_override=item.spec_override,
                quantity_band=item.quantity_band,
            )
        )

    item_lines = "; ".join(
        f"{ri.item_name} ({item.spec_override or ri.spec or ri.category}, {item.quantity_band or 'qty tbd'})"
        for item, ri in zip(payload.items, rate_items)
    )
    body = (
        f"Requesting a current price for: {item_lines}. "
        + (f"Required by {payload.required_by}. " if payload.required_by else "")
        + (f"Please quote validity of {payload.requested_validity_days} days. " if payload.requested_validity_days else "")
        + _reply_format_example()
    )

    for vendor in vendors:
        db.add(PriceRequestVendor(price_request_id=price_request.id, vendor_id=vendor.id))
        for channel in payload.channels:
            recipient = _vendor_recipient_or_400(vendor, channel)
            db.add(
                Message(
                    doc_type=DocumentType.PRICE_REQUEST,
                    doc_id=price_request.id,
                    channel=channel,
                    recipient=recipient,
                    sender_id=current_user.id,
                    template_key="vendor_price_update_request",
                    subject="NestaPrime -- price update request" if channel == MessageChannel.EMAIL else None,
                    body_note=body[:500],
                    status=MessageStatus.RECORDED,
                )
            )

    write_audit_log_entry(
        db, current_user, "price_request", price_request.id, "status",
        old_value=None, new_value=PriceRequestStatus.OPEN.value,
        reason=f"Requested {len(payload.items)} item(s) from {len(vendors)} vendor(s)",
    )

    db.commit()
    db.refresh(price_request)
    return _price_request_to_out(db, price_request)


@price_requests_router.get("/price-requests", response_model=list[PriceRequestOut])
def list_price_requests(
    status: PriceRequestStatus | None = None,
    overdue_only: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    query = db.query(PriceRequest)
    if status is not None:
        query = query.filter(PriceRequest.status == status)
    rows = query.order_by(PriceRequest.sent_at.desc()).all()
    out = [_price_request_to_out(db, pr) for pr in rows]
    if overdue_only:
        out = [pr for pr in out if pr.reminder_due]
    return out


@price_requests_router.get("/price-requests/{price_request_id}", response_model=PriceRequestOut)
def get_price_request(
    price_request_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    pr = db.query(PriceRequest).filter(PriceRequest.id == price_request_id).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Price request not found")
    return _price_request_to_out(db, pr)


@price_requests_router.post("/price-requests/{price_request_id}/close", response_model=PriceRequestOut)
def close_price_request(
    price_request_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    pr = db.query(PriceRequest).filter(PriceRequest.id == price_request_id).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Price request not found")
    if pr.status == PriceRequestStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Price request is already closed")

    old_status = pr.status
    pr.status = PriceRequestStatus.CLOSED
    write_audit_log_entry(
        db, current_user, "price_request", pr.id, "status",
        old_value=old_status.value, new_value=PriceRequestStatus.CLOSED.value, reason="Closed",
    )
    db.commit()
    db.refresh(pr)
    return _price_request_to_out(db, pr)


# ---------------------------------------------------------------------------
# Vendor replies
# ---------------------------------------------------------------------------


@price_requests_router.post(
    "/price-requests/{price_request_id}/items/{item_id}/replies",
    response_model=VendorReplyOut,
    status_code=201,
)
def create_vendor_reply(
    price_request_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: VendorReplyCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """M.7.3 rule 3: no inbound WhatsApp/email webhook exists in this
    build, so Procurement/PM/Director reads the vendor's actual reply and
    logs it here. The regex assist in _parse_vendor_reply proposes
    rate/unit/GST-basis/validity from raw_reply_text; any parsed_* field
    explicitly supplied in the payload overrides that proposal -- the
    human typing this call in either case is what "a human confirms"
    means, since nothing here is auto-applied to RATES_MASTER yet (that
    only happens via POST .../use, rule 5)."""
    pr = db.query(PriceRequest).filter(PriceRequest.id == price_request_id).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Price request not found")
    item = (
        db.query(PriceRequestItem)
        .filter(PriceRequestItem.id == item_id, PriceRequestItem.price_request_id == price_request_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Price request item not found")
    invited = (
        db.query(PriceRequestVendor)
        .filter(
            PriceRequestVendor.price_request_id == price_request_id,
            PriceRequestVendor.vendor_id == payload.vendor_id,
        )
        .first()
    )
    if not invited:
        raise HTTPException(status_code=400, detail="This vendor was not invited on this price request")

    proposed = _parse_vendor_reply(payload.raw_reply_text)
    reply = VendorReply(
        price_request_id=price_request_id,
        price_request_item_id=item_id,
        vendor_id=payload.vendor_id,
        raw_reply_text=payload.raw_reply_text,
        parsed_rate=payload.parsed_rate if payload.parsed_rate is not None else proposed["parsed_rate"],
        parsed_unit=payload.parsed_unit if payload.parsed_unit is not None else proposed["parsed_unit"],
        parsed_gst_basis=payload.parsed_gst_basis if payload.parsed_gst_basis is not None else proposed["parsed_gst_basis"],
        parsed_validity_days=(
            payload.parsed_validity_days if payload.parsed_validity_days is not None else proposed["parsed_validity_days"]
        ),
        attachment_id=payload.attachment_id,
        created_by_id=current_user.id,
    )
    db.add(reply)

    if pr.status == PriceRequestStatus.OPEN:
        pr.status = PriceRequestStatus.REPLIED

    db.commit()
    db.refresh(reply)

    vendor = db.query(Vendor).filter(Vendor.id == payload.vendor_id).first()
    write_audit_log_entry(
        db, current_user, "price_request", price_request_id, "vendor_reply",
        old_value=None, new_value=f"{vendor.name if vendor else payload.vendor_id}: {reply.parsed_rate}",
        reason=payload.raw_reply_text[:300],
    )
    db.commit()

    return _vendor_reply_to_out(db, reply)


@price_requests_router.get(
    "/price-requests/{price_request_id}/items/{item_id}/replies",
    response_model=list[VendorReplyOut],
)
def list_vendor_replies(
    price_request_id: uuid.UUID,
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    """M.7.3 rule 5: "Multiple vendor replies for the same item are shown
    side by side ... with a 'use this rate' action." Ordered cheapest
    first (nulls -- an unparsed rate -- last) to make comparison easy."""
    if not db.query(PriceRequestItem).filter(PriceRequestItem.id == item_id).first():
        raise HTTPException(status_code=404, detail="Price request item not found")
    replies = (
        db.query(VendorReply)
        .filter(VendorReply.price_request_id == price_request_id, VendorReply.price_request_item_id == item_id)
        .all()
    )
    replies.sort(key=lambda r: (r.parsed_rate is None, r.parsed_rate if r.parsed_rate is not None else 0))
    return [_vendor_reply_to_out(db, r) for r in replies]


class UseReplyRequest(BaseModel):
    apply_to: PriceRequestApplyTarget
    cost_sheet_line_id: uuid.UUID | None = None


@price_requests_router.post("/vendor-replies/{reply_id}/use", response_model=VendorReplyOut)
def use_vendor_reply(
    reply_id: uuid.UUID,
    payload: UseReplyRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """M.7.3 rule 5: "the chosen vendor's reply is linked to the BOM line
    and later the PO." rule 4: "PM or Director confirms it into the
    master, or applies it as a Manual rate on the open Cost Sheet" -- both
    are offered here (apply_to=both), independently of each other.
    Applying to master mirrors rate_items.py's own update_rate_value:
    closes the currently-open RateHistory row and opens a new one with
    this vendor attributed, and keeps the item Unverified (source=MANUAL,
    verified=False) -- "the captured price is created as an Unverified
    rate proposal" (rule 4); a PM/Director still separately promotes it
    to an AI rate via the existing POST /rate-items/{id}/confirm."""
    reply = db.query(VendorReply).filter(VendorReply.id == reply_id).first()
    if not reply:
        raise HTTPException(status_code=404, detail="Vendor reply not found")
    if reply.parsed_rate is None:
        raise HTTPException(status_code=400, detail="This reply has no parsed rate to apply")
    if payload.apply_to in (PriceRequestApplyTarget.COST_SHEET_LINE, PriceRequestApplyTarget.BOTH):
        if payload.cost_sheet_line_id is None:
            raise HTTPException(status_code=422, detail="cost_sheet_line_id is required for this apply_to")

    item = db.query(PriceRequestItem).filter(PriceRequestItem.id == reply.price_request_item_id).first()
    vendor = db.query(Vendor).filter(Vendor.id == reply.vendor_id).first()

    if payload.apply_to in (PriceRequestApplyTarget.MASTER, PriceRequestApplyTarget.BOTH):
        rate_item = db.query(RateItem).filter(RateItem.id == item.rate_item_id).first()
        if not rate_item:
            raise HTTPException(status_code=404, detail="Rate item no longer exists")

        open_row = (
            db.query(RateHistory)
            .filter(RateHistory.rate_item_id == rate_item.id, RateHistory.effective_to.is_(None))
            .order_by(RateHistory.effective_from.desc())
            .first()
        )
        effective_from = date.today()
        if open_row is not None:
            closed_to = effective_from - timedelta(days=1)
            open_row.effective_to = closed_to if closed_to >= open_row.effective_from else open_row.effective_from

        rate_item.rate = reply.parsed_rate
        rate_item.source = RateSource.MANUAL
        rate_item.verified = False
        rate_item.vendor = vendor.name if vendor else None
        db.add(
            RateHistory(
                rate_item_id=rate_item.id,
                rate=reply.parsed_rate,
                effective_from=effective_from,
                effective_to=None,
                vendor_id=reply.vendor_id,
                changed_by_id=current_user.id,
                reason=f"Vendor price-update reply via price request {reply.price_request_id}",
            )
        )

    if payload.apply_to in (PriceRequestApplyTarget.COST_SHEET_LINE, PriceRequestApplyTarget.BOTH):
        line = db.query(CostSheetLine).filter(CostSheetLine.id == payload.cost_sheet_line_id).first()
        if not line:
            raise HTTPException(status_code=404, detail="Cost sheet line not found")
        cost_sheet = db.query(CostSheet).filter(CostSheet.id == line.cost_sheet_id).first()
        if cost_sheet.status not in _EDITABLE_COST_SHEET_STATUSES:
            raise HTTPException(
                status_code=400, detail=f"Cannot edit a line on a cost sheet in {cost_sheet.status.value} status"
            )
        line.rate = reply.parsed_rate
        line.source = RateSource.MANUAL

    reply.confirmed = True
    reply.confirmed_by_id = current_user.id
    reply.confirmed_at = datetime.now(UTC)
    reply.applied_as = payload.apply_to

    write_audit_log_entry(
        db, current_user, "price_request", reply.price_request_id, "applied_rate",
        old_value=None, new_value=str(reply.parsed_rate),
        reason=f"{vendor.name if vendor else reply.vendor_id}'s reply applied to {payload.apply_to.value}",
        request=request,
    )

    db.commit()
    db.refresh(reply)
    return _vendor_reply_to_out(db, reply)
