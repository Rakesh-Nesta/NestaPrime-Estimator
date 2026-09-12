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

import io
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
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

from app.api.company import get_current_company_logo
from app.api.documents import DOCUMENT_ROLES
from app.api.schedule import get_schedule
from app.api.settings import get_current_setting_value
from app.api.sports import _dimension_deviations, _worst_deviation_status
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.attachment import Attachment, AttachmentTag
from app.models.client import Client, ClientType
from app.models.document import CostSheetLine, Estimate, EstimateOption, Quotation, QuotationLine, WorkPackage
from app.models.package_content import PackageContent
from app.models.project import Project
from app.models.scope_item import ProjectScopeItem, ScopeItem
from app.models.setting import DocumentType
from app.models.sport import ProjectSport, Sport
from app.pdf_utils import amount_in_words_inr, format_inr, round_to_nearest_10

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


def _starter_terms(db: Session, tender_mode: bool = False, quick_setup: bool = False) -> list[str]:
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
    terms = list(_STARTER_TERMS_FIXED)
    if tender_mode:
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


def _product_image_flowable(db: Session, option_id: uuid.UUID, max_width: float, max_height: float):
    """M.6: 'product options table (Budget/Standard/Premium with images).'
    The latest non-superseded product_image attachment on this specific
    option (Attachment's own EstimateOption doc_type, separate from
    Estimate's, since one image belongs to one sport+package row, not
    the whole Estimate). Scaled to fit inside (max_width, max_height)
    while preserving the original aspect ratio -- reportlab pulls Pillow
    in as its own dependency, so no extra image library is needed. A
    missing/corrupt file or no upload at all silently yields no image
    rather than breaking PDF generation -- the row just has no picture."""
    attachment = (
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
    if attachment is None:
        return ""
    path = Path(attachment.storage_path)
    if not path.exists():
        return ""
    try:
        # ImageReader.getSize() only reads the header -- a truncated or
        # otherwise corrupt file can still pass that and only fail later,
        # inside reportlab's own build() when the pixel data is actually
        # decoded (too late to degrade gracefully). Pillow's own .load()
        # forces the full decode now, while it's still inside this
        # try/except, so a bad file is caught here instead of crashing
        # PDF generation for the whole document.
        with PILImage.open(path) as pil_image:
            pil_image.load()
        reader = ImageReader(str(path))
        original_width, original_height = reader.getSize()
        scale = min(max_width / original_width, max_height / original_height)
        return Image(str(path), width=original_width * scale, height=original_height * scale)
    except Exception:
        return ""


def _company_logo_flowable(db: Session, max_width: float, max_height: float):
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


@pdf_documents_router.get("/estimates/{estimate_id}/pdf")
def get_estimate_pdf(
    estimate_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    estimate = _get_estimate(db, estimate_id)
    project = db.query(Project).filter(Project.id == estimate.project_id).first()
    client = db.query(Client).filter(Client.id == project.client_id).first()
    options = db.query(EstimateOption).filter(EstimateOption.estimate_id == estimate_id).all()
    inclusions, exclusions = _inclusions_and_exclusions(db, project.id)

    styles = _styles()
    logo = _company_logo_flowable(db, 45 * mm, 18 * mm)
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
                _product_image_flowable(db, option.id, image_col_width, image_col_height),
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

    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm).build(story)
    return _pdf_response(buffer, f"{estimate.document_no}.pdf")


# ---------------------------------------------------------------------------
# Formal Quotation PDF
# ---------------------------------------------------------------------------


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


@pdf_documents_router.get("/quotations/{quotation_id}/pdf")
def get_quotation_pdf(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    quotation = _get_quotation(db, quotation_id)
    project = db.query(Project).filter(Project.id == quotation.project_id).first()
    client = db.query(Client).filter(Client.id == project.client_id).first()
    estimate = db.query(Estimate).filter(Estimate.id == quotation.estimate_id).first()
    qlines = db.query(QuotationLine).filter(QuotationLine.quotation_id == quotation_id).all()
    inclusions, exclusions = _inclusions_and_exclusions(db, project.id)

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
    logo = _company_logo_flowable(db, 45 * mm, 18 * mm)
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
    totals_rows = [
        ["Subtotal", format_inr(selling_ex_gst)],
        ["GST @ 18% (flat)", format_inr(gst_amount)],
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
    duration_text = f"{warranty_years} year(s)" if warranty_years is not None else "Not yet configured (Q.1)"
    warranty_rows = [["Item", "Basis", "Duration"]] + [
        [item, basis, duration_text] for item, basis in WARRANTY_TABLE
    ]
    warranty_table = Table(warranty_rows, colWidths=[65 * mm, 70 * mm, 40 * mm])
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
        for term in _starter_terms(db, project.tender_mode, project.quick_setup)
    )

    validity_note = (
        f"Valid until {quotation.sent_at.date().isoformat()} (30 days from sending)."
        if quotation.sent_at
        else "Validity: 30 days from the date this quotation is sent to the client."
    )
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(validity_note, styles["Normal"]))

    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("Accepted by client: _______________________ &nbsp;&nbsp; Date: ____________", styles["Normal"]))

    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm).build(story)
    return _pdf_response(buffer, f"{quotation.document_no}.pdf")
