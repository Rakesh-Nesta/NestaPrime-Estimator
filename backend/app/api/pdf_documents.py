"""Part M.6: client-facing Estimate and Formal Quotation PDFs.

Everything printed here is either a live read of an existing table (M.6's
own principle for every other document in the app) or, where the
blueprint gives no computed data at all, the exact starter text the
blueprint itself provides for that gap (Appendix B's T&C, the warranty
*basis* -- manufacturer-backed vs NestaPrime workmanship -- with no
fabricated year figures the blueprint never states). K.3 applies here as
everywhere else: neither PDF ever prints cost, margin or floor -- the
Quotation PDF only ever uses selling_after_discount/gst_amount/
quotation_total, all already GST-inclusive, client-facing numbers.
"""

import functools
import io
import json
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.api.company import get_current_company_logo
from app.api.documents import DOCUMENT_ROLES
from app.api.schedule import get_schedule
from app.api.settings import get_current_setting_value
from app.api.sports import _dimension_deviations, _worst_deviation_status
from app.core import ownership, upload_validators
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.attachment import Attachment, AttachmentTag
from app.models.client import Client, ClientType
from app.models.document import (
    CostSheetLine,
    Estimate,
    EstimateOption,
    EstimateStatus,
    Quotation,
    QuotationLine,
    QuotationStatus,
    WorkPackage,
)
from app.models.package_content import PackageContent
from app.models.pdf_image_exclusion import PdfImageExclusion
from app.models.project import Project
from app.models.scope_item import ProjectScopeItem, ScopeItem
from app.models.setting import DocumentType
from app.models.sport import ProjectSport, Sport
from app.pdf_utils import amount_in_words_inr, format_inr, round_to_nearest_10
from app.services import quotation_content

pdf_documents_router = APIRouter(tags=["pdf-documents"])

# Appendix B, condensed to printable clauses -- this project's own
# blueprint text, reproduced as the "starter T&C" it explicitly names
# itself, not third-party content. The jurisdiction clause's city is
# built separately by _starter_terms() below (Q.1/Part O: COMPANY's
# registered-office city is Director-configurable, not a fixed string).
_STARTER_TERMS_FIXED = [
    "Validity: 30 days from the date of this quotation.",
    "Payment: as per the payment schedule below, tied to the delivery milestones.",
    "Delivery timeline: as per the schedule below, from advance receipt and site handover.",
    "Warranty: coverage per item as per the warranty table below (manufacturer-backed for "
    "turf/flooring/lighting, NestaPrime workmanship for structure and civil); excludes misuse, "
    "vandalism, unauthorised repair, lack of specified maintenance (AMC or logged maintenance), "
    "flooding, fire, and Acts of God. Claims by written notice with photos; inspection within 7 "
    "working days; repair or replace at NestaPrime's option. A warranty reserve of 1% of the "
    "contract value is held internally.",
    "Client to provide clear site access, power and water for the works.",
    "Variations to the scope are charged at the unit rates quoted here.",
    "Force majeure: flood, earthquake, cyclone, fire, epidemic/pandemic, war, riot, strike, "
    "government order or lockdown, or other event beyond reasonable control. The affected party "
    "notifies within 7 days; time is extended by the duration; neither party is liable for the "
    "delay; either may terminate after 90 continuous days.",
    "Taxes: GST at the rate applicable on the date of invoice; any statutory change after the "
    "quotation date is to the client's account. GST on advances is payable on receipt.",
]


# Amendment 2 (Annexure 2): the Quick setup form's own field-by-field spec
# table (docs/annexures/Amendments-2-4-9-specs.md) names the exact wording
# each hidden field's default should carry onto the client-facing document
# -- reproduced here verbatim rather than re-derived, so the PDF always
# says the same thing the spec promised it would.
_QUICK_SETUP_ASSUMPTION_TERMS = [
    "Site address to be confirmed before survey.",
    "Distance-based logistics costed at actuals.",
    "Site assumed level pending physical survey.",
    "Soil test required before construction if site conditions differ (D.4).",
    "Site access assumed unrestricted; narrow-road/no-crane surcharge applies if not.",
    "Power and water assumed available on site.",
]


QUOTATION_TERMS_SETTING_KEY = "quotation_terms_and_conditions"
QUOTATION_WARRANTY_TABLE_SETTING_KEY = "quotation_warranty_table"


def _current_quotation_terms(db: Session) -> list[str]:
    """Section 14: the 8 T&C clauses below become Director-editable via
    Master Settings, stored as a JSON list under QUOTATION_TERMS_SETTING_KEY
    -- unset is not the same as "no terms," it's "no override yet," so an
    unconfigured or unparseable value falls back to today's exact wording
    rather than printing nothing."""
    raw = get_current_setting_value(db, QUOTATION_TERMS_SETTING_KEY)
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list) and all(isinstance(t, str) for t in parsed):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return list(_STARTER_TERMS_FIXED)


def _current_warranty_table(db: Session) -> list[tuple[str, str]]:
    """Section 14: same override pattern as _current_quotation_terms, for
    the item/basis warranty table."""
    raw = get_current_setting_value(db, QUOTATION_WARRANTY_TABLE_SETTING_KEY)
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list) and all(isinstance(row, list) and len(row) == 2 for row in parsed):
                return [(row[0], row[1]) for row in parsed]
        except (json.JSONDecodeError, TypeError):
            pass
    return list(WARRANTY_TABLE)


def _starter_terms(
    db: Session,
    tender_mode: bool = False,
    quick_setup: bool = False,
    terms_override: list[str] | None = None,
) -> list[str]:
    """Appendix B's jurisdiction clause names 'NestaPrime's registered
    office city' -- Part O's COMPANY master carries that city as a real
    field, not a fixed string, so it's substituted in here whenever a
    Director has actually configured company_registered_office_city;
    otherwise the clause falls back to the same generic wording Appendix
    B itself uses, rather than fabricating a city. K.1 4A/4B are mutually
    exclusive (never both), so a Tender Mode document's own internally-
    held reserve is the DLP reserve, not the private-client warranty
    reserve -- the fixed warranty clause's last sentence is swapped
    accordingly rather than printing a reserve that was never actually
    held for this document.

    quick_setup appends the blind-quoting assumption clauses (Amendment 2)
    for a project created through the 5-field Quick setup form -- every
    field that form didn't ask for was filled with a stated assumption
    rather than a real site fact, and that assumption has to reach the
    client on the document the price is actually quoted on, not just
    live invisibly in the database."""
    terms = list(terms_override) if terms_override is not None else _current_quotation_terms(db)
    # Index 3 is only "the warranty clause" for today's own fixed wording --
    # if a Director has edited the terms via Section 14, this best-effort
    # substitution simply does nothing when its exact source text no longer
    # matches, rather than raising on an IndexError or a bad guess.
    if tender_mode and len(terms) > 3:
        terms[3] = terms[3].replace(
            "A warranty reserve of 1% of the contract value is held internally.",
            "A DLP (defect-liability period) reserve of 1% of the contract value is held internally "
            "(Tender Mode; Part L).",
        )
    city = get_current_setting_value(db, "company_registered_office_city")
    jurisdiction = (
        f"Jurisdiction: courts at {city}; disputes above Rs 25 L go to arbitration under the "
        "Arbitration and Conciliation Act 1996 with a sole arbitrator."
        if city
        else "Jurisdiction: courts at NestaPrime's registered office city; disputes above Rs 25 L go to "
        "arbitration under the Arbitration and Conciliation Act 1996 with a sole arbitrator."
    )
    result = [*terms, jurisdiction]
    if quick_setup:
        result.append(
            "This quotation was prepared from a simplified (Quick) setup -- the following site "
            "details were assumed rather than surveyed:"
        )
        result.extend(_QUICK_SETUP_ASSUMPTION_TERMS)
    return result


