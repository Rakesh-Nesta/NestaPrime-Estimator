import hashlib
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import get_current_user, require_roles
from app.db.session import get_db
from app.models.company_logo import CompanyLogo

router = APIRouter(prefix="/company", tags=["company"])

# Q.1: COMPANY's other fields (legal name, PAN, GSTIN, bank details) are
# Director-only Master Settings -- the logo follows the same rule.
WRITE_ROLES = ("director",)

# R.0: "Logo (SVG/PNG) ... for PDF." Only these two -- an arbitrary image
# format isn't something reportlab's own Image flowable (PDF rendering,
# M.6/pdf_documents.py) can always embed reliably, and PNG/SVG are the
# two the blueprint itself names.
ALLOWED_CONTENT_TYPES = {"image/png": ".png", "image/svg+xml": ".svg"}
MAX_LOGO_SIZE_BYTES = 5 * 1024 * 1024  # a company logo has no business being larger than this


def _logo_storage_dir() -> Path:
    path = Path(settings.attachment_storage_root) / "company_logo"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_current_company_logo(db: Session) -> CompanyLogo | None:
    """The single CURRENT logo -- most recent upload by uploaded_at.
    Exported for pdf_documents.py to embed in the Estimate/Quotation
    header."""
    return db.query(CompanyLogo).order_by(CompanyLogo.uploaded_at.desc()).first()


class CompanyLogoOut(BaseModel):
    id: uuid.UUID
    original_filename: str
    content_type: str
    uploaded_by_id: uuid.UUID
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("/logo/meta", response_model=CompanyLogoOut)
def get_company_logo_meta(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    logo = get_current_company_logo(db)
    if logo is None:
        raise HTTPException(status_code=404, detail="No company logo has been uploaded yet")
    return logo


@router.get("/logo")
def download_company_logo(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Streams the current logo file -- used directly as an <img src>
    by the frontend, and read from disk by pdf_documents.py for the PDF
    header (same storage_path, no duplicate copy)."""
    logo = get_current_company_logo(db)
    if logo is None:
        raise HTTPException(status_code=404, detail="No company logo has been uploaded yet")
    path = Path(logo.storage_path)
    if not path.exists():
        raise HTTPException(status_code=410, detail="Stored logo file is missing from disk")
    return FileResponse(path, media_type=logo.content_type, filename=logo.original_filename)


@router.post("/logo", response_model=CompanyLogoOut, status_code=201)
async def upload_company_logo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """M.3's own 'no overwrite, no delete' discipline: this always
    inserts a new row (and a new file on disk) rather than mutating the
    previous logo -- the most recent upload becomes current, but who
    uploaded what and when stays in the audit trail."""
    content_type = file.content_type or ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Logo must be PNG or SVG (R.0) -- got '{content_type or 'unknown'}'",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Empty file")
    if len(content) > MAX_LOGO_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Logo exceeds the 5 MB limit")

    sha256 = hashlib.sha256(content).hexdigest()
    original_filename = file.filename or f"logo{ALLOWED_CONTENT_TYPES[content_type]}"
    dest = _logo_storage_dir() / f"{uuid.uuid4()}{ALLOWED_CONTENT_TYPES[content_type]}"
    dest.write_bytes(content)

    logo = CompanyLogo(
        original_filename=original_filename,
        original_sha256=sha256,
        storage_path=str(dest),
        content_type=content_type,
        uploaded_by_id=current_user.id,
    )
    db.add(logo)
    db.commit()
    db.refresh(logo)
    return logo
