import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.api.pricing import compute_pricing, cost_weighted_floor_and_target, effective_floor_and_target
from app.api.settings import get_current_setting_value, get_gst_rate_percent
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.attachment import ApprovalStrength, Attachment, AttachmentTag
from app.models.client import Client
from app.models.purchase_order import PurchaseOrder, PurchaseOrderLine, PurchaseOrderStatus
from app.models.vendor import Vendor
from app.models.document import (
    CostSheet,
    CostSheetLine,
    CostSheetStatus,
    Estimate,
    EstimateOption,
    EstimateOptionClientStatus,
    EstimateStatus,
    Quotation,
    QuotationLine,
    QuotationStatus,
    WorkPackage,
)
from app.models.margin_policy import MarginPolicy
from app.models.project import Package, Project
from app.models.rate_item import LabourCategory, RateSource
from app.models.setting import DocumentType, Override
from app.models.sport import ProjectSport

# M.3: quotations at or above this value (or any Government/Tender deal)
# require Formal evidence before Won, not just Informal.
FORMAL_EVIDENCE_REQUIRED_ABOVE_RS = 2_500_000.0  # "[confirm]"

# M.1: an Unverified (skip-generated, M.2 rule 3) cost sheet "behaves as
# Draft for editing" -- every place that gates an edit/recompute action on
# Draft status accepts either.
_EDITABLE_COST_SHEET_STATUSES = (CostSheetStatus.DRAFT, CostSheetStatus.UNVERIFIED)


def _has_evidence(db: Session, doc_type: DocumentType, doc_id: uuid.UUID, require_formal: bool = False) -> bool:
    query = db.query(Attachment).filter(
        Attachment.doc_type == doc_type,
        Attachment.doc_id == doc_id,
        Attachment.tag == AttachmentTag.APPROVAL_EVIDENCE,
        Attachment.superseded_by_id.is_(None),
    )
    if require_formal:
        query = query.filter(Attachment.approval_strength == ApprovalStrength.FORMAL)
    return query.first() is not None


def _enforce_approval_evidence(
    db: Session,
    doc_type: DocumentType,
    doc_id: uuid.UUID,
    current_user,
    waive_evidence_reason: str | None,
    require_formal: bool = False,
    request: Request | None = None,
) -> None:
    """M.3: 'A stage cannot move to its approved status without at least
    one attachment tagged approval_evidence unless PM/Director waives it
    (logged).' Government/Tender and quotations >= Rs 25L require Formal
    evidence specifically (M.3). M.5 names "waivers" as one of the audit
    log's four covered categories -- logged here, the one place every
    waiver in the app actually happens."""
    if _has_evidence(db, doc_type, doc_id, require_formal=require_formal):
        return
    if not waive_evidence_reason:
        kind = "Formal approval_evidence" if require_formal else "an approval_evidence attachment"
        raise HTTPException(
            status_code=422,
            detail=f"This action needs {kind}, or a PM/Director waiver reason (M.3)",
        )
    if current_user.role.value not in ("pm", "director"):
        raise HTTPException(status_code=403, detail="Only PM/Director may waive approval evidence (M.4)")

    write_audit_log_entry(
        db, current_user, doc_type.value, doc_id, "approval_evidence_waiver",
        old_value=None, new_value="waived", reason=waive_evidence_reason, request=request,
    )

cost_sheets_router = APIRouter(tags=["cost-sheets"])
estimates_router = APIRouter(tags=["estimates"])
quotations_router = APIRouter(tags=["quotations"])

# K.3: cost, contingency, markup and margin are never visible to Sales.
COST_ROLES = ("pm", "director")
# M.4: Sales may create/send Estimates & Quotations and record client
# status / won-lost, but the responses below strip cost-side fields for it.
DOCUMENT_ROLES = ("sales", "pm", "director")

# Fallbacks used only when Part Q's Master Settings has no row yet for the
# key (e.g. a fresh test DB) -- see get_current_setting_value calls below
# for the live values.
ESTIMATE_VALIDITY_DAYS_DEFAULT = 15
QUOTATION_VALIDITY_DAYS_DEFAULT = 30
PRICE_RANGE_PERCENT_DEFAULT = 5.0  # M.1: "range_pct [confirm 5%]"

# K.1 step 6 defaults, keyed by work_package -- overridable per Part Q.
CONTINGENCY_PERCENT_DEFAULT = {
    WorkPackage.CIVIL: 5.0,
    WorkPackage.STRUCTURE: 5.0,
    WorkPackage.FLOORING: 3.0,
    WorkPackage.ELECTRICAL: 3.0,
    WorkPackage.POOL: 8.0,
    WorkPackage.HVAC: 5.0,
    WorkPackage.ACCESSORIES: 2.0,
    WorkPackage.SCOPE: 5.0,
    WorkPackage.SERVICES: 0.0,
}
BLENDED_LABOUR_FALLBACK_PERCENT_DEFAULT = 22.0  # J.2 "Blended fallback"
SITE_ESTABLISHMENT_PERCENT_DEFAULT = 6.0  # D.4 "[confirm 4-8%]" -- midpoint
# K.1 step 4B: "Warranty reserve 1% (private clients; Appendix B)" --
# mutually exclusive with step 4A's Tender Mode DLP reserve (never both).
WARRANTY_RESERVE_PERCENT_DEFAULT = 1.0
# K.1 step 4A (Tender Mode only): "DLP reserve 1% (replaces the 1%
# warranty reserve of Appendix B -- never both)."
DLP_RESERVE_PERCENT_DEFAULT = 1.0
# Part L "Statutory": "BOCW cess 1% on works > Rs 10 L ... flow into K.1
# step 4A." Tender Mode only, and only once the pre-cess subtotal (across
# every work package) exceeds this threshold.
BOCW_CESS_PERCENT_DEFAULT = 1.0
BOCW_CESS_THRESHOLD_RS_DEFAULT = 1_000_000.0  # "Rs 10 L"
# K.1 step 5A: "Company overhead recovery [confirm 10%] of step 5."
COMPANY_OVERHEAD_RECOVERY_PERCENT_DEFAULT = 10.0