WARRANTY_TABLE = [
    ("Flooring / turf", "Manufacturer-backed"),
    ("Lighting fixtures", "Manufacturer-backed"),
    ("MS structure & civil", "NestaPrime workmanship"),
    ("Pool equipment", "Manufacturer-backed"),
    ("Gym equipment", "Manufacturer-backed"),
]

# B.2's own worked example is the only warranty DURATION the blueprint
# gives for any client type: "Client = School -> ... Warranty 5 yr."
# Every other client type has no figure anywhere in the document, so
# none is fabricated here -- _warranty_years returns None for them
# until a Director actually configures warranty_years_<client_type>.
WARRANTY_YEARS_DEFAULT: dict[ClientType, int] = {ClientType.SCHOOL: 5}


def _warranty_years(db: Session, client_type: ClientType | None) -> int | None:
    if client_type is None:
        return None
    value = get_current_setting_value(db, f"warranty_years_{client_type.value}")
    if value is not None:
        return int(float(value))
    return WARRANTY_YEARS_DEFAULT.get(client_type)


# Part O COMPANY master: "NestaPrime legal name, PAN, bank details, logo,
# e-invoice applicable flag, turnover band." No admin UI/table is built
# for this (it's a handful of Director-set values for a single-tenant
# app, not a multi-row master), so each field is a plain Master Setting
# -- Director sets it once via the generic /settings endpoint, same
# mechanism every other Q.1 constant in this app already uses.
_COMPANY_SETTING_FIELDS: list[tuple[str, str]] = [
    ("company_legal_name", "Registered as"),
    ("company_pan", "PAN"),
    ("company_gstin", "GSTIN"),
    ("company_bank_name", "Bank"),
    ("company_bank_account_name", "Account name"),
    ("company_bank_account_number", "Account no."),
    ("company_bank_ifsc", "IFSC"),
]
_COMPANY_IDENTITY_KEYS = {"company_legal_name", "company_pan", "company_gstin"}
_COMPANY_BANK_KEYS = {"company_bank_name", "company_bank_account_name", "company_bank_account_number", "company_bank_ifsc"}


def _company_details_lines(db: Session, keys: set[str] | None = None) -> list[str]:
    """R.0 checklist: 'Logo (SVG/PNG), company details, GSTIN, bank
    details for PDF | High.' None of this was printed anywhere before --
    not hardcoded wrong, simply absent. Blank/unconfigured fields are
    skipped rather than printed as '[confirm]' noise; a Director who
    hasn't set any of these yet sees the same PDF as before this change."""
    lines = []
    for key, label in _COMPANY_SETTING_FIELDS:
        if keys is not None and key not in keys:
            continue
        value = get_current_setting_value(db, key)
        if value:
            lines.append(f"<b>{label}:</b> {value}")
    return lines


def _get_estimate(db: Session, estimate_id: uuid.UUID) -> Estimate:
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    return estimate


# --- memory budget for images embedded in generated PDFs ------------------------------------------------------------
# Generated PDFs decode every embedded image in full. Measured on a development machine (NOT the server, no load test):
# ~13 MB of peak memory per megapixel, e.g. 12 Mpx = 180 MB / 2.5 s, 50 Mpx = 0.7 GB / 11 s. The intended server is a 2 GB
# Lightsail instance that also runs Postgres, with 2 gunicorn workers (Dockerfile), so the limits below are PROVISIONAL and
# were chosen against that: one build at a time per worker x 24 Mpx per document = ~0.3 GB per worker, ~0.6 GB for both.
# Change them if the server's memory or worker count changes.
MAX_EMBED_PIXELS = 16_000_000  # per image; larger stored images are left out of the PDF (graceful skip, like a corrupt one)
MAX_PDF_IMAGE_PIXELS = 24_000_000  # per document, summed over every embedded image
PDF_BUILD_WAIT_SECONDS = 30  # a request waits this long for the worker's single build slot, then gets 503
MAX_PDF_BUILD_WAITERS = 4  # further requests are refused at once (503): waiting threads would otherwise tie up the thread pool
# SCOPE: these two semaphores are per PROCESS. The deployment is one `backend` container (docker-compose.prod.yml, no
# replicas) running 2 gunicorn workers (Dockerfile) => at most 2 builds at once machine-wide. Adding workers or replicas
# multiplies the worst-case memory: re-derive the budget above if either changes.
_PDF_BUILD_SLOT = threading.BoundedSemaphore(1)  # per worker process: only one PDF build decodes images at a time
_PDF_BUILD_WAITERS = threading.BoundedSemaphore(MAX_PDF_BUILD_WAITERS)

# bytes per pixel once decoded, relative to 8-bit RGB (3): the budget counts DECODED size, not just pixel count
_BYTES_PER_PIXEL = {"1": 0.125, "L": 1, "P": 1, "LA": 2, "RGB": 3, "YCbCr": 3, "LAB": 3, "HSV": 3, "RGBA": 4, "CMYK": 4,
                    "I": 4, "F": 4, "I;16": 2}


class _PixelBudget:
    def __init__(self, total: int | None = None):
        self.remaining = MAX_PDF_IMAGE_PIXELS if total is None else total

    def take(self, pixels: int) -> bool:
        if pixels > self.remaining:
            return False
        self.remaining -= pixels
        return True


def _decoded_cost(pil_image) -> int:
    """RGB-equivalent pixels: width x height x (bytes per pixel / 3), so an RGBA or CMYK image counts a third more than the
    same-sized RGB one and a 32-bit float image counts as much as it really occupies. Computed from the header alone."""
    bytes_per_pixel = _BYTES_PER_PIXEL.get(pil_image.mode, 4)
    return int(pil_image.width * pil_image.height * bytes_per_pixel / 3)


def _within_embed_budget(pil_image, budget: "_PixelBudget | None" = None) -> bool:
    """True when this image may be decoded into the PDF: within the per-image ceiling AND the document's remaining budget,
    both measured in RGB-equivalent pixels from the image HEADER -- called before any pixel data is loaded, so nothing
    large is allocated for an image that is then refused. Images stored before the upload ceiling existed can exceed
    either, so an over-budget image is left out (the same graceful skip as a corrupt one) rather than decoded."""
    cost = _decoded_cost(pil_image)
    if cost > MAX_EMBED_PIXELS:
        return False
    return budget.take(cost) if budget is not None else True


def _one_pdf_build_at_a_time(builder):
    """Serialise PDF builds within a worker so concurrent requests cannot decode images at the same time (threads in one
    worker would otherwise stack their memory). A request that cannot get the slot in time is told to retry (503)."""
    @functools.wraps(builder)
    def wrapper(*args, **kwargs):
        busy = HTTPException(
            status_code=503, headers={"Retry-After": "5"},
            detail={"code": "pdf_busy", "message": "PDF generation is busy. Please retry shortly."},
        )
        # Only a few requests may WAIT for the slot (each waiter holds a pool thread); the rest are refused immediately.
        if not _PDF_BUILD_WAITERS.acquire(blocking=False):
            raise busy
        try:
            got_slot = _PDF_BUILD_SLOT.acquire(timeout=PDF_BUILD_WAIT_SECONDS)
        finally:
            _PDF_BUILD_WAITERS.release()
        if not got_slot:
            raise busy
        try:  # the slot is held BEFORE the builder runs, i.e. before any image is opened or decoded
            return builder(*args, **kwargs)
        finally:
            _PDF_BUILD_SLOT.release()

    return wrapper


# --- which images a generated PDF contains, and why any are left out ------------------------------------------------
# A selected image that cannot be embedded is NEVER dropped silently: generation (and therefore a direct API call, a
# download and a send alike) refuses with a structured 409 listing each excluded image and the reason, until the user
# resolves it -- replace the image, or explicitly remove it from THIS document (a PdfImageExclusion record; the
# Attachment itself is never touched). The read-only /pdf-check endpoints preview the same decision, but only the
# generation path enforces it, so a stale preview can never let an omission through.

