import hashlib
import json
import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import Estimate, EstimateOption, Quotation, QuotationLine
from app.models.report import Report, ReportStatus, ReportType
from app.models.setting import Override
from app.models.sport import ProjectSport, Sport
from app.models.user import User

router = APIRouter(prefix="/reports", tags=["reports"])

# T.2 rule 3: "role gate matches the underlying data, not a new permission."
# Pipeline carries quotation totals Sales already sees on the documents
# themselves; Margin carries cost/margin, which K.3 restricts to PM/Director.
# Override Summary is narrower still -- Q.2 rule 2 names only the Director
# ("The Director sees a monthly 'override report'"), not PM.
VISIBLE_ROLES = {
    ReportType.PIPELINE: ("sales", "pm", "director"),
    ReportType.MARGIN: ("pm", "director"),
    ReportType.OVERRIDE_SUMMARY: ("director",),
}
ALL_REPORT_ROLES = ("sales", "pm", "director")


def _in_period(value: datetime | date | None, period_from: date, period_to: date) -> bool:
    if value is None:
        return False
    value_date = value.date() if isinstance(value, datetime) else value
    return period_from <= value_date <= period_to


def _hash_content(content: dict) -> str:
    canonical = json.dumps(content, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sports_for_quotation(db: Session, quotation_id: uuid.UUID) -> list[str]:
    rows = (
        db.query(Sport.name)
        .join(ProjectSport, ProjectSport.sport_id == Sport.id)
        .join(EstimateOption, EstimateOption.project_sport_id == ProjectSport.id)
        .join(QuotationLine, QuotationLine.estimate_option_id == EstimateOption.id)
        .filter(QuotationLine.quotation_id == quotation_id)
        .all()
    )
    return [r[0] for r in rows]


def _build_pipeline_content(db: Session, period_from: date, period_to: date) -> dict:
    """T.1 Quotation Pipeline: estimates created/sent, and -- for the cohort
    of quotations released in the period -- counts/totals by current status,
    by sport and by who released. Won/Lost/Expired have no dedicated
    transition timestamp in this schema (only released_at/sent_at exist), so
    this reports their *current* status for the released-in-period cohort
    rather than a separate per-status date -- documented simplification,
    same spirit as CostSheet's own cost-buildup note."""
    estimates = db.query(Estimate).all()
    estimates_created = [e for e in estimates if _in_period(e.created_at, period_from, period_to)]
    estimates_sent = [e for e in estimates if _in_period(e.sent_at, period_from, period_to)]

    quotations = db.query(Quotation).all()
    released_in_period = [q for q in quotations if _in_period(q.released_at, period_from, period_to)]

    by_status: dict[str, int] = {}
    by_sport: dict[str, dict[str, float]] = {}
    by_released_by: dict[str, dict[str, float]] = {}
    user_names: dict[uuid.UUID, str] = {}
    total_amount = 0.0

    for q in released_in_period:
        status_key = q.status.value
        by_status[status_key] = by_status.get(status_key, 0) + 1
        amount = float(q.quotation_total)
        total_amount += amount

        if q.released_by_id not in user_names:
            user = db.query(User).filter(User.id == q.released_by_id).first()
            user_names[q.released_by_id] = user.name if user else "Unknown"
        released_by_name = user_names[q.released_by_id]
        bucket = by_released_by.setdefault(released_by_name, {"count": 0, "total_amount": 0.0})
        bucket["count"] += 1
        bucket["total_amount"] += amount

        # A multi-sport quotation's frozen selling price isn't decomposed
        # per line in this schema (M.1's simplification), so each sport the
        # quotation covers is credited the full quotation amount here --
        # counts by sport are exact, totals by sport are an approximation.
        for sport_name in _sports_for_quotation(db, q.id):
            sport_bucket = by_sport.setdefault(sport_name, {"count": 0, "total_amount": 0.0})
            sport_bucket["count"] += 1
            sport_bucket["total_amount"] += amount

    return {
        "period_from": period_from.isoformat(),
        "period_to": period_to.isoformat(),
        "estimates": {
            "created": len(estimates_created),
            "sent": len(estimates_sent),
        },
        "quotations_released_in_period": {
            "count": len(released_in_period),
            "total_amount": round(total_amount, 2),
            "by_status": by_status,
            "by_sport": by_sport,
            "by_released_by": by_released_by,
        },
    }


def _build_margin_content(db: Session, period_from: date, period_to: date) -> dict:
    """T.1 Margin Performance: every quotation released in the month, its
    cost/selling/margin figures and floor comparison. K.3: PM/Director only."""
    quotations = db.query(Quotation).all()
    released_in_period = [q for q in quotations if _in_period(q.released_at, period_from, period_to)]

    lines = []
    below_floor_count = 0
    total_cost = 0.0
    total_selling = 0.0
    margin_sum = 0.0

    for q in released_in_period:
        released_by = db.query(User).filter(User.id == q.released_by_id).first()
        cost_total = float(q.cost_total)
        selling_after_discount = float(q.selling_after_discount)
        margin_percent = float(q.margin_percent)
        total_cost += cost_total
        total_selling += selling_after_discount
        margin_sum += margin_percent
        if q.below_floor:
            below_floor_count += 1
        lines.append(
            {
                "document_no": q.document_no,
                "project_id": str(q.project_id),
                "cost_total": cost_total,
                "selling_price_ex_gst": float(q.selling_price_ex_gst),
                "discount_amount": float(q.discount_amount),
                "selling_after_discount": selling_after_discount,
                "margin_percent": margin_percent,
                "floor_margin_percent": float(q.floor_margin_percent),
                "below_floor": q.below_floor,
                "cost_basis_unverified": q.cost_basis_unverified,
                "released_at": q.released_at.isoformat() if q.released_at else None,
                "released_by": released_by.name if released_by else None,
            }
        )

    count = len(released_in_period)
    return {
        "period_from": period_from.isoformat(),
        "period_to": period_to.isoformat(),
        "quotations": lines,
        "summary": {
            "count": count,
            "total_cost": round(total_cost, 2),
            "total_selling": round(total_selling, 2),
            "average_margin_percent": round(margin_sum / count, 2) if count else None,
            "below_floor_count": below_floor_count,
        },
    }


def _build_override_summary_content(db: Session, period_from: date, period_to: date) -> dict:
    """Q.2 rule 2: 'The Director sees a monthly "override report" (which
    settings are overridden most often -> candidates for a master
    update).' Every Override row created in the period, grouped by
    setting_key and ranked by how often it was overridden -- the most-
    overridden setting first, since that is the one most worth promoting
    to a new master value. most_common_override_value is exactly that
    candidate: whichever override_value was chosen most often for that
    setting in the period."""
    overrides = db.query(Override).all()
    in_period = [o for o in overrides if _in_period(o.created_at, period_from, period_to)]

    by_key: dict[str, dict] = {}
    for o in in_period:
        bucket = by_key.setdefault(
            o.setting_key, {"count": 0, "value_counts": {}, "document_types": set()}
        )
        bucket["count"] += 1
        bucket["value_counts"][o.override_value] = bucket["value_counts"].get(o.override_value, 0) + 1
        bucket["document_types"].add(o.document_type.value)

    rows = []
    for setting_key, bucket in by_key.items():
        most_common_value = max(bucket["value_counts"].items(), key=lambda kv: kv[1])[0]
        rows.append(
            {
                "setting_key": setting_key,
                "override_count": bucket["count"],
                "value_breakdown": bucket["value_counts"],
                "most_common_override_value": most_common_value,
                "document_types": sorted(bucket["document_types"]),
            }
        )
    rows.sort(key=lambda r: r["override_count"], reverse=True)

    return {
        "period_from": period_from.isoformat(),
        "period_to": period_to.isoformat(),
        "total_overrides": len(in_period),
        "rows": rows,
    }


SOURCE_TABLES = {
    ReportType.PIPELINE: "ESTIMATES, QUOTATIONS",
    ReportType.MARGIN: "COST_SHEETS, QUOTATIONS, OVERRIDES",
    ReportType.OVERRIDE_SUMMARY: "OVERRIDES",
}


class ReportGenerate(BaseModel):
    report_type: ReportType
    period_from: date
    period_to: date


class ReportOut(BaseModel):
    id: uuid.UUID
    report_type: ReportType
    period_from: date
    period_to: date
    status: ReportStatus
    source_tables: str
    file_hash: str
    content: dict
    generated_by_id: uuid.UUID
    released_by_id: uuid.UUID | None
    released_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.post("/generate", response_model=ReportOut, status_code=201)
def generate_report(
    payload: ReportGenerate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ALL_REPORT_ROLES)),
):
    if payload.period_from > payload.period_to:
        raise HTTPException(status_code=422, detail="period_from must not be after period_to")

    allowed_roles = VISIBLE_ROLES[payload.report_type]
    if current_user.role.value not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{current_user.role.value}' cannot generate a {payload.report_type.value} report",
        )

    if payload.report_type == ReportType.PIPELINE:
        content = _build_pipeline_content(db, payload.period_from, payload.period_to)
        status_ = ReportStatus.RELEASED  # T.2 rule 4: nothing to gate, open to Sales already
    elif payload.report_type == ReportType.MARGIN:
        content = _build_margin_content(db, payload.period_from, payload.period_to)
        status_ = ReportStatus.DRAFT  # T.2 rule 4: Director must release Director/CA-only content
    else:
        content = _build_override_summary_content(db, payload.period_from, payload.period_to)
        status_ = ReportStatus.DRAFT  # same governance-content gate as Margin

    report = Report(
        report_type=payload.report_type,
        period_from=payload.period_from,
        period_to=payload.period_to,
        source_tables=SOURCE_TABLES[payload.report_type],
        content=content,
        file_hash=_hash_content(content),
        status=status_,
        generated_by_id=current_user.id,
        released_at=datetime.now(UTC) if status_ == ReportStatus.RELEASED else None,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("", response_model=list[ReportOut])
def list_reports(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ALL_REPORT_ROLES)),
):
    visible_types = [t for t, roles in VISIBLE_ROLES.items() if current_user.role.value in roles]
    return (
        db.query(Report)
        .filter(Report.report_type.in_(visible_types))
        .order_by(Report.created_at.desc())
        .all()
    )


@router.get("/{report_id}", response_model=ReportOut)
def get_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ALL_REPORT_ROLES)),
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if current_user.role.value not in VISIBLE_ROLES[report.report_type]:
        raise HTTPException(status_code=403, detail="This role cannot view this report type")
    return report


@router.post("/{report_id}/release", response_model=ReportOut)
def release_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("director")),
):
    """T.2 rule 4: Director-only, mirrors the Cost Sheet verification gate."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status != ReportStatus.DRAFT:
        raise HTTPException(status_code=400, detail=f"Cannot release a report in {report.status.value} status")

    report.status = ReportStatus.RELEASED
    report.released_by_id = current_user.id
    report.released_at = datetime.now(UTC)
    db.commit()
    db.refresh(report)
    return report
