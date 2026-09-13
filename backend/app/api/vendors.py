import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.product import Product
from app.models.vendor import Vendor

vendors_router = APIRouter(prefix="/vendors", tags=["vendors"])
# Separate top-level router (not nested under /vendors) for by-id product
# operations -- /vendors/{vendor_id} (GET/PATCH) is a single-path-segment
# pattern that would otherwise shadow /vendors/products/{id} in Starlette's
# registration-order route matching ("products" parses as {vendor_id}
# before ever reaching the product route).
products_router = APIRouter(prefix="/products", tags=["products"])

# M.4: "Edit consumption sheet, raise RFQ / PO" -- Sales/Site Engineer/CA
# have no reason to see vendor relationships or pricing.
PROCUREMENT_ROLES = ("pm", "director", "procurement")


class VendorCreate(BaseModel):
    name: str
    vendor_code: str | None = None
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
    vendor_code: str | None = None
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
    vendor_code: str | None
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


# ---------------------------------------------------------------------------
# Amendment 7: Products -- "products with approximate pricing under each
# vendor." Nested under a vendor for create/list (a product always belongs
# to exactly one vendor); update/delete address the product directly since
# its vendor never changes after creation.
# ---------------------------------------------------------------------------


class ProductCreate(BaseModel):
    name: str
    spec: str | None = None
    unit: str | None = None
    approx_price: float | None = None
    category: str | None = None
    notes: str | None = None


class ProductUpdate(BaseModel):
    name: str | None = None
    spec: str | None = None
    unit: str | None = None
    approx_price: float | None = None
    category: str | None = None
    notes: str | None = None


class ProductOut(BaseModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    name: str
    spec: str | None
    unit: str | None
    approx_price: float | None
    category: str | None
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


@vendors_router.post("/{vendor_id}/products", response_model=ProductOut, status_code=201)
def create_product(
    vendor_id: uuid.UUID,
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*PROCUREMENT_ROLES)),
):
    if not db.query(Vendor).filter(Vendor.id == vendor_id).first():
        raise HTTPException(status_code=404, detail="Vendor not found")
    product = Product(vendor_id=vendor_id, **payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@vendors_router.get("/{vendor_id}/products", response_model=list[ProductOut])
def list_products(
    vendor_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*PROCUREMENT_ROLES)),
):
    if not db.query(Vendor).filter(Vendor.id == vendor_id).first():
        raise HTTPException(status_code=404, detail="Vendor not found")
    return db.query(Product).filter(Product.vendor_id == vendor_id).order_by(Product.name).all()


@products_router.patch("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*PROCUREMENT_ROLES)),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@products_router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*PROCUREMENT_ROLES)),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