_REASON_TEXT = {
    "over_image_budget": "is too large to embed in a generated PDF",
    "over_document_budget": "would push this document's total image size over the limit",
    "unreadable": "could not be read as an image",
    "file_missing": "is missing from storage",
    "removed_by_user": "was removed from this document by a user",
}


@dataclass
class ImageExclusion:
    attachment_id: str
    filename: str
    tag: str
    reason: str
    message: str
    user_removed: bool = False
    exclusion_id: str | None = None

    def as_dict(self) -> dict:
        return {
            "attachment_id": self.attachment_id, "filename": self.filename, "tag": self.tag, "reason": self.reason,
            "message": self.message, "user_removed": self.user_removed, "exclusion_id": self.exclusion_id,
        }


class _ImagePlan:
    """Per-document record of the decisions made about each selected image."""

    def __init__(self, db: Session, doc_type: DocumentType, doc_id: uuid.UUID):
        self.doc_type = doc_type
        self.doc_id = doc_id
        self.budget = _PixelBudget()
        self.exclusions: list[ImageExclusion] = []
        self.included = 0
        self.removed = {
            row.attachment_id: row
            for row in db.query(PdfImageExclusion).filter(
                PdfImageExclusion.doc_type == doc_type.value, PdfImageExclusion.doc_id == doc_id
            )
        }

    def admit(self, pil_image) -> str | None:
        """None when the image fits, else the reason. Header-only: nothing has been decoded yet."""
        cost = _decoded_cost(pil_image)
        if cost > MAX_EMBED_PIXELS:
            return "over_image_budget"
        if not self.budget.take(cost):
            return "over_document_budget"
        return None

    def add(self, attachment: Attachment, reason: str) -> None:
        removal = self.removed.get(attachment.id)
        self.exclusions.append(ImageExclusion(
            attachment_id=str(attachment.id), filename=attachment.original_filename, tag=attachment.tag.value,
            reason=reason, message=f"{attachment.original_filename} {_REASON_TEXT[reason]}",
            user_removed=reason == "removed_by_user", exclusion_id=str(removal.id) if removal else None,
        ))

    @property
    def blocking(self) -> list[ImageExclusion]:
        return [e for e in self.exclusions if not e.user_removed]

    def raise_if_blocked(self) -> None:
        if self.blocking:
            raise HTTPException(status_code=409, detail=self.blocked_detail())

    def blocked_detail(self) -> dict:
        return {
            "code": "pdf_images_excluded",
            "message": "This document cannot be generated yet: some of its selected images cannot be included. "
                       "Replace each image, or remove it from this document, then try again.",
            "excluded": [e.as_dict() for e in self.blocking],
        }


def _latest_product_image(db: Session, option_id: uuid.UUID):
    return (
        db.query(Attachment)
        .filter(
            Attachment.doc_type == DocumentType.ESTIMATE_OPTION,
            Attachment.doc_id == option_id,
            Attachment.tag == AttachmentTag.PRODUCT_IMAGE,
            Attachment.superseded_by_id.is_(None),
        )
        .order_by(Attachment.uploaded_at.desc())
        .first()
    )


def _quotation_photos(db: Session, quotation_id: uuid.UUID) -> list:
    return (
        db.query(Attachment)
        .filter(
            Attachment.doc_type == DocumentType.QUOTATION,
            Attachment.doc_id == quotation_id,
            Attachment.tag == AttachmentTag.PHOTO,
            Attachment.superseded_by_id.is_(None),
        )
        .order_by(Attachment.uploaded_at.asc())
        .all()
    )


def _selected_images(db: Session, doc_type: DocumentType, doc_id: uuid.UUID) -> list:
    """The images a document of this type would try to embed -- ONE definition shared by the builders, the preview and the
    exclusion endpoint, so they cannot drift apart."""
    if doc_type == DocumentType.ESTIMATE:
        options = db.query(EstimateOption).filter(EstimateOption.estimate_id == doc_id).all()
        return [image for option in options if (image := _latest_product_image(db, option.id)) is not None]
    if doc_type == DocumentType.QUOTATION:
        return _quotation_photos(db, doc_id)
    return []


def _evaluate_image(plan: "_ImagePlan", attachment: Attachment, full: bool) -> bool:
    """True when the image may be embedded; otherwise the reason is recorded on the plan. full=True (generation) decodes the
    image, so a corrupt one is found here; full=False (preview) applies the same header-level budget and the cheap, bounded
    upload validators instead of a full decode."""
    if attachment.id in plan.removed:
        plan.add(attachment, "removed_by_user")
        return False
    path = Path(attachment.storage_path)
    if not path.exists():
        plan.add(attachment, "file_missing")
        return False
    try:
        with PILImage.open(path) as pil_image:
            reason = plan.admit(pil_image)  # from the header, before any pixel data is loaded
            if reason:
                plan.add(attachment, reason)
                return False
            if full:
                pil_image.load()
        if not full:
            extension = path.suffix.lower()
            if extension in upload_validators.VALIDATORS:
                upload_validators.VALIDATORS[extension](path)
    except Exception:  # noqa: BLE001 - anything unreadable is reported, never swallowed
        plan.add(attachment, "unreadable")
        return False
    return True


def _scaled_image(path: Path, max_width: float, max_height: float):
    reader = ImageReader(str(path))
    original_width, original_height = reader.getSize()
    scale = min(max_width / original_width, max_height / original_height)
    return Image(str(path), width=original_width * scale, height=original_height * scale)


def _product_image_flowable(db: Session, option_id: uuid.UUID, max_width: float, max_height: float, plan: "_ImagePlan"):
    """M.6: 'product options table (Budget/Standard/Premium with images).' The latest non-superseded product_image on this
    specific option, scaled to fit while preserving the aspect ratio. A row with NO upload simply has no picture; an image
    that exists but cannot be embedded is recorded on the plan (and blocks generation) -- never silently dropped."""
    attachment = _latest_product_image(db, option_id)
    if attachment is None:
        return ""
    if not _evaluate_image(plan, attachment, full=True):
        return ""
    try:
        flowable = _scaled_image(Path(attachment.storage_path), max_width, max_height)
    except Exception:  # noqa: BLE001
        plan.add(attachment, "unreadable")
        return ""
    plan.included += 1
    return flowable


def _quotation_photo_flowables(db: Session, quotation_id: uuid.UUID, max_width: float, max_height: float, plan: "_ImagePlan") -> list:
    """Every non-superseded photo-tagged attachment on this Quotation (a site layout, a 3D render ...). Same rule as above:
    each one is embedded, explicitly removed by a user for this document, or recorded as an exclusion that blocks generation."""
    flowables: list = []
    for attachment in _quotation_photos(db, quotation_id):
        if not _evaluate_image(plan, attachment, full=True):
            continue
        try:
            flowables.append(_scaled_image(Path(attachment.storage_path), max_width, max_height))
            flowables.append(Spacer(1, 3 * mm))
        except Exception:  # noqa: BLE001
            plan.add(attachment, "unreadable")
            continue
        plan.included += 1
    return flowables


def _company_logo_flowable(db: Session, max_width: float, max_height: float, budget: "_PixelBudget | None" = None):
    """R.0: 'Logo (SVG/PNG) ... for PDF.' Only a PNG logo can actually be
    embedded here -- reportlab's Image flowable (and the Pillow decode
    it relies on, same as _product_image_flowable above) has no native
    SVG rasteriser, and this app carries no separate SVG-to-raster
    dependency. An uploaded SVG logo still downloads fine from
    GET /company/logo for on-screen use; the PDF header just falls back
    to the plain text company name for that format, same as when no
    logo has been uploaded at all -- never a broken/blank image."""
    logo = get_current_company_logo(db)
    if logo is None or logo.content_type != "image/png":
        return None
    path = Path(logo.storage_path)
    if not path.exists():
        return None
    try:
        with PILImage.open(path) as pil_image:
            if not _within_embed_budget(pil_image, budget):  # a 5 MB PNG can still decode to gigabytes
                return None
            pil_image.load()
        reader = ImageReader(str(path))
        original_width, original_height = reader.getSize()
        scale = min(max_width / original_width, max_height / original_height)
        return Image(str(path), width=original_width * scale, height=original_height * scale)
    except Exception:
        return None