# J.2: "Preferred: activity-based labour rates ... so labour follows
# effort, not material value." Named activities, matched by the labour
# category on the line AND the line's own unit -- an activity rate only
# applies when a line's unit matches what that activity is priced in.
# electrical has a Settings key below for completeness (J.2 names all six)
# but no take-off engine produces a line in its matching unit (point), so
# it never fires today -- a documented, honest gap, not a bug. Netting and
# pool_mep have no activity-rate alternative in J.2's own table, so they
# always use the category-% fallback, by design. None of these Settings
# carry a numeric default -- J.2 gives no [confirm] figure for them,
# unlike the % fallback table -- so every Cost Sheet uses the % fallback
# until the Director actually configures a real rate in Master Settings.
# wooden_flooring and acrylic_pu (Part F.3/F.2) only fire on the single
# "finished surface" line each of flooring.py's wooden/acrylic-PU
# take-offs produces -- their supporting layers (ply, battens, moisture
# barrier) carry no labour_category_id at all and use the blended
# fallback, so one installation isn't charged the activity rate multiple
# times over.
ACTIVITY_RATE_RULES: list[tuple[str, str, str]] = [
    ("ms_fabrication_erection", "kg", "activity_rate_ms_per_kg"),
    ("civil_base_site_prep", "cum", "activity_rate_concrete_per_cum"),
    ("turf_laying", "sqm", "activity_rate_turf_laying_per_sqm"),
    ("wooden_flooring", "sqft", "activity_rate_wooden_flooring_per_sqft"),
    ("acrylic_pu", "sqft", "activity_rate_acrylic_pu_per_sqft"),
]
J2_NAMED_ACTIVITY_CATEGORY_KEYS = {
    "ms_fabrication_erection",
    "civil_base_site_prep",
    "turf_laying",
    "wooden_flooring",
    "acrylic_pu",
    "electrical",
}


def _get_setting_float(db: Session, key: str, default: float) -> float:
    value = get_current_setting_value(db, key)
    return float(value) if value is not None else default


def _current_override(db: Session, doc_type: DocumentType, doc_id: uuid.UUID, key: str) -> Override | None:
    """Q.2 rule 2: 'An override changes only that document.' Multiple
    Override rows can exist for the same (document, key) pair over time
    (nothing here ever mutates or deletes one, matching this app's
    write-once convention for approval-adjacent records) -- the most
    recently created one is the currently-effective override."""
    return (
        db.query(Override)
        .filter(Override.document_type == doc_type, Override.document_id == doc_id, Override.setting_key == key)
        .order_by(Override.created_at.desc())
        .first()
    )


def _get_effective_setting_float(
    db: Session, doc_type: DocumentType, doc_id: uuid.UUID, key: str, default: float
) -> float:
    """Q.2 rule 2: a document-scoped Override takes precedence over the
    global Master Setting, which itself takes precedence over the
    Python fallback -- one extra, document-scoped tier ahead of
    _get_setting_float's own two-tier precedence."""
    override = _current_override(db, doc_type, doc_id, key)
    if override is not None:
        return float(override.override_value)
    return _get_setting_float(db, key, default)


def _get_setting_int(db: Session, key: str, default: int) -> int:
    value = get_current_setting_value(db, key)
    return int(value) if value is not None else default


def _document_no(project_no: str, prefix: str, revision_major: int, revision_minor: int = 0) -> str:
    """M.2 rule 10: the CS-/EST-/NPQ- documents reuse the project's own
    YYMM-#### suffix, e.g. project P-2609-0018 -> CS-2609-0018-R1."""
    suffix = project_no.split("-", 1)[1]
    rev = f"R{revision_major}" if revision_minor == 0 else f"R{revision_major}.{revision_minor}"
    return f"{prefix}-{suffix}-{rev}"


def _get_margin_policy(db: Session, client_type) -> MarginPolicy:
    policy = db.query(MarginPolicy).filter(MarginPolicy.client_type == client_type).first()
    if not policy:
        raise HTTPException(status_code=404, detail="No margin policy for this client type")
    return policy


# --------------------------------------------------------------------------
# Cost Sheets (M.1 stage 1)
# --------------------------------------------------------------------------


class CostSheetCreate(BaseModel):
    # A whole-project figure typed directly still works (the original
    # document-state-machine simplification); omit it to start an empty
    # Draft and build the total up from real CostSheetLine rows + /recompute
    # instead.
    cost_total: float = Field(default=0.0, ge=0)


class CostSheetOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    document_no: str
    revision_major: int
    revision_minor: int
    status: CostSheetStatus
    cost_total: float
    auto_generated: bool
    verified_by_id: uuid.UUID | None
    verified_at: datetime | None
    created_by_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@cost_sheets_router.post(
    "/projects/{project_id}/cost-sheets", response_model=CostSheetOut, status_code=201
)
def create_cost_sheet(
    project_id: uuid.UUID,
    payload: CostSheetCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    existing = (
        db.query(CostSheet)
        .filter(CostSheet.project_id == project_id, CostSheet.status != CostSheetStatus.SUPERSEDED)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="An active cost sheet already exists for this project; use /revise on it instead",
        )

    cost_sheet = CostSheet(
        project_id=project_id,
        document_no=_document_no(project.project_no, "CS", 1),
        cost_total=payload.cost_total,
        created_by_id=current_user.id,
    )
    db.add(cost_sheet)
    db.commit()
    db.refresh(cost_sheet)
    return cost_sheet


@cost_sheets_router.get("/projects/{project_id}/cost-sheets", response_model=list[CostSheetOut])
def list_cost_sheets(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    return (
        db.query(CostSheet)
        .filter(CostSheet.project_id == project_id)
        .order_by(CostSheet.revision_major.desc())
        .all()
    )


@cost_sheets_router.get("/cost-sheets/{cost_sheet_id}", response_model=CostSheetOut)
def get_cost_sheet(
    cost_sheet_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    cost_sheet = db.query(CostSheet).filter(CostSheet.id == cost_sheet_id).first()
    if not cost_sheet:
        raise HTTPException(status_code=404, detail="Cost sheet not found")
    return cost_sheet


@cost_sheets_router.post("/cost-sheets/{cost_sheet_id}/verify", response_model=CostSheetOut)
def verify_cost_sheet(
    cost_sheet_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """M.1: 'Draft -> Verified' by PM or Director -- an Unverified
    (skip-generated) cost sheet can also be verified this way once real
    figures replace the PM's original ballpark (M.2 rule 3)."""
    cost_sheet = db.query(CostSheet).filter(CostSheet.id == cost_sheet_id).first()
    if not cost_sheet:
        raise HTTPException(status_code=404, detail="Cost sheet not found")
    if cost_sheet.status not in _EDITABLE_COST_SHEET_STATUSES:
        raise HTTPException(status_code=400, detail=f"Cannot verify a cost sheet in {cost_sheet.status.value} status")
    if cost_sheet.cost_total <= 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot verify a cost sheet with no cost -- enter cost_total or add lines and /recompute",
        )
    if current_user.role.value != "director":
        missing = _categories_missing_activity_rate(db, cost_sheet_id)
        if len(missing) > 3:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"More than 3 categories lack activity rates ({', '.join(sorted(missing))}) "
                    "-- Director confirmation required (J.2)"
                ),
            )

    was_unverified = cost_sheet.status == CostSheetStatus.UNVERIFIED
    cost_sheet.status = CostSheetStatus.VERIFIED
    cost_sheet.verified_by_id = current_user.id
    cost_sheet.verified_at = datetime.now(UTC)

    if was_unverified:
        # M.1: "resting on an Unverified Cost Sheet ... cannot be marked
        # Won until the Cost Sheet is verified" -- the gate tracks the
        # cost sheet's real status, so a Quotation already built on this
        # Unverified sheet becomes released/won-eligible the normal way
        # once it's verified, rather than being permanently stuck.
        estimate_ids = [
            row[0] for row in db.query(Estimate.id).filter(Estimate.cost_sheet_id == cost_sheet_id).all()
        ]
        if estimate_ids:
            db.query(Quotation).filter(Quotation.estimate_id.in_(estimate_ids)).update(
                {Quotation.cost_basis_unverified: False}, synchronize_session=False
            )

    db.commit()
    db.refresh(cost_sheet)
    return cost_sheet


@cost_sheets_router.post(
    "/cost-sheets/{cost_sheet_id}/revise", response_model=CostSheetOut, status_code=201
)
def revise_cost_sheet(
    cost_sheet_id: uuid.UUID,
    payload: CostSheetCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """M.2 rule 4: 'Any edit to a Verified Cost Sheet creates CS-R(n+1) in
    Draft requiring re-verification'; the prior revision becomes Superseded.
    Known gap: the new revision does not carry over the old revision's
    CostSheetLine rows (M.2 rule 4's 'refresh to current settings' choice
    isn't implemented at line level yet) -- re-enter cost_total directly or
    re-add lines and /recompute on the new revision."""
    current = db.query(CostSheet).filter(CostSheet.id == cost_sheet_id).first()
    if not current:
        raise HTTPException(status_code=404, detail="Cost sheet not found")
    if current.status != CostSheetStatus.VERIFIED:
        raise HTTPException(status_code=400, detail="Only a Verified cost sheet can be revised")

    project = db.query(Project).filter(Project.id == current.project_id).first()
    new_revision = CostSheet(
        project_id=current.project_id,
        document_no=_document_no(project.project_no, "CS", current.revision_major + 1),
        revision_major=current.revision_major + 1,
        cost_total=payload.cost_total,
        created_by_id=current_user.id,
    )
    current.status = CostSheetStatus.SUPERSEDED
    db.add(new_revision)
    db.commit()
    db.refresh(new_revision)
    return new_revision


# --------------------------------------------------------------------------
# Cost Sheet lines (Part O COST_SHEETS.lines[]) -- the take-off quantity
# engine's foundation. Manually entered for now; Parts D/E/F will populate
# these programmatically once their formulas are built.
# --------------------------------------------------------------------------


class CostSheetLineCreate(BaseModel):
    project_sport_id: uuid.UUID | None = None
    rate_item_id: uuid.UUID | None = None
    work_package: WorkPackage
    category: str
    item_name: str
    spec: str | None = None
    unit: str
    quantity: float = Field(gt=0)
    rate: float = Field(ge=0)
    source: RateSource = RateSource.MANUAL
    city_of_quote: str | None = None
    labour_category_id: uuid.UUID | None = None
    wastage_percent: float | None = Field(default=None, ge=0)


class CostSheetLineOut(BaseModel):
    id: uuid.UUID
    cost_sheet_id: uuid.UUID
    project_sport_id: uuid.UUID | None
    rate_item_id: uuid.UUID | None
    work_package: WorkPackage
    category: str
    item_name: str
    spec: str | None
    unit: str
    quantity: float
    rate: float
    amount: float  # quantity x rate, computed -- not a stored column
    source: RateSource
    city_of_quote: str | None
    labour_category_id: uuid.UUID | None
    wastage_percent: float | None
    created_at: datetime


def _line_to_out(line: CostSheetLine) -> CostSheetLineOut:
    return CostSheetLineOut(
        id=line.id,
        cost_sheet_id=line.cost_sheet_id,
        project_sport_id=line.project_sport_id,
        rate_item_id=line.rate_item_id,
        work_package=line.work_package,
        category=line.category,
        item_name=line.item_name,
        spec=line.spec,
        unit=line.unit,
        quantity=float(line.quantity),
        rate=float(line.rate),
        amount=float(line.quantity) * float(line.rate),
        source=line.source,
        city_of_quote=line.city_of_quote,
        labour_category_id=line.labour_category_id,
        wastage_percent=float(line.wastage_percent) if line.wastage_percent is not None else None,
        created_at=line.created_at,
    )


def _activity_rate_for_line(db: Session, line: CostSheetLine, category_key: str | None) -> float | None:
    if category_key is None:
        return None
    for rule_category_key, rule_unit, settings_key in ACTIVITY_RATE_RULES:
        if category_key == rule_category_key and line.unit == rule_unit:
            value = get_current_setting_value(db, settings_key)
            return float(value) if value is not None else None
    return None


def _labour_amount_and_warning(
    db: Session, line: CostSheetLine, material: float, blended_fallback_percent: float
) -> tuple[float, str | None]:
    """J.2: activity rate first (Rs/unit x quantity), category % as
    fallback -- with the fallback surfaced as a warning whenever the
    category is one of J.2's own named activities."""
    category = (
        db.query(LabourCategory).filter(LabourCategory.id == line.labour_category_id).first()
        if line.labour_category_id
        else None
    )
    category_key = category.key if category else None

    activity_rate = _activity_rate_for_line(db, line, category_key)
    if activity_rate is not None:
        return float(line.quantity) * activity_rate, None

    percent = float(category.default_percent) if category else blended_fallback_percent
    warning = None
    if category_key in J2_NAMED_ACTIVITY_CATEGORY_KEYS:
        warning = f"Activity rate missing for {category.name} -- using fallback {percent:g}%"
    return material * percent / 100, warning


def _categories_missing_activity_rate(db: Session, cost_sheet_id: uuid.UUID) -> set[str]:
    """J.2: 'If more than 3 categories on a Cost Sheet lack activity rates,
    PM verification requires Director confirmation.' Counted only among
    J.2's own named activity categories -- netting and pool_mep never had
    an activity-rate alternative in the blueprint, so they don't count as
    'missing' one."""
    lines = db.query(CostSheetLine).filter(CostSheetLine.cost_sheet_id == cost_sheet_id).all()
    missing: set[str] = set()
    for line in lines:
        category = (
            db.query(LabourCategory).filter(LabourCategory.id == line.labour_category_id).first()
            if line.labour_category_id
            else None
        )
        if not category or category.key not in J2_NAMED_ACTIVITY_CATEGORY_KEYS:
            continue
        if _activity_rate_for_line(db, line, category.key) is None:
            missing.add(category.key)
    return missing


def _compute_cost_sheet_total(db: Session, cost_sheet: CostSheet) -> float:
    """K.1 steps 1 (material), 2 (labour -- activity rate first, category-%
    fallback per J.2), 3 (site establishment %, D.4; freight/crane are
    PM-entered CostSheetLine rows via POST .../freight-crane, so they flow
    through steps 1-2 like any other line rather than needing a separate
    term here), 4 (design & approvals -- likewise PM-entered lines via
    POST .../design-approvals), 4A (Tender Mode only: DLP reserve % + BOCW
    cess % above the Rs 10 L threshold; BG cost and tender fee are
    PM-entered lines via POST .../tender-overheads, same pattern as
    freight/crane), 4B (warranty reserve %, private/non-Tender projects
    only -- mutually exclusive with 4A's DLP reserve, per K.1's own text),
    5A (company overhead recovery % of step 5) and 6 (contingency grouped
    by work_package).

    Site establishment, warranty/DLP reserve and company overhead recovery
    are each "a flat % of a running subtotal" globally (K.1 steps 3/4B or
    4A/5A), but since a percentage of a sum equals the sum of that
    percentage applied to each addend, multiplying each work_package's own
    subtotal by every one of these flat factors before that package's own
    contingency is mathematically identical to computing one global amount
    at each step and allocating it back out proportionally -- so they're
    all folded into the same per-package loop without a separate
    allocation pass, in the same order the blueprint lists them (3, 4B/4A,
    5A) ahead of contingency (6). BOCW cess breaks that trick on its own,
    though: Part L's 10 L threshold applies to the WHOLE project's pre-cess
    subtotal, not to each work_package independently, so the loop runs in
    two passes -- the first computes each package's pre-cess subtotal (and
    their sum, to test the threshold once), the second applies the
    resulting cess percentage (0% or the configured rate, same for every
    package once decided) ahead of that package's own contingency."""
    lines = db.query(CostSheetLine).filter(CostSheetLine.cost_sheet_id == cost_sheet.id).all()
    if not lines:
        raise HTTPException(status_code=400, detail="Cannot recompute a cost sheet with no lines")

    project = db.query(Project).filter(Project.id == cost_sheet.project_id).first()
    tender_mode = project is not None and project.tender_mode

    blended_fallback = db.query(LabourCategory).filter(LabourCategory.key == "blended_fallback").first()
    blended_fallback_percent = (
        float(blended_fallback.default_percent) if blended_fallback else BLENDED_LABOUR_FALLBACK_PERCENT_DEFAULT
    )

    package_base: dict[WorkPackage, float] = {}
    for line in lines:
        material = float(line.quantity) * float(line.rate)
        labour, _warning = _labour_amount_and_warning(db, line, material, blended_fallback_percent)
        package_base[line.work_package] = package_base.get(line.work_package, 0.0) + material + labour

    site_establishment_percent = _get_effective_setting_float(
        db, DocumentType.COST_SHEET, cost_sheet.id, "site_establishment_percent", SITE_ESTABLISHMENT_PERCENT_DEFAULT
    )
    warranty_reserve_percent = (
        0.0
        if tender_mode
        else _get_effective_setting_float(
            db, DocumentType.COST_SHEET, cost_sheet.id, "warranty_reserve_percent", WARRANTY_RESERVE_PERCENT_DEFAULT
        )
    )
    dlp_reserve_percent = (
        _get_effective_setting_float(
            db, DocumentType.COST_SHEET, cost_sheet.id, "dlp_reserve_percent", DLP_RESERVE_PERCENT_DEFAULT
        )
        if tender_mode
        else 0.0
    )
    company_overhead_percent = _get_effective_setting_float(
        db, DocumentType.COST_SHEET, cost_sheet.id, "company_overhead_recovery_percent",
        COMPANY_OVERHEAD_RECOVERY_PERCENT_DEFAULT,
    )

    pre_cess_by_package: dict[WorkPackage, float] = {}
    pre_cess_total = 0.0
    for work_package, base in package_base.items():
        loaded = base * (1 + site_establishment_percent / 100)
        loaded *= 1 + warranty_reserve_percent / 100
        loaded *= 1 + dlp_reserve_percent / 100
        loaded *= 1 + company_overhead_percent / 100
        pre_cess_by_package[work_package] = loaded
        pre_cess_total += loaded

    bocw_cess_threshold_rs = _get_setting_float(db, "bocw_cess_threshold_rs", BOCW_CESS_THRESHOLD_RS_DEFAULT)
    bocw_cess_percent = (
        _get_effective_setting_float(
            db, DocumentType.COST_SHEET, cost_sheet.id, "bocw_cess_percent", BOCW_CESS_PERCENT_DEFAULT
        )
        if (tender_mode and pre_cess_total > bocw_cess_threshold_rs)
        else 0.0
    )

    cost_incl_contingency = 0.0
    for work_package, loaded in pre_cess_by_package.items():
        loaded *= 1 + bocw_cess_percent / 100
        contingency_percent = _get_effective_setting_float(
            db, DocumentType.COST_SHEET, cost_sheet.id,
            f"contingency_{work_package.value}_percent", CONTINGENCY_PERCENT_DEFAULT[work_package],
        )
        cost_incl_contingency += loaded * (1 + contingency_percent / 100)
    return cost_incl_contingency


@cost_sheets_router.post(
    "/cost-sheets/{cost_sheet_id}/lines", response_model=CostSheetLineOut, status_code=201
)
def add_cost_sheet_line(
    cost_sheet_id: uuid.UUID,
    payload: CostSheetLineCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    cost_sheet = db.query(CostSheet).filter(CostSheet.id == cost_sheet_id).first()
    if not cost_sheet:
        raise HTTPException(status_code=404, detail="Cost sheet not found")
    if cost_sheet.status not in _EDITABLE_COST_SHEET_STATUSES:
        raise HTTPException(status_code=400, detail="Lines can only be added to a Draft or Unverified cost sheet")

    if payload.project_sport_id is not None:
        project_sport = (
            db.query(ProjectSport)
            .filter(ProjectSport.id == payload.project_sport_id, ProjectSport.project_id == cost_sheet.project_id)
            .first()
        )
        if not project_sport:
            raise HTTPException(status_code=404, detail="Sport selection not on this project")

    line = CostSheetLine(cost_sheet_id=cost_sheet_id, **payload.model_dump())
    db.add(line)
    db.commit()
    db.refresh(line)
    return _line_to_out(line)


@cost_sheets_router.get("/cost-sheets/{cost_sheet_id}/lines", response_model=list[CostSheetLineOut])
def list_cost_sheet_lines(
    cost_sheet_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    lines = db.query(CostSheetLine).filter(CostSheetLine.cost_sheet_id == cost_sheet_id).all()
    return [_line_to_out(line) for line in lines]


@cost_sheets_router.delete("/cost-sheets/{cost_sheet_id}/lines/{line_id}", status_code=204)
def delete_cost_sheet_line(
    cost_sheet_id: uuid.UUID,
    line_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    cost_sheet = db.query(CostSheet).filter(CostSheet.id == cost_sheet_id).first()
    if not cost_sheet:
        raise HTTPException(status_code=404, detail="Cost sheet not found")
    if cost_sheet.status not in _EDITABLE_COST_SHEET_STATUSES:
        raise HTTPException(status_code=400, detail="Lines can only be removed from a Draft or Unverified cost sheet")

    line = (
        db.query(CostSheetLine)
        .filter(CostSheetLine.id == line_id, CostSheetLine.cost_sheet_id == cost_sheet_id)
        .first()
    )
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    db.delete(line)
    db.commit()


@cost_sheets_router.post("/cost-sheets/{cost_sheet_id}/recompute", response_model=CostSheetOut)
def recompute_cost_sheet(
    cost_sheet_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    cost_sheet = db.query(CostSheet).filter(CostSheet.id == cost_sheet_id).first()
    if not cost_sheet:
        raise HTTPException(status_code=404, detail="Cost sheet not found")
    if cost_sheet.status not in _EDITABLE_COST_SHEET_STATUSES:
        raise HTTPException(status_code=400, detail="Only a Draft or Unverified cost sheet can be recomputed")

    cost_sheet.cost_total = _compute_cost_sheet_total(db, cost_sheet)
    db.commit()
    db.refresh(cost_sheet)
    return cost_sheet


class K1ConstantOut(BaseModel):
    key: str
    label: str
    master_value: float
    effective_value: float
    is_overridden: bool
    override_reason: str | None
    override_id: uuid.UUID | None


@cost_sheets_router.get("/cost-sheets/{cost_sheet_id}/k1-constants", response_model=list[K1ConstantOut])
def get_k1_constants(
    cost_sheet_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """Q.2 rule 2: surfaces every K.1 percentage this cost sheet's own
    /recompute actually reads, its current global Master Setting value
    (or Python fallback if never configured), and whether a document-
    scoped Override is currently in effect for it -- the read side of
    the same precedence _get_effective_setting_float applies when
    computing the total, so the UI never has to duplicate these
    defaults itself."""
    cost_sheet = db.query(CostSheet).filter(CostSheet.id == cost_sheet_id).first()
    if not cost_sheet:
        raise HTTPException(status_code=404, detail="Cost sheet not found")
    project = db.query(Project).filter(Project.id == cost_sheet.project_id).first()

    keys: list[tuple[str, str, float]] = [
        ("site_establishment_percent", "Site establishment %", SITE_ESTABLISHMENT_PERCENT_DEFAULT),
        ("company_overhead_recovery_percent", "Company overhead recovery %", COMPANY_OVERHEAD_RECOVERY_PERCENT_DEFAULT),
    ]
    if project is not None and project.tender_mode:
        keys.append(("dlp_reserve_percent", "DLP reserve % (Tender Mode)", DLP_RESERVE_PERCENT_DEFAULT))
        keys.append(("bocw_cess_percent", "BOCW cess % (Tender Mode, works > Rs 10 L)", BOCW_CESS_PERCENT_DEFAULT))
    else:
        keys.append(("warranty_reserve_percent", "Warranty reserve %", WARRANTY_RESERVE_PERCENT_DEFAULT))
    for work_package in WorkPackage:
        keys.append((
            f"contingency_{work_package.value}_percent",
            f"Contingency -- {work_package.value}",
            CONTINGENCY_PERCENT_DEFAULT[work_package],
        ))

    out: list[K1ConstantOut] = []
    for key, label, default in keys:
        master_value = _get_setting_float(db, key, default)
        override = _current_override(db, DocumentType.COST_SHEET, cost_sheet.id, key)
        out.append(K1ConstantOut(
            key=key,
            label=label,
            master_value=master_value,
            effective_value=float(override.override_value) if override else master_value,
            is_overridden=override is not None,
            override_reason=override.reason if override else None,
            override_id=override.id if override else None,
        ))
    return out


@cost_sheets_router.get("/cost-sheets/{cost_sheet_id}/labour-warnings", response_model=list[str])
def get_labour_warnings(
    cost_sheet_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """J.2: 'the Cost Sheet shows a warning line "Activity rate missing
    for [category] -- using fallback X%".' One warning per line whose
    category has a preferred activity rate (J.2) that isn't configured or
    doesn't match this line's unit."""
    cost_sheet = db.query(CostSheet).filter(CostSheet.id == cost_sheet_id).first()
    if not cost_sheet:
        raise HTTPException(status_code=404, detail="Cost sheet not found")

    lines = db.query(CostSheetLine).filter(CostSheetLine.cost_sheet_id == cost_sheet_id).all()
    blended_fallback = db.query(LabourCategory).filter(LabourCategory.key == "blended_fallback").first()
    blended_fallback_percent = (
        float(blended_fallback.default_percent) if blended_fallback else BLENDED_LABOUR_FALLBACK_PERCENT_DEFAULT
    )

    warnings = []
    for line in lines:
        material = float(line.quantity) * float(line.rate)
        _, warning = _labour_amount_and_warning(db, line, material, blended_fallback_percent)
        if warning:
            warnings.append(warning)
    return warnings


def _po_lookup_for_cost_sheet(
    db: Session, cost_sheet_id: uuid.UUID
) -> dict[uuid.UUID, tuple[PurchaseOrderLine, PurchaseOrder, Vendor]]:
    """Part O: one PO line per CostSheetLine at most (see
    PurchaseOrderLine's own docstring on why split-sourcing isn't
    modelled), so a single cost_sheet_line_id -> (PurchaseOrderLine,
    PurchaseOrder, Vendor) map covers every line -- a cancelled PO isn't
    procurement in progress, so it's excluded here. Shared by the
    Consumption Sheet's JSON view (below) and its Excel export."""
    po_rows = (
        db.query(PurchaseOrderLine, PurchaseOrder, Vendor)
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.purchase_order_id)
        .join(Vendor, Vendor.id == PurchaseOrder.vendor_id)
        .filter(PurchaseOrder.cost_sheet_id == cost_sheet_id, PurchaseOrder.status != PurchaseOrderStatus.CANCELLED)
        .all()
    )
    return {po_line.cost_sheet_line_id: (po_line, po, vendor) for po_line, po, vendor in po_rows}


class ConsumptionSheetRowOut(BaseModel):
    """J.3 Material Consumption Sheet columns. Vendor / delivery date /
    received qty are now a real read of Part O's PURCHASE_ORDERS when a
    PO has been raised for this line; a line with no PO yet still shows
    null rather than fabricated procurement data."""

    id: uuid.UUID
    category: str
    item_name: str
    spec: str | None
    unit: str
    theoretical_qty: float
    wastage_percent: float | None
    order_qty: float
    rate: float
    amount: float
    vendor: str | None = None
    po_no: str | None = None
    delivery_date: date | None = None
    received_qty: float | None = None
    balance_qty: float | None = None
    # J.3's example remark ("Galvanised, coastal") is a spec/finish note --
    # already folded into item_name by the take-off engines that apply a
    # finish (e.g. Structures' coastal galvanising) rather than tracked in
    # a separate column, so there is nothing distinct to surface here yet.
    remarks: None = None


@cost_sheets_router.get(
    "/cost-sheets/{cost_sheet_id}/consumption-sheet", response_model=list[ConsumptionSheetRowOut]
)
def get_consumption_sheet(
    cost_sheet_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """J.3: 'auto-generated from all modules -- the procurement working
    document.' A live computed view over this Cost Sheet's lines (J.3
    doesn't ask for a frozen snapshot the way Part T's reports do), backing
    out each line's theoretical (pre-wastage) quantity from its stored
    order quantity and wastage_percent -- 0% wastage (theoretical == order)
    for any line with none recorded, e.g. manual lines and exact-count
    items like fixtures or catch pits."""
    cost_sheet = db.query(CostSheet).filter(CostSheet.id == cost_sheet_id).first()
    if not cost_sheet:
        raise HTTPException(status_code=404, detail="Cost sheet not found")

    lines = db.query(CostSheetLine).filter(CostSheetLine.cost_sheet_id == cost_sheet_id).all()
    po_by_cost_sheet_line_id = _po_lookup_for_cost_sheet(db, cost_sheet_id)

    rows = []
    for line in lines:
        order_qty = float(line.quantity)
        wastage_percent = float(line.wastage_percent) if line.wastage_percent is not None else None
        theoretical_qty = order_qty / (1 + wastage_percent / 100) if wastage_percent else order_qty

        procurement = po_by_cost_sheet_line_id.get(line.id)
        po_line, po, vendor = procurement if procurement else (None, None, None)

        rows.append(
            ConsumptionSheetRowOut(
                id=line.id,
                category=line.category,
                item_name=line.item_name,
                spec=line.spec,
                unit=line.unit,
                theoretical_qty=round(theoretical_qty, 3),
                wastage_percent=wastage_percent,
                order_qty=order_qty,
                rate=float(line.rate),
                amount=order_qty * float(line.rate),
                vendor=vendor.name if vendor else None,
                po_no=po.po_no if po else None,
                delivery_date=po.delivery_date if po else None,
                received_qty=float(po_line.received_qty) if po_line else None,
                balance_qty=(float(po_line.quantity) - float(po_line.received_qty)) if po_line else None,
            )
        )
    return rows


# --------------------------------------------------------------------------
# Estimates (M.1 stage 2)
# --------------------------------------------------------------------------


class EstimateOptionCreate(BaseModel):
    project_sport_id: uuid.UUID
    package: Package
    cost_for_option: float = Field(gt=0)


class EstimateCreate(BaseModel):
    options: list[EstimateOptionCreate] = Field(min_length=1)


class EstimateOptionOut(BaseModel):
    id: uuid.UUID
    estimate_id: uuid.UUID
    project_sport_id: uuid.UUID
    package: Package
    cost_for_option: float | None  # stripped to None for Sales (K.3)
    price_low: float
    price_high: float
    client_status: EstimateOptionClientStatus
    client_demand_note: str | None

    model_config = ConfigDict(from_attributes=True)


class EstimateOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    cost_sheet_id: uuid.UUID
    document_no: str
    revision_major: int
    revision_minor: int
    status: EstimateStatus
    client_status: str  # derived, M.4a #7
    sent_at: datetime | None
    expires_at: datetime | None
    created_by_id: uuid.UUID
    created_at: datetime
    options: list[EstimateOptionOut]

    model_config = ConfigDict(from_attributes=True)


def _derived_client_status(options: list[EstimateOption]) -> str:
    """M.4a #7: 'approved if any option approved; rejected only if all
    rejected'."""
    statuses = {o.client_status for o in options}
    if EstimateOptionClientStatus.APPROVED in statuses:
        return "approved"
    if statuses == {EstimateOptionClientStatus.REJECTED}:
        return "rejected"
    if EstimateOptionClientStatus.DEMAND_RECEIVED in statuses:
        return "demand_received"
    return "pending"


def _estimate_to_out(estimate: Estimate, options: list[EstimateOption], role: str) -> EstimateOut:
    option_outs = []
    for o in options:
        out = EstimateOptionOut.model_validate(o)
        if role == "sales":
            out.cost_for_option = None
        option_outs.append(out)
    return EstimateOut(
        id=estimate.id,
        project_id=estimate.project_id,
        cost_sheet_id=estimate.cost_sheet_id,
        document_no=estimate.document_no,
        revision_major=estimate.revision_major,
        revision_minor=estimate.revision_minor,
        status=estimate.status,
        client_status=_derived_client_status(options),
        sent_at=estimate.sent_at,
        expires_at=estimate.expires_at,
        created_by_id=estimate.created_by_id,
        created_at=estimate.created_at,
        options=option_outs,
    )


@estimates_router.post(
    "/projects/{project_id}/estimates", response_model=EstimateOut, status_code=201
)
def create_estimate(
    project_id: uuid.UUID,
    payload: EstimateCreate,
    db: Session = Depends(get_db),
    # Estimate creation needs a per-option cost figure (K.3-protected), so
    # this endpoint -- unlike M.4's "Sales/PM/Director may create" -- is
    # PM/Director only until a real per-sport cost breakdown exists that
    # would let Sales create one without ever seeing the number.
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """M.2 rule 1: 'An Estimate cannot be created until its Cost Sheet is
    Verified' -- exception: 'when a stage is skipped under rule 3, the
    auto-generated Cost Sheet is Unverified, which permits creation of
    the next stage' -- so Unverified counts too, with the consequence
    (Director-only Quotation release, cost_basis_unverified) carried
    downstream from there rather than blocked here."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    cost_sheet = (
        db.query(CostSheet)
        .filter(
            CostSheet.project_id == project_id,
            CostSheet.status.in_((CostSheetStatus.VERIFIED, CostSheetStatus.UNVERIFIED)),
        )
        .order_by(CostSheet.revision_major.desc())
        .first()
    )
    if not cost_sheet:
        raise HTTPException(status_code=400, detail="Project has no Verified (or skip-generated Unverified) cost sheet")

    client = db.query(Client).filter(Client.id == project.client_id).first()
    if client.blacklist_flag:
        raise HTTPException(
            status_code=400, detail="This client is blacklisted (Part O) -- new Estimates are blocked"
        )
    policy = _get_margin_policy(db, client.type)
    gst_rate_percent = get_gst_rate_percent(db)
    price_range_percent = _get_setting_float(db, "estimate_price_range_percent", PRICE_RANGE_PERCENT_DEFAULT)

    estimate = Estimate(
        project_id=project_id,
        cost_sheet_id=cost_sheet.id,
        document_no=_document_no(project.project_no, "EST", 1),
        created_by_id=current_user.id,
    )
    db.add(estimate)
    db.flush()

    options = []
    for option_payload in payload.options:
        project_sport = (
            db.query(ProjectSport)
            .filter(ProjectSport.id == option_payload.project_sport_id, ProjectSport.project_id == project_id)
            .first()
        )
        if not project_sport:
            raise HTTPException(
                status_code=404, detail=f"Sport selection {option_payload.project_sport_id} not on this project"
            )

        # K.2 / M.1: each option is priced at ITS OWN target margin -- a
        # sport-type floor override (Director-set) replaces the client
        # floor only for that sport, so options for different sports in
        # the same Estimate can carry different targets.
        _, target = effective_floor_and_target(db, policy, project_sport.sport_id)
        selling_ex_gst = option_payload.cost_for_option / (1 - target / 100)
        selling_incl_gst = selling_ex_gst * (1 + gst_rate_percent / 100)
        option = EstimateOption(
            estimate_id=estimate.id,
            project_sport_id=option_payload.project_sport_id,
            package=option_payload.package,
            cost_for_option=option_payload.cost_for_option,
            price_low=selling_incl_gst * (1 - price_range_percent / 100),
            price_high=selling_incl_gst * (1 + price_range_percent / 100),
        )
        db.add(option)
        options.append(option)

    db.commit()
    for o in options:
        db.refresh(o)
    return _estimate_to_out(estimate, options, current_user.role.value)


@estimates_router.get("/projects/{project_id}/estimates", response_model=list[EstimateOut])
def list_estimates(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    estimates = db.query(Estimate).filter(Estimate.project_id == project_id).all()
    out = []
    for e in estimates:
        options = db.query(EstimateOption).filter(EstimateOption.estimate_id == e.id).all()
        out.append(_estimate_to_out(e, options, current_user.role.value))
    return out


@estimates_router.get("/estimates/{estimate_id}", response_model=EstimateOut)
def get_estimate(
    estimate_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    options = db.query(EstimateOption).filter(EstimateOption.estimate_id == estimate.id).all()
    return _estimate_to_out(estimate, options, current_user.role.value)


@estimates_router.post("/estimates/{estimate_id}/send", response_model=EstimateOut)
def send_estimate(
    estimate_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    """M.1: first send -> Sent, starts the 15-day validity (M.7.2 rule 3)."""
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    if estimate.status != EstimateStatus.DRAFT:
        raise HTTPException(status_code=400, detail=f"Cannot send an estimate in {estimate.status.value} status")

    validity_days = _get_setting_int(db, "estimate_validity_days", ESTIMATE_VALIDITY_DAYS_DEFAULT)
    estimate.status = EstimateStatus.SENT
    estimate.sent_at = datetime.now(UTC)
    estimate.expires_at = estimate.sent_at + timedelta(days=validity_days)
    db.commit()
    options = db.query(EstimateOption).filter(EstimateOption.estimate_id == estimate.id).all()
    db.refresh(estimate)
    return _estimate_to_out(estimate, options, current_user.role.value)


class EstimateOptionStatusUpdate(BaseModel):
    client_status: EstimateOptionClientStatus
    client_demand_note: str | None = None
    waive_evidence_reason: str | None = None


@estimates_router.patch(
    "/estimates/{estimate_id}/options/{option_id}/client-status", response_model=EstimateOptionOut
)
def update_option_client_status(
    estimate_id: uuid.UUID,
    option_id: uuid.UUID,
    payload: EstimateOptionStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    """M.4: 'record Client approved / demand / rejected' -- Sales included.
    M.3: an option can't move to Client approved without an
    approval_evidence attachment on the Estimate, unless PM/Director waives
    it. M.5 names "approvals" as an audit log category -- logged below."""
    option = (
        db.query(EstimateOption)
        .filter(EstimateOption.id == option_id, EstimateOption.estimate_id == estimate_id)
        .first()
    )
    if not option:
        raise HTTPException(status_code=404, detail="Estimate option not found")

    if payload.client_status == EstimateOptionClientStatus.APPROVED:
        _enforce_approval_evidence(
            db, DocumentType.ESTIMATE, estimate_id, current_user, payload.waive_evidence_reason, request=request
        )

    old_status = option.client_status
    option.client_status = payload.client_status
    option.client_demand_note = payload.client_demand_note
    write_audit_log_entry(
        db, current_user, "estimate_option", option.id, "client_status",
        old_value=old_status.value, new_value=payload.client_status.value, request=request,
    )
    db.commit()
    db.refresh(option)
    out = EstimateOptionOut.model_validate(option)
    if current_user.role.value == "sales":
        out.cost_for_option = None
    return out


# --------------------------------------------------------------------------
# Quotations (M.1 stage 3)
# --------------------------------------------------------------------------


class QuotationCreate(BaseModel):
    estimate_id: uuid.UUID
    included_option_ids: list[uuid.UUID] = Field(min_length=1)
    discount_type: str | None = None
    discount_value: float = Field(default=0.0, ge=0)


class QuotationOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    estimate_id: uuid.UUID
    document_no: str
    revision_major: int
    revision_minor: int
    status: QuotationStatus
    cost_total: float | None  # stripped for Sales (K.3)
    target_margin_percent: float | None
    floor_margin_percent: float | None
    selling_price_ex_gst: float
    discount_type: str | None
    discount_value: float
    discount_amount: float
    selling_after_discount: float
    margin_percent: float | None  # stripped for Sales
    below_floor: bool | None  # stripped for Sales
    gst_amount: float
    quotation_total: float
    cost_basis_unverified: bool
    released_by_id: uuid.UUID | None
    released_at: datetime | None
    sent_at: datetime | None
    expires_at: datetime | None
    won_lost_reason: str | None
    created_by_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def _quotation_to_out(quotation: Quotation, role: str) -> QuotationOut:
    out = QuotationOut.model_validate(quotation)
    if role == "sales":
        out.cost_total = None
        out.target_margin_percent = None
        out.floor_margin_percent = None
        out.margin_percent = None
        out.below_floor = None
    return out


@quotations_router.post(
    "/projects/{project_id}/quotations", response_model=QuotationOut, status_code=201
)
def create_quotation(
    project_id: uuid.UUID,
    payload: QuotationCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    """M.2 rule 2: needs at least one option Client approved or Client
    demand received. M.2 rule 11: covers the approved subset of sports."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    estimate = (
        db.query(Estimate).filter(Estimate.id == payload.estimate_id, Estimate.project_id == project_id).first()
    )
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found on this project")

    included_options = []
    for option_id in payload.included_option_ids:
        option = (
            db.query(EstimateOption)
            .filter(EstimateOption.id == option_id, EstimateOption.estimate_id == estimate.id)
            .first()
        )
        if not option:
            raise HTTPException(status_code=404, detail=f"Estimate option {option_id} not found on this estimate")
        if option.client_status not in (
            EstimateOptionClientStatus.APPROVED,
            EstimateOptionClientStatus.DEMAND_RECEIVED,
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Option {option_id} is not Client approved or Client demand received",
            )
        included_options.append(option)

    cost_sheet = db.query(CostSheet).filter(CostSheet.id == estimate.cost_sheet_id).first()
    client = db.query(Client).filter(Client.id == project.client_id).first()
    policy = _get_margin_policy(db, client.type)

    # K.2: "Multi-sport project: floor = cost-weighted average of the
    # applicable floors" -- each included option contributes its own
    # effective (sport-override-or-client) floor, weighted by its own cost.
    cost_and_sport_ids = [
        (
            float(o.cost_for_option),
            db.query(ProjectSport).filter(ProjectSport.id == o.project_sport_id).first().sport_id,
        )
        for o in included_options
    ]
    cost_total = sum(cost for cost, _ in cost_and_sport_ids)
    floor, target = cost_weighted_floor_and_target(db, policy, cost_and_sport_ids)
    pricing = compute_pricing(db, cost_total, floor, target, payload.discount_type, payload.discount_value)

    quotation = Quotation(
        project_id=project_id,
        estimate_id=estimate.id,
        document_no=_document_no(project.project_no, "NPQ", 1),
        cost_total=cost_total,
        target_margin_percent=pricing.target_margin_percent,
        floor_margin_percent=pricing.floor_margin_percent,
        selling_price_ex_gst=pricing.selling_price_ex_gst,
        discount_type=payload.discount_type,
        discount_value=payload.discount_value,
        discount_amount=pricing.discount_amount,
        selling_after_discount=pricing.selling_after_discount,
        margin_percent=pricing.margin_percent,
        below_floor=pricing.below_floor,
        gst_amount=pricing.gst_amount,
        quotation_total=pricing.quotation_total,
        cost_basis_unverified=(cost_sheet.status != CostSheetStatus.VERIFIED),
        created_by_id=current_user.id,
    )
    db.add(quotation)
    db.flush()
    for option in included_options:
        db.add(QuotationLine(quotation_id=quotation.id, estimate_option_id=option.id))

    if payload.discount_value:
        # M.5 names "discounts" as an audit log category.
        write_audit_log_entry(
            db, current_user, "quotation", quotation.id, "discount_value",
            old_value=0, new_value=payload.discount_value,
            reason=f"discount_type={payload.discount_type}", request=request,
        )

    db.commit()
    db.refresh(quotation)
    return _quotation_to_out(quotation, current_user.role.value)


@quotations_router.get("/projects/{project_id}/quotations", response_model=list[QuotationOut])
def list_quotations(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    quotations = db.query(Quotation).filter(Quotation.project_id == project_id).all()
    return [_quotation_to_out(q, current_user.role.value) for q in quotations]


@quotations_router.get("/quotations/{quotation_id}", response_model=QuotationOut)
def get_quotation(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return _quotation_to_out(quotation, current_user.role.value)


@quotations_router.post("/quotations/{quotation_id}/release", response_model=QuotationOut)
def release_quotation(
    quotation_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """M.1: 'PM or Director release; Director if discount below floor or
    if the underlying Cost Sheet is Unverified.'"""
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if quotation.status != QuotationStatus.DRAFT:
        raise HTTPException(status_code=400, detail=f"Cannot release a quotation in {quotation.status.value} status")

    project = db.query(Project).filter(Project.id == quotation.project_id).first()
    client = db.query(Client).filter(Client.id == project.client_id).first()
    if client.overdue_flag:
        raise HTTPException(
            status_code=400,
            detail="This client is overdue (Part O) -- Quotation release is blocked until a Director clears it",
        )

    needs_director = quotation.below_floor or quotation.cost_basis_unverified
    if needs_director and current_user.role.value != "director":
        raise HTTPException(
            status_code=403,
            detail="Below-floor discount or unverified cost basis requires Director release",
        )

    if needs_director:
        # M.5 names "discounts" as an audit log category; a below-floor
        # release is exactly the case where a discount pushed margin past
        # the point that needs Director sign-off (K.1 step 10 / K.2).
        why = []
        if quotation.below_floor:
            why.append("below_floor")
        if quotation.cost_basis_unverified:
            why.append("cost_basis_unverified")
        write_audit_log_entry(
            db, current_user, "quotation", quotation.id, "status",
            old_value=quotation.status.value, new_value=QuotationStatus.RELEASED.value,
            reason=f"Director release required: {', '.join(why)}", request=request,
        )

    quotation.status = QuotationStatus.RELEASED
    quotation.released_by_id = current_user.id
    quotation.released_at = datetime.now(UTC)
    db.commit()
    db.refresh(quotation)
    return _quotation_to_out(quotation, current_user.role.value)


@quotations_router.post("/quotations/{quotation_id}/send", response_model=QuotationOut)
def send_quotation(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    """M.1: 'Released -> Sent', starts the 30-day validity."""
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if quotation.status != QuotationStatus.RELEASED:
        raise HTTPException(status_code=400, detail="Only a Released quotation can be sent")

    validity_days = _get_setting_int(db, "quotation_validity_days", QUOTATION_VALIDITY_DAYS_DEFAULT)
    quotation.status = QuotationStatus.SENT
    quotation.sent_at = datetime.now(UTC)
    quotation.expires_at = quotation.sent_at + timedelta(days=validity_days)
    db.commit()
    db.refresh(quotation)
    return _quotation_to_out(quotation, current_user.role.value)


class WonLostRequest(BaseModel):
    reason: str | None = None
    waive_evidence_reason: str | None = None


@quotations_router.post("/quotations/{quotation_id}/mark-won", response_model=QuotationOut)
def mark_quotation_won(
    quotation_id: uuid.UUID,
    payload: WonLostRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    """M.2 rule 3: 'cannot be marked Won until the Cost Sheet is verified.'
    M.3: needs an approval_evidence attachment (Formal specifically for
    Government/Tender or quotations >= Rs 25L) unless PM/Director waives
    it."""
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if quotation.status != QuotationStatus.SENT:
        raise HTTPException(status_code=400, detail="Only a Sent quotation can be marked Won")
    if quotation.cost_basis_unverified:
        raise HTTPException(status_code=400, detail="Cannot mark Won while the cost basis is unverified")

    project = db.query(Project).filter(Project.id == quotation.project_id).first()
    require_formal = project.tender_mode or float(quotation.quotation_total) >= FORMAL_EVIDENCE_REQUIRED_ABOVE_RS
    _enforce_approval_evidence(
        db, DocumentType.QUOTATION, quotation_id, current_user, payload.waive_evidence_reason,
        require_formal=require_formal, request=request,
    )

    quotation.status = QuotationStatus.WON
    quotation.won_lost_reason = payload.reason
    db.commit()
    db.refresh(quotation)
    return _quotation_to_out(quotation, current_user.role.value)


@quotations_router.post("/quotations/{quotation_id}/mark-lost", response_model=QuotationOut)
def mark_quotation_lost(
    quotation_id: uuid.UUID,
    payload: WonLostRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if quotation.status not in (QuotationStatus.RELEASED, QuotationStatus.SENT):
        raise HTTPException(status_code=400, detail="Only a Released or Sent quotation can be marked Lost")

    quotation.status = QuotationStatus.LOST
    quotation.won_lost_reason = payload.reason
    db.commit()
    db.refresh(quotation)
    return _quotation_to_out(quotation, current_user.role.value)
