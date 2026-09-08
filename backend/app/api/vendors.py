import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.vendor import Vendor

vendors_router = APIRouter(prefix="/vendors", tags=["vendors"])

# M.4: "Edit consumption sheet, raise RFQ / PO" -- Sales/Site Engineer/CA
# have no reason to see vendor relationships or pricing.
PROCUREMENT_ROLES = ("pm", "director", "procurement")


class VendorCreate(BaseModel):
    name: str
    city: str | None = None
    category: str | None = None
    contact_name: str | None = None
    phone: str | None = None
    email: str | None = None
    gstin: str | None = None
    rcm_applicable: bool = False
    payment_terms: str | None = None
    reliability_score: float | None = None
    whatsapp_opt_in: bool = False
    email_opt_in: bool = True
    consent_date: date | None = None


class VendorUpdate(BaseModel):
    name: str | None = None
    city: str | None = None
    category: str | None = None
    contact_name: str | None = None
    phone: str | None = None
    email: str | None = None
    gstin: str | None = None
    rcm_applicable: bool | None = None
    payment_terms: str | None = None
    reliability_score: float | None = None
    whatsapp_opt_in: bool | None = None
    email_opt_in: bool | None = None
    consent_date: date | None = None


class VendorOut(BaseModel):
    id: uuid.UUID
    name: str
    city: str | None
    category: str | None
    contact_name: str | None
    phone: str | None
    email: str | None
    gstin: str | None
    rcm_applicable: bool
    payment_terms: str | None
    reliability_score: float | None
    whatsapp_opt_in: bool
    email_opt_in: bool
    consent_date: date | None

    model_config = ConfigDict(from_attributes=True)


@vendors_router.post("", response_model=VendorOut, status_code=201)
def create_vendor(
    payload: VendorCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*PROCUREMENT_ROLES)),
):
    vendor = Vendor(**payload.model_dump())
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor


@vendors_router.get("", response_model=list[VendorOut])
def list_vendors(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*PROCUREMENT_ROLES)),
):
    return db.query(Vendor).order_by(Vendor.name).all()


@vendors_router.get("/{vendor_id}", response_model=VendorOut)
def get_vendor(
    vendor_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*PROCUREMENT_ROLES)),
):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor


@vendors_router.patch("/{vendor_id}", response_model=VendorOut)
def update_vendor(
    vendor_id: uuid.UUID,
    payload: VendorUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*PROCUREMENT_ROLES)),
):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(vendor, field, value)
    db.commit()
    db.refresh(vendor)
    return vendor