_DEVIATION_COLOR = {"green": "green", "amber": "#b45309", "red": "red"}


def _standard_vs_actual_row(db: Session, styles, sport: Sport, project_sport: ProjectSport) -> list:
    """M.6: 'sport(s), dimensions standard vs actual with citation' on both
    the Estimate and Quotation PDF. C.3's deviation_thresholds (amber/red)
    only mean anything once an actual figure has been recorded -- before
    that this honestly prints 'Not yet recorded' rather than the old
    placeholder behaviour of quietly repeating the standard figure as if
    it were a real as-built measurement."""
    citation = f" ({sport.source_citation})" if sport.source_citation else ""
    standard_text = f"{sport.playing_dims} ft{citation}"
    if project_sport.actual_l_ft is None and project_sport.actual_w_ft is None:
        return [sport.name, standard_text, "Not yet recorded"]

    actual_l = project_sport.actual_l_ft if project_sport.actual_l_ft is not None else "-"
    actual_w = project_sport.actual_w_ft if project_sport.actual_w_ft is not None else "-"
    actual_text = f"{actual_l} x {actual_w} ft"
    deviations = _dimension_deviations(db, sport, project_sport)
    status = _worst_deviation_status(deviations)
    if status:
        worst_pct = max(d.deviation_percent for d in deviations)
        actual_text += f'<br/><font color="{_DEVIATION_COLOR[status]}">{status.upper()} ({worst_pct}% deviation)</font>'
    return [sport.name, standard_text, Paragraph(actual_text, styles["Normal"])]


def _get_quotation(db: Session, quotation_id: uuid.UUID) -> Quotation:
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return quotation


def _inclusions_and_exclusions(db: Session, project_id: uuid.UUID) -> tuple[list[str], list[str]]:
    """Part I: 'unchecked = excluded and listed under Exclusions' -- a
    project-specific, real read of Module 10's own checklist, not
    boilerplate."""
    all_items = db.query(ScopeItem).order_by(ScopeItem.display_order).all()
    included = db.query(ProjectScopeItem).filter(ProjectScopeItem.project_id == project_id).all()
    included_by_scope_item_id = {row.scope_item_id: row for row in included}

    inclusions, exclusions = [], []
    for item in all_items:
        row = included_by_scope_item_id.get(item.id)
        if row:
            label = item.name if not row.note else f"{item.name} ({row.note})"
            inclusions.append(label)
        else:
            exclusions.append(item.name)
    return inclusions, exclusions


def _pdf_response(buffer: io.BytesIO, filename: str) -> StreamingResponse:
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CompanyHeader", parent=styles["Title"], alignment=TA_CENTER, fontSize=16))
    styles.add(ParagraphStyle(name="DocTitle", parent=styles["Heading1"], alignment=TA_CENTER, fontSize=13))
    styles.add(ParagraphStyle(name="SectionHeading", parent=styles["Heading2"], fontSize=11, spaceBefore=10))
    return styles


_TABLE_GRID = TableStyle(
    [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
)


def _client_block(styles, client: Client, project: Project) -> list:
    lines = [f"<b>Client:</b> {client.name}"]
    if client.contact_name:
        lines.append(f"<b>Contact:</b> {client.contact_name}")
    if client.phone:
        lines.append(f"<b>Phone:</b> {client.phone}")
    if client.email:
        lines.append(f"<b>Email:</b> {client.email}")
    if client.billing_address:
        lines.append(f"<b>Address:</b> {client.billing_address}")
    if client.gstin:
        lines.append(f"<b>GSTIN:</b> {client.gstin}")
    lines.append(f"<b>Site:</b> {project.site_address or project.city}")
    return [Paragraph(line, styles["Normal"]) for line in lines]


def _exclusions_flow(styles, exclusions: list[str]) -> list:
    if not exclusions:
        return [Paragraph("None -- full Part I scope checklist is included.", styles["Normal"])]
    return [Paragraph("&bull; " + item, styles["Normal"]) for item in exclusions]


def _package_content_flow(db: Session, styles, sport: Sport, option: EstimateOption) -> list:
    """Part O PACKAGES / M.6: what a Budget/Standard/Premium option
    actually contains -- flooring, structure, lighting, scope and
    warranty, as the Director has set them for this sport+tier (Q.1).
    Falls back to an honest 'not yet configured' line rather than
    fabricating content the Director hasn't entered, same convention as
    _warranty_years() below when no client-type warranty duration is
    set."""
    content = (
        db.query(PackageContent)
        .filter(PackageContent.sport_id == sport.id, PackageContent.tier == option.package)
        .first()
    )
    heading = f"{sport.name} -- {option.package.value.capitalize()}"
    if content is None:
        return [
            Paragraph(f"<b>{heading}</b>", styles["Normal"]),
            Paragraph("Package content not yet configured (Q.1 Master Settings).", styles["Normal"]),
        ]
    flow = [
        Paragraph(f"<b>{heading}</b>", styles["Normal"]),
        Paragraph(f"<b>Flooring:</b> {content.flooring_description}", styles["Normal"]),
        Paragraph(f"<b>Structure:</b> {content.structure_description}", styles["Normal"]),
        Paragraph(f"<b>Lighting:</b> {content.lighting_description}", styles["Normal"]),
    ]
    flow.extend(
        Paragraph("&bull; " + line.strip(), styles["Normal"])
        for line in content.scope_description.splitlines()
        if line.strip()
    )
    if content.warranty_years is not None:
        flow.append(Paragraph(f"<b>Warranty:</b> {content.warranty_years} year(s)", styles["Normal"]))
    return flow


# ---------------------------------------------------------------------------
# Estimate PDF
# ---------------------------------------------------------------------------


@_one_pdf_build_at_a_time
def build_estimate_pdf(db: Session, estimate_id: uuid.UUID) -> tuple[io.BytesIO, str]:
    """Amendment 8 (Section 8): factored out of the route below so
    app/api/messages.py can attach the same PDF to a WhatsApp/Telegram
    send without a second, divergent copy of this layout."""
    estimate = _get_estimate(db, estimate_id)
    plan = _ImagePlan(db, DocumentType.ESTIMATE, estimate_id)
    project = db.query(Project).filter(Project.id == estimate.project_id).first()
    client = db.query(Client).filter(Client.id == project.client_id).first()
    options = db.query(EstimateOption).filter(EstimateOption.estimate_id == estimate_id).all()
    inclusions, exclusions = _inclusions_and_exclusions(db, project.id)

    styles = _styles()
    logo = _company_logo_flowable(db, 45 * mm, 18 * mm, plan.budget)
    story: list = [
        *([logo, Spacer(1, 2 * mm)] if logo else []),
        Paragraph("NESTAPRIME SPORTS INFRASTRUCTURE", styles["CompanyHeader"]),
        Paragraph("ESTIMATE", styles["DocTitle"]),
        Spacer(1, 4 * mm),
        Paragraph(
            f"<b>Estimate No.:</b> {estimate.document_no} &nbsp;&nbsp; "
            f"<b>Date:</b> {(estimate.sent_at or estimate.created_at).date().isoformat()}",
            styles["Normal"],
        ),
        *[Paragraph(line, styles["Normal"]) for line in _company_details_lines(db, _COMPANY_IDENTITY_KEYS)],
        Spacer(1, 3 * mm),
        *_client_block(styles, client, project),
        Spacer(1, 5 * mm),
        Paragraph("Product options", styles["SectionHeading"]),
    ]

    image_col_width, image_col_height = 24 * mm, 18 * mm
    rows = [["Image", "Sport", "Package", "Playing dimensions", "Governing body", "Indicative price (GST-incl.)"]]
    for option in options:
        project_sport = db.query(ProjectSport).filter(ProjectSport.id == option.project_sport_id).first()
        sport = db.query(Sport).filter(Sport.id == project_sport.sport_id).first()
        rows.append(
            [
                _product_image_flowable(db, option.id, image_col_width, image_col_height, plan),
                sport.name,
                option.package.value.capitalize(),
                f"{sport.playing_dims} ft" + (f"\n({sport.source_citation})" if sport.source_citation else ""),
                sport.governing_body,
                f"{format_inr(float(option.price_low))} - {format_inr(float(option.price_high))}",
            ]
        )
    table = Table(rows, colWidths=[26 * mm, 30 * mm, 18 * mm, 38 * mm, 28 * mm, 40 * mm])
    table.setStyle(_TABLE_GRID)
    story.append(table)

    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("Package content", styles["SectionHeading"]))
    for option in options:
        project_sport = db.query(ProjectSport).filter(ProjectSport.id == option.project_sport_id).first()
        sport = db.query(Sport).filter(Sport.id == project_sport.sport_id).first()
        story.extend(_package_content_flow(db, styles, sport, option))
        story.append(Spacer(1, 2 * mm))

    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("Standard vs. actual dimensions", styles["SectionHeading"]))
    dims_rows = [["Sport", "Standard (governing body)", "Actual (as built)"]]
    for option in options:
        project_sport = db.query(ProjectSport).filter(ProjectSport.id == option.project_sport_id).first()
        sport = db.query(Sport).filter(Sport.id == project_sport.sport_id).first()
        dims_rows.append(_standard_vs_actual_row(db, styles, sport, project_sport))
    dims_table = Table(dims_rows, colWidths=[45 * mm, 75 * mm, 55 * mm])
    dims_table.setStyle(_TABLE_GRID)
    story.append(dims_table)

    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("Inclusions (Part I scope)", styles["SectionHeading"]))
    if inclusions:
        story.extend(Paragraph("&bull; " + item, styles["Normal"]) for item in inclusions)
    else:
        story.append(Paragraph("As per NestaPrime standard package specification.", styles["Normal"]))
    story.append(Paragraph("Exclusions", styles["SectionHeading"]))
    story.extend(_exclusions_flow(styles, exclusions))

    validity_note = (
        f"Valid until {(estimate.sent_at.date() if estimate.sent_at else None)} (15 days from sending)."
        if estimate.sent_at
        else "Validity: 15 days from the date this estimate is sent to the client."
    )
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(validity_note, styles["Normal"]))

    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("Approve option: ______________________&nbsp;&nbsp;&nbsp; OR", styles["Normal"]))
    story.append(Paragraph("My requirement: ___________________________________________", styles["Normal"]))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Client signature: _______________________ &nbsp;&nbsp; Date: ____________", styles["Normal"]))

    plan.raise_if_blocked()  # nothing selected is dropped silently: refuse, listing each excluded image
    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm).build(story)
    return buffer, f"{estimate.document_no}.pdf"


@pdf_documents_router.get("/estimates/{estimate_id}/pdf")
def get_estimate_pdf(
    estimate_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    buffer, filename = build_estimate_pdf(db, estimate_id)
    return _pdf_response(buffer, filename)


# ---------------------------------------------------------------------------
# Formal Quotation PDF
# ---------------------------------------------------------------------------


def _scope_of_work_flow(db: Session, styles, sport_rows: list[dict], inclusions: list[str]) -> list:
    """Amendment 54 (Section 58): what is being delivered, in words, with no price
    on any line -- the Director-authored package content for each sport and tier
    (a sport with none is left out, never printed as 'not configured'), then the
    project's Part I inclusions. Empty when there is nothing to show, so the
    heading is omitted too."""
    blocks: list = []
    for row in sport_rows:
        if quotation_content.package_content_for(db, row["sport"], row["option"]) is not None:
            blocks.extend(_package_content_flow(db, styles, row["sport"], row["option"]))
            blocks.append(Spacer(1, 2 * mm))
    if inclusions:
        blocks.append(Paragraph("<b>Included in the scope of work</b>", styles["Normal"]))
        blocks.extend(Paragraph("&bull; " + _xml_escape(item), styles["Normal"]) for item in inclusions)
    if not blocks:
        return []
    return [Paragraph("Scope of work", styles["SectionHeading"]), *blocks]


def _cover_letter_flow(db: Session, styles, quotation: Quotation, project: Project, client: Client, sport_rows: list[dict]) -> list:
    """Amendment 54 (Section 58): the addressee, subject, the saved cover note and a
    sign-off. Printed only when the quotation has a cover note (an unused note
    changes nothing, Amendment 13's promise). Every free-typed value is escaped."""
    flow: list = []
    who = quotation_content.addressee(db, client)
    if who:
        name, designation = who
        text = f"<b>Kind attention:</b> {_xml_escape(name)}" + (f", {_xml_escape(designation)}" if designation else "")
        flow.append(Paragraph(text, styles["Normal"]))
    sport_names = ", ".join(row["sport"].name for row in sport_rows)
    subject = f"Quotation {quotation.document_no}" + (f" -- {sport_names}" if sport_names else "")
    subject += f" at {project.site_address or project.city}"
    flow.append(Paragraph(f"<b>Subject:</b> {_xml_escape(subject)}", styles["Normal"]))
    flow.append(Spacer(1, 3 * mm))
    flow.append(Paragraph(_xml_escape(quotation.cover_note).replace("\n", "<br/>"), styles["Normal"]))
    flow.append(Spacer(1, 3 * mm))
    flow.append(Paragraph("Yours faithfully,", styles["Normal"]))
    flow.append(Paragraph(f"For <b>{_xml_escape(quotation_content.company_name(db))}</b>", styles["Normal"]))
    signatory_name, signatory_designation = quotation_content.signatory_settings(db)
    if signatory_name:
        flow.append(Spacer(1, 6 * mm))
        flow.append(Paragraph(f"<b>{_xml_escape(signatory_name)}</b>", styles["Normal"]))
        if signatory_designation:
            flow.append(Paragraph(_xml_escape(signatory_designation), styles["Normal"]))
    flow.append(Spacer(1, 4 * mm))
    return flow


def _granular_boq_rows_for_sport(
    db: Session, cost_sheet_id: uuid.UUID, project_sport_id: uuid.UUID, sport_ex_gst: float
) -> list[dict] | None:
    """Part L Format row: 'BOQ-style itemised schedule ... instead of
    packages.' Breaks one sport/package's lump-sum BOQ line into one row
    per (work_package, category) group of its own CostSheetLine rows --
    grouped, not per individual line, so a client never sees a PM's raw
    item_name shorthand verbatim and the table reads like a real
    trade-level tender BOQ rather than a full take-off dump (explicit
    choice with the user, 2026-09-10, over a full per-line breakdown).

    Every figure here is a SELLING rate, never the internal cost rate:
    each group's own cost share (qty x cost rate, summed) determines what
    fraction of this sport's already-computed, post-discount, ex-GST
    selling amount (sport_ex_gst) it is apportioned -- the same
    cost-share-apportionment principle the caller already uses to split
    the whole Quotation's selling total across sports (K.3: no client
    document ever contains a cost price or margin).

    Returns None (never []) when this sport has no priced CostSheetLine
    rows to group -- e.g. its Cost Sheet total was entered directly
    rather than built up from lines -- so the caller falls back to a
    single lump-sum row rather than fabricate a breakdown that isn't
    there."""
    lines = (
        db.query(CostSheetLine)
        .filter(
            CostSheetLine.cost_sheet_id == cost_sheet_id,
            CostSheetLine.project_sport_id == project_sport_id,
            CostSheetLine.rate.isnot(None),
        )
        .all()
    )
    sport_line_cost_total = sum(float(line.quantity) * float(line.rate) for line in lines)
    if not lines or sport_line_cost_total <= 0:
        return None

    groups: dict[tuple[str, str], list[CostSheetLine]] = {}
    for line in lines:
        groups.setdefault((line.work_package.value, line.category), []).append(line)

    work_package_order = {wp.value: idx for idx, wp in enumerate(WorkPackage)}
    ordered_keys = sorted(groups.keys(), key=lambda k: (work_package_order[k[0]], k[1]))

    rows = []
    for work_package, category in ordered_keys:
        group_lines = groups[(work_package, category)]
        group_cost = sum(float(line.quantity) * float(line.rate) for line in group_lines)
        group_amount = sport_ex_gst * (group_cost / sport_line_cost_total)
        units = {line.unit for line in group_lines}
        if len(units) == 1:
            unit = units.pop()
            qty = sum(float(line.quantity) for line in group_lines)
            rate = group_amount / qty if qty else group_amount
        else:
            unit, qty, rate = "Lot", 1.0, group_amount
        rows.append({"category": category, "unit": unit, "qty": qty, "rate": rate, "amount": group_amount})
    return rows


@_one_pdf_build_at_a_time
def build_quotation_pdf(
    db: Session,
    quotation_id: uuid.UUID,
    current_user,
    terms_override: list[str] | None = None,
    warranty_table_override: list[tuple[str, str]] | None = None,
) -> tuple[io.BytesIO, str]:
    """Amendment 8 (Section 8): see build_estimate_pdf's own docstring.
    current_user is threaded through to the internal get_schedule() call
    below (called directly as a plain function here, not through
    FastAPI's own dependency injection, so it needs a real value).

    terms_override/warranty_table_override (Section 14): only ever passed
    by the preview endpoint below, to render unsaved draft text against a
    real Quotation's data without writing anything to the database. The
    real download endpoint never passes these -- it always reads whatever
    is currently saved via _current_quotation_terms/_current_warranty_table."""
    plan = _ImagePlan(db, DocumentType.QUOTATION, quotation_id)
    quotation = _get_quotation(db, quotation_id)
    project = db.query(Project).filter(Project.id == quotation.project_id).first()
    client = db.query(Client).filter(Client.id == project.client_id).first()
    estimate = db.query(Estimate).filter(Estimate.id == quotation.estimate_id).first()
    qlines = db.query(QuotationLine).filter(QuotationLine.quotation_id == quotation_id).all()
    inclusions, exclusions = _inclusions_and_exclusions(db, project.id)
    # Amendment 54: the scope of work, the letter block and a warranty table without
    # an invented duration appear only on a quotation not yet sent, never in tender mode.
    enhanced = quotation_content.is_enhanced(quotation, project)

    # Line amounts apportioned pro-rata to each sport's own share of the
    # underlying cost (cost_for_option / cost_total) -- the app prices the
    # whole Quotation as one blended selling price (K.1), not per-sport, so
    # this is a fair, auditable split of that SAME total rather than a
    # second, independent figure.
    cost_total = float(quotation.cost_total)
    selling_ex_gst = float(quotation.selling_after_discount)
    gst_amount = float(quotation.gst_amount)

    sport_rows = []
    for qline in qlines:
        option = db.query(EstimateOption).filter(EstimateOption.id == qline.estimate_option_id).first()
        project_sport = db.query(ProjectSport).filter(ProjectSport.id == option.project_sport_id).first()
        sport = db.query(Sport).filter(Sport.id == project_sport.sport_id).first()
        share = (float(option.cost_for_option) / cost_total) if cost_total else 0.0
        sport_rows.append(
            {
                "sport": sport,
                "project_sport": project_sport,
                "option": option,
                "share": share,
                "ex_gst": selling_ex_gst * share,
                "gst": gst_amount * share,
            }
        )

    styles = _styles()
    doc_title = "FINANCIAL BID (Tender Mode)" if project.tender_mode else "FORMAL QUOTATION"
    logo = _company_logo_flowable(db, 45 * mm, 18 * mm, plan.budget)
    story: list = [
        *([logo, Spacer(1, 2 * mm)] if logo else []),
        Paragraph("NESTAPRIME SPORTS INFRASTRUCTURE", styles["CompanyHeader"]),
        Paragraph(doc_title, styles["DocTitle"]),
        Spacer(1, 4 * mm),
        Paragraph(
            f"<b>Quotation No.:</b> {quotation.document_no} &nbsp;&nbsp; "
            f"<b>Date:</b> {(quotation.sent_at or quotation.created_at).date().isoformat()}",
            styles["Normal"],
        ),
        *[Paragraph(line, styles["Normal"]) for line in _company_details_lines(db, _COMPANY_IDENTITY_KEYS)],
        Spacer(1, 3 * mm),
        *_client_block(styles, client, project),
        Spacer(1, 5 * mm),
    ]

    # Amendment 13 (Section 12): an optional, always human-reviewed
    # introduction paragraph -- additive only, renders nothing when
    # unset, so an unused cover_note changes today's PDF not at all.
    # Escaped for the same reason as project.custom_notes below (genuinely
    # free-typed text, not a derived/enum string).
    if quotation.cover_note and enhanced:
        story.extend(_cover_letter_flow(db, styles, quotation, project, client, sport_rows))
    elif quotation.cover_note:
        cover_note_html = _xml_escape(quotation.cover_note).replace("\n", "<br/>")
        story.append(Paragraph(cover_note_html, styles["Normal"]))
        story.append(Spacer(1, 4 * mm))

    # Reference images (site layout diagrams, 3D renders) uploaded via the
    # Quotation's own Attachments panel -- attaching already worked, but
    # nothing on this screen ever made it into the actual client-facing
    # PDF until now.
    photo_flowables = _quotation_photo_flowables(db, quotation.id, 160 * mm, 100 * mm, plan)
    if photo_flowables:
        story.append(Paragraph("Reference Images", styles["SectionHeading"]))
        story.extend(photo_flowables)
        story.append(Spacer(1, 2 * mm))

    if project.tender_mode:
        # Part L: "BOQ-style itemised schedule (item no., description,
        # unit, qty, rate, amount) instead of packages; DSR/SOR reference
        # column." M.4a: this IS the NPQ Quotation record with a BOQ
        # export applied, not a separate document type -- and K.1 step 9's
        # "discount distributed proportionally into item rates (BOQ rule)"
        # is already what row["ex_gst"] does (it apportions
        # selling_after_discount, i.e. post-discount, by cost share), so
        # no separate discount line is needed here, same as the private-
        # client table below never carries one either.
        #
        # Each sport/package is broken into one BOQ row per work-package/
        # category group of its own CostSheetLine rows (see
        # _granular_boq_rows_for_sport) -- a real, cost-share-apportioned
        # breakdown, not a fully per-line material take-off (that would
        # expose raw PM-entered item_name text to the client; the user
        # chose category-grouped over that on 2026-09-10). A sport with no
        # priced CostSheetLine rows (its Cost Sheet total was entered
        # directly) falls back to a single lump-sum "Lot" line, same as
        # before this change -- never fabricated. There is no DSR/SOR code
        # system in this app, so that column is printed blank for every
        # item rather than fabricated.
        story.append(Paragraph("Bill of Quantities (BOQ)", styles["SectionHeading"]))
        rows = [["Item", "Description", "DSR/SOR ref.", "Unit", "Qty", "Rate (ex-GST)", "Amount (ex-GST)"]]
        idx = 0
        for row in sport_rows:
            sport, option = row["sport"], row["option"]
            package_label = f"{sport.name} ({option.package.value.capitalize()})"
            granular = _granular_boq_rows_for_sport(
                db, estimate.cost_sheet_id, option.project_sport_id, row["ex_gst"]
            )
            if granular:
                for group in granular:
                    idx += 1
                    rows.append(
                        [
                            str(idx),
                            f"{package_label} -- {group['category']}",
                            "--",
                            group["unit"],
                            f"{group['qty']:g}",
                            format_inr(group["rate"]),
                            format_inr(group["amount"]),
                        ]
                    )
            else:
                idx += 1
                rows.append(
                    [
                        str(idx),
                        package_label,
                        "--",
                        "Lot",
                        "1",
                        format_inr(row["ex_gst"]),
                        format_inr(row["ex_gst"]),
                    ]
                )
        table = Table(rows, colWidths=[10 * mm, 55 * mm, 18 * mm, 14 * mm, 12 * mm, 28 * mm, 28 * mm])
        table.setStyle(_TABLE_GRID)
        story.append(table)
    else:
        story.append(Paragraph("Particulars", styles["SectionHeading"]))
        rows = [["Description", "Area / unit", "Rate basis", "Amount (ex-GST)"]]
        for row in sport_rows:
            sport, project_sport, option = row["sport"], row["project_sport"], row["option"]
            rows.append(
                [
                    f"{sport.name} ({option.package.value.capitalize()})",
                    f"{sport.playing_dims} ft, {project_sport.number_of_courts} court"
                    + ("s" if project_sport.number_of_courts != 1 else ""),
                    "Lump sum, turnkey",
                    format_inr(row["ex_gst"]),
                ]
            )
        table = Table(rows, colWidths=[55 * mm, 45 * mm, 35 * mm, 40 * mm])
        table.setStyle(_TABLE_GRID)
        story.append(table)

    total_rounded = round_to_nearest_10(float(quotation.quotation_total))
    # Amendment 24: back-derived from this document's own frozen
    # gst_amount/selling_ex_gst -- the rate that actually produced the
    # rupee figure already printed next to it, not whatever the Master
    # Setting/blend happens to be today (Note R1's HSN-9506 blending
    # means this isn't always literally 18%). selling_ex_gst is the
    # ex-GST base in both GstMode.EXCLUSIVE and GstMode.INCLUSIVE.
    effective_gst_rate = (gst_amount / selling_ex_gst * 100) if selling_ex_gst else 18.0
    totals_rows = [
        ["Subtotal", format_inr(selling_ex_gst)],
        [f"GST @ {effective_gst_rate:.1f}%", format_inr(gst_amount)],
        ["Total Project Cost", format_inr(total_rounded)],
    ]
    totals_table = Table(totals_rows, colWidths=[135 * mm, 40 * mm])
    totals_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ]
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(totals_table)
    story.append(Paragraph("GST as applicable is included in the above cost.", styles["Normal"]))
    story.append(Paragraph(f"<b>Amount in words:</b> {amount_in_words_inr(total_rounded)}", styles["Normal"]))

    if enhanced:
        story.extend(_scope_of_work_flow(db, styles, sport_rows, inclusions))

    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("Delivery timeline &amp; payment schedule", styles["SectionHeading"]))
    for row in sport_rows:
        sport, project_sport = row["sport"], row["project_sport"]
        schedule_out = get_schedule(
            project_sport_id=project_sport.id, start_date=None, mobilisation_days=None, db=db, current_user=current_user
        )
        story.append(
            Paragraph(
                f"<b>{sport.name}</b> -- estimated {schedule_out.total_weeks} week(s) from mobilisation.",
                styles["Normal"],
            )
        )
        # Milestone amounts split off this sport's own apportioned share
        # (row["ex_gst"]/row["gst"]), so they sum back to that share exactly.
        milestone_rows = [["Milestone", "%", "Date", "Amount (Rs base + GST = Total)"]]
        for milestone in schedule_out.payment_schedule:
            base = row["ex_gst"] * milestone.percent / 100
            gst = row["gst"] * milestone.percent / 100
            milestone_rows.append(
                [
                    milestone.name,
                    f"{milestone.percent:g}%",
                    milestone.date.isoformat(),
                    f"{format_inr(base)} + GST {format_inr(gst)} = {format_inr(base + gst)}",
                ]
            )
        milestone_table = Table(milestone_rows, colWidths=[30 * mm, 15 * mm, 25 * mm, 105 * mm])
        milestone_table.setStyle(_TABLE_GRID)
        story.append(milestone_table)
        story.append(Spacer(1, 2 * mm))

    bank_lines = _company_details_lines(db, _COMPANY_BANK_KEYS)
    if bank_lines:
        story.append(Paragraph("Payment to", styles["SectionHeading"]))
        story.extend(Paragraph(line, styles["Normal"]) for line in bank_lines)

    story.append(Paragraph("Warranty", styles["SectionHeading"]))
    warranty_years = _warranty_years(db, client.type if client else None)
    warranty_source = warranty_table_override or _current_warranty_table(db)
    if warranty_years is None and enhanced:
        # Amendment 54: no duration is configured for this client type, so the table
        # has no duration column rather than saying "not yet configured" to a client
        # (pdf_gaps tells the person preparing the quotation).
        warranty_rows = [["Item", "Basis"]] + [[item, basis] for item, basis in warranty_source]
        warranty_widths = [65 * mm, 110 * mm]
    else:
        duration_text = f"{warranty_years} year(s)" if warranty_years is not None else "Not yet configured (Q.1)"
        warranty_rows = [["Item", "Basis", "Duration"]] + [[item, basis, duration_text] for item, basis in warranty_source]
        warranty_widths = [65 * mm, 70 * mm, 40 * mm]
    warranty_table = Table(warranty_rows, colWidths=warranty_widths)
    warranty_table.setStyle(_TABLE_GRID)
    story.append(warranty_table)

    story.append(Paragraph("Standard vs. actual dimensions", styles["SectionHeading"]))
    dims_rows = [["Sport", "Standard (governing body)", "Actual (as built)"]]
    for row in sport_rows:
        dims_rows.append(_standard_vs_actual_row(db, styles, row["sport"], row["project_sport"]))
    dims_table = Table(dims_rows, colWidths=[45 * mm, 75 * mm, 55 * mm])
    dims_table.setStyle(_TABLE_GRID)
    story.append(dims_table)

    story.append(Paragraph("Exclusions", styles["SectionHeading"]))
    story.extend(_exclusions_flow(styles, exclusions))

    story.append(Paragraph("Terms &amp; conditions", styles["SectionHeading"]))
    story.extend(
        Paragraph("&bull; " + term, styles["Normal"])
        for term in _starter_terms(db, project.tender_mode, project.quick_setup, terms_override=terms_override)
    )

    # Amendment 5's Custom Notes component: unstructured remarks a Sales/PM/
    # Director user added on Project Setup, Cost Sheet, or Estimate (one
    # field on the Project, not per-screen) -- only rendered when actually
    # set, right after the fixed T&C list per the amendment's own "Special
    # Remarks / T&C" wording.
    if project.custom_notes:
        story.append(Paragraph("Special Remarks", styles["SectionHeading"]))
        # Escaped -- this is genuinely free-typed text (unlike every other
        # Paragraph() call in this file, which interpolates derived/enum
        # strings), so a stray '<' or '&' would otherwise break ReportLab's
        # mini-XML parser. <br/> preserves the textarea's own line breaks,
        # which Paragraph collapses like HTML by default.
        notes_html = _xml_escape(project.custom_notes).replace("\n", "<br/>")
        story.append(Paragraph(notes_html, styles["Normal"]))

    validity_note = (
        f"Valid until {quotation.sent_at.date().isoformat()} (30 days from sending)."
        if quotation.sent_at
        else "Validity: 30 days from the date this quotation is sent to the client."
    )
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(validity_note, styles["Normal"]))

    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("Accepted by client: _______________________ &nbsp;&nbsp; Date: ____________", styles["Normal"]))

    plan.raise_if_blocked()  # nothing selected is dropped silently: refuse, listing each excluded image
    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm).build(story)
    return buffer, f"{quotation.document_no}.pdf"


@pdf_documents_router.get("/quotations/{quotation_id}/pdf")
def get_quotation_pdf(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    buffer, filename = build_quotation_pdf(db, quotation_id, current_user)
    return _pdf_response(buffer, filename)


@pdf_documents_router.get("/quotation-template-defaults")
def get_quotation_template_defaults(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("pm", "director")),
):
    """Section 14: the Master Settings editor's starting point -- whatever
    is currently effective (a saved override, or today's hardcoded
    default), never a separately maintained copy that could drift from
    what the PDF actually prints. Same read gate as Master Settings itself
    (settings.py's READ_ROLES) -- PM can view, Director can edit.

    Deliberately NOT nested under /quotations/... -- documents.py's
    GET /quotations/{quotation_id} is registered on an earlier router, so
    a literal /quotations/template-defaults would be swallowed by that
    path param (and fail parsing "template-defaults" as a UUID) before
    ever reaching this route."""
    return {
        "terms": _current_quotation_terms(db),
        "warranty_table": [list(row) for row in _current_warranty_table(db)],
    }


class QuotationTemplatePreviewRequest(BaseModel):
    # Section 14: unsaved draft text from the Master Settings editor --
    # never written anywhere, only rendered against a real Quotation's
    # other data so the Director can see the result before saving.
    terms: list[str] | None = None
    warranty_table: list[tuple[str, str]] | None = None


@pdf_documents_router.post("/quotations/{quotation_id}/preview-pdf")
def preview_quotation_pdf_template(
    quotation_id: uuid.UUID,
    payload: QuotationTemplatePreviewRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("director")),
):
    """Section 14: same Director-only gate as Master Settings itself
    (settings.py's WRITE_ROLES) -- this is the live-preview step the
    approved spec requires before a T&C/warranty-table edit is saved."""
    buffer, filename = build_quotation_pdf(
        db, quotation_id, current_user,
        terms_override=payload.terms, warranty_table_override=payload.warranty_table,
    )
    return _pdf_response(buffer, f"preview-{filename}")


# ---------------------------------------------------------------------------
# Image preview and document-specific exclusions
# ---------------------------------------------------------------------------

_CLOSED_QUOTATION = (QuotationStatus.WON, QuotationStatus.LOST, QuotationStatus.EXPIRED, QuotationStatus.SUPERSEDED)
_CLOSED_ESTIMATE = (EstimateStatus.EXPIRED, EstimateStatus.SUPERSEDED)


class PdfCheckOut(BaseModel):
    doc_type: str
    doc_id: uuid.UUID
    complete: bool  # True only when every selected image would be embedded (user-removed ones are an explicit choice)
    included_images: int
    excluded: list[dict]
    note: str


def _plan_preview(db: Session, doc_type: DocumentType, doc_id: uuid.UUID) -> PdfCheckOut:
    plan = _ImagePlan(db, doc_type, doc_id)
    for attachment in _selected_images(db, doc_type, doc_id):
        if _evaluate_image(plan, attachment, full=False):
            plan.included += 1
    return PdfCheckOut(
        doc_type=doc_type.value, doc_id=doc_id, complete=not plan.blocking, included_images=plan.included,
        excluded=[e.as_dict() for e in plan.exclusions],
        note="This is a preview. The document is checked again when it is generated, downloaded or sent.",
    )


@pdf_documents_router.get("/estimates/{estimate_id}/pdf-check", response_model=PdfCheckOut)
def check_estimate_pdf(
    estimate_id: uuid.UUID, db: Session = Depends(get_db), current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    _get_estimate(db, estimate_id)
    return _plan_preview(db, DocumentType.ESTIMATE, estimate_id)


@pdf_documents_router.get("/quotations/{quotation_id}/pdf-check", response_model=PdfCheckOut)
def check_quotation_pdf(
    quotation_id: uuid.UUID, db: Session = Depends(get_db), current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    if not db.query(Quotation).filter(Quotation.id == quotation_id).first():
        raise HTTPException(status_code=404, detail="Quotation not found")
    return _plan_preview(db, DocumentType.QUOTATION, quotation_id)


class PdfImageExclusionIn(BaseModel):
    doc_type: DocumentType
    doc_id: uuid.UUID
    attachment_id: uuid.UUID
    reason: str | None = None


class PdfImageExclusionOut(BaseModel):
    id: uuid.UUID
    doc_type: str
    doc_id: uuid.UUID
    attachment_id: uuid.UUID
    reason: str | None


def _guard_document_open(db: Session, doc_type: DocumentType, doc_id: uuid.UUID) -> None:
    """A closed document (won/lost/expired/superseded quotation, expired/superseded estimate) is a record: what its PDF
    contains is not changed by an exclusion."""
    if doc_type == DocumentType.QUOTATION:
        document = db.query(Quotation).filter(Quotation.id == doc_id).first()
        closed = document is not None and document.status in _CLOSED_QUOTATION
    elif doc_type == DocumentType.ESTIMATE:
        document = db.query(Estimate).filter(Estimate.id == doc_id).first()
        closed = document is not None and document.status in _CLOSED_ESTIMATE
    else:
        raise HTTPException(status_code=400, detail="Only an Estimate or a Quotation has a generated PDF")
    if document is None:
        raise HTTPException(status_code=404, detail=f"{doc_type.value} not found")
    if closed:
        raise HTTPException(status_code=409, detail="This document is closed; the images in its PDF can no longer be changed")


@pdf_documents_router.post("/pdf-image-exclusions", response_model=PdfImageExclusionOut, status_code=201)
def exclude_image_from_document(
    payload: PdfImageExclusionIn, request: Request, db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    """Explicitly remove ONE selected image from ONE document's PDF. The Attachment, its file and hash are untouched and
    every other document that uses it is unaffected; the decision is attributed and audited."""
    ownership.require_visible_document(db, current_user, payload.doc_type.value, payload.doc_id)  # Amendment 60: body ids too
    _guard_document_open(db, payload.doc_type, payload.doc_id)
    attachment = next((a for a in _selected_images(db, payload.doc_type, payload.doc_id) if a.id == payload.attachment_id), None)
    if attachment is None:
        raise HTTPException(status_code=400, detail="That image is not one of the images this document includes")
    existing = (
        db.query(PdfImageExclusion)
        .filter(PdfImageExclusion.doc_type == payload.doc_type.value, PdfImageExclusion.doc_id == payload.doc_id,
                PdfImageExclusion.attachment_id == attachment.id)
        .first()
    )
    if existing is not None:
        return existing  # idempotent
    row = PdfImageExclusion(
        doc_type=payload.doc_type.value, doc_id=payload.doc_id, attachment_id=attachment.id,
        excluded_by_id=current_user.id, reason=(payload.reason or None),
    )
    db.add(row)
    write_audit_log_entry(
        db, current_user, payload.doc_type.value, payload.doc_id, "pdf_image_excluded", None, attachment.original_filename,
        reason=payload.reason, request=request,
    )
    db.commit()
    db.refresh(row)
    return row


@pdf_documents_router.delete("/pdf-image-exclusions/{exclusion_id}", status_code=204)
def restore_image_to_document(
    exclusion_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    row = db.query(PdfImageExclusion).filter(PdfImageExclusion.id == exclusion_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Exclusion not found")
    doc_type = DocumentType(row.doc_type)
    _guard_document_open(db, doc_type, row.doc_id)
    attachment = db.query(Attachment).filter(Attachment.id == row.attachment_id).first()
    write_audit_log_entry(
        db, current_user, row.doc_type, row.doc_id, "pdf_image_excluded", attachment.original_filename if attachment else None,
        None, reason="restored to the document", request=request,
    )
    db.delete(row)
    db.commit()
