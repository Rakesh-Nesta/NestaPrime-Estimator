import hashlib
import io
import json
import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException
from openpyxl import Workbook
from pydantic import BaseModel, ConfigDict
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import Estimate, EstimateOption, EstimateOptionClientStatus, Quotation, QuotationLine
from app.models.report import Report, ReportStatus, ReportType
from app.models.setting import Override
from app.models.sport import ProjectSport, Sport
from app.models.user import User
from app.services import ai_content
from app.xlsx_utils import xlsx_header_row as _header_row
from app.xlsx_utils import xlsx_response as _xlsx_response

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

    # M.2 rule 9: "an Estimate can also close as 'Client rejected' with a
    # reason ... so lost deals are counted at the estimate stage, not only
    # at quotation." EstimateOption has no status-change timestamp of its
    # own (same simplification as Won/Lost below), so this counts rejected
    # options on the estimates-sent-in-period cohort as its period anchor,
    # rather than a "rejected in period" date that doesn't exist.
    sent_estimate_ids = [e.id for e in estimates_sent]
    rejected_by_reason: dict[str, int] = {}
    if sent_estimate_ids:
        rejected_options = (
            db.query(EstimateOption)
            .filter(
                EstimateOption.estimate_id.in_(sent_estimate_ids),
                EstimateOption.client_status == EstimateOptionClientStatus.REJECTED,
            )
            .all()
        )
        for option in rejected_options:
            key = option.rejection_reason.value if option.rejection_reason else "unspecified"
            rejected_by_reason[key] = rejected_by_reason.get(key, 0) + 1

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
            "rejected_by_reason": rejected_by_reason,
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


class ReportSummaryOut(BaseModel):
    summary: str


@router.post("/{report_id}/summary", response_model=ReportSummaryOut)
def summarize_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ALL_REPORT_ROLES)),
):
    """Amendment 13 (Section 12): a narrative paragraph over this
    report's own already-computed content -- never persisted, never
    changes what's stored or exported. Same gate as GET .../{report_id}
    (T.2 rule 3: role gate matches the underlying data), since a summary
    reveals nothing the report itself doesn't already show."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if current_user.role.value not in VISIBLE_ROLES[report.report_type]:
        raise HTTPException(status_code=403, detail="This role cannot view this report type")

    prompt = (
        f"Write a brief narrative summary (3-5 sentences, plain text, no headings) of this "
        f"{report.report_type.value.replace('_', ' ')} report for {report.period_from.isoformat()} to "
        f"{report.period_to.isoformat()}, suitable for a Director to forward as-is. Call out anything "
        "that stands out (e.g. below-floor margins, a concentration of overrides, a slow period) -- "
        "don't just restate every number.\n\n" + json.dumps(report.content)
    )
    try:
        summary = ai_content.generate_text(prompt, max_tokens=500)
    except ai_content.AiContentError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ReportSummaryOut(summary=summary)


def _pipeline_to_xlsx(wb: Workbook, content: dict) -> None:
    est = content.get("estimates", {})
    ws = wb.active
    ws.title = "Summary"
    _header_row(ws, ["Metric", "Value"])
    ws.append(["Period from", content.get("period_from")])
    ws.append(["Period to", content.get("period_to")])
    ws.append(["Estimates created", est.get("created", 0)])
    ws.append(["Estimates sent", est.get("sent", 0)])
    quo = content.get("quotations_released_in_period", {})
    ws.append(["Quotations released", quo.get("count", 0)])
    ws.append(["Total amount", quo.get("total_amount", 0)])

    ws2 = wb.create_sheet("Rejected by reason")
    _header_row(ws2, ["Reason", "Count"])
    for reason, count in est.get("rejected_by_reason", {}).items():
        ws2.append([reason, count])

    ws3 = wb.create_sheet("Quotations by sport")
    _header_row(ws3, ["Sport", "Count", "Total amount"])
    for sport, row in quo.get("by_sport", {}).items():
        ws3.append([sport, row.get("count", 0), row.get("total_amount", 0)])

    ws4 = wb.create_sheet("Quotations by status")
    _header_row(ws4, ["Status", "Count"])
    for status, count in quo.get("by_status", {}).items():
        ws4.append([status, count])

    ws5 = wb.create_sheet("Quotations by released by")
    _header_row(ws5, ["Released by", "Count", "Total amount"])
    for user_name, row in quo.get("by_released_by", {}).items():
        ws5.append([user_name, row.get("count", 0), row.get("total_amount", 0)])


def _margin_to_xlsx(wb: Workbook, content: dict) -> None:
    ws = wb.active
    ws.title = "Quotations"
    _header_row(
        ws,
        [
            "Document no.", "Project ID", "Cost total", "Selling (ex GST)", "Discount", "Selling after discount",
            "Margin %", "Floor margin %", "Below floor", "Cost basis unverified", "Released at", "Released by",
        ],
    )
    for q in content.get("quotations", []):
        ws.append(
            [
                q.get("document_no"), q.get("project_id"), q.get("cost_total"), q.get("selling_price_ex_gst"),
                q.get("discount_amount"), q.get("selling_after_discount"), q.get("margin_percent"),
                q.get("floor_margin_percent"), q.get("below_floor"), q.get("cost_basis_unverified"),
                q.get("released_at"), q.get("released_by"),
            ]
        )

    summary = content.get("summary", {})
    ws2 = wb.create_sheet("Summary")
    _header_row(ws2, ["Metric", "Value"])
    ws2.append(["Period from", content.get("period_from")])
    ws2.append(["Period to", content.get("period_to")])
    ws2.append(["Count", summary.get("count", 0)])
    ws2.append(["Total cost", summary.get("total_cost", 0)])
    ws2.append(["Total selling", summary.get("total_selling", 0)])
    ws2.append(["Average margin %", summary.get("average_margin_percent")])
    ws2.append(["Below floor count", summary.get("below_floor_count", 0)])


def _override_summary_to_xlsx(wb: Workbook, content: dict) -> None:
    ws = wb.active
    ws.title = "Overrides"
    _header_row(ws, ["Setting key", "Override count", "Most common value", "Document types"])
    for row in content.get("rows", []):
        ws.append(
            [
                row.get("setting_key"), row.get("override_count"), row.get("most_common_override_value"),
                ", ".join(row.get("document_types", [])),
            ]
        )

    ws2 = wb.create_sheet("Summary")
    _header_row(ws2, ["Metric", "Value"])
    ws2.append(["Period from", content.get("period_from")])
    ws2.append(["Period to", content.get("period_to")])
    ws2.append(["Total overrides", content.get("total_overrides", 0)])


_XLSX_BUILDERS = {
    ReportType.PIPELINE: _pipeline_to_xlsx,
    ReportType.MARGIN: _margin_to_xlsx,
    ReportType.OVERRIDE_SUMMARY: _override_summary_to_xlsx,
}


@router.get("/{report_id}/export")
def export_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ALL_REPORT_ROLES)),
):
    """A formatted Excel workbook over this report's own content --
    same gate as GET .../{report_id}. This is the report's real,
    shareable form; the on-screen raw JSON view is an internal debugging
    aid, not something meant to be handed to anyone."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if current_user.role.value not in VISIBLE_ROLES[report.report_type]:
        raise HTTPException(status_code=403, detail="This role cannot view this report type")

    wb = Workbook()
    _XLSX_BUILDERS[report.report_type](wb, report.content)
    filename = f"{report.report_type.value}_{report.period_from.isoformat()}_{report.period_to.isoformat()}.xlsx"
    return _xlsx_response(wb, filename)


def _kv_table(styles, rows: list[tuple]) -> Table:
    from app.api.pdf_documents import _TABLE_GRID  # local: avoids a circular import at module load time

    data = [[Paragraph(str(k), styles["Normal"]), Paragraph(str(v), styles["Normal"])] for k, v in rows]
    t = Table(data, colWidths=[60 * mm, 100 * mm])
    t.setStyle(_TABLE_GRID)
    return t


def _rows_table(styles, headers: list[str], rows: list[list]) -> Table:
    from app.api.pdf_documents import _TABLE_GRID  # local: avoids a circular import at module load time

    data = [[Paragraph(h, styles["Normal"]) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(cell), styles["Normal"]) for cell in row])
    t = Table(data, repeatRows=1)
    t.setStyle(_TABLE_GRID)
    return t


def _pipeline_to_pdf_story(styles, content: dict) -> list:
    est = content.get("estimates", {})
    quo = content.get("quotations_released_in_period", {})
    story = [
        _kv_table(
            styles,
            [
                ("Period", f"{content.get('period_from')} to {content.get('period_to')}"),
                ("Estimates created", est.get("created", 0)),
                ("Estimates sent", est.get("sent", 0)),
                ("Quotations released", quo.get("count", 0)),
                ("Total amount", quo.get("total_amount", 0)),
            ],
        ),
        Spacer(1, 6 * mm),
    ]
    if quo.get("by_sport"):
        story.append(Paragraph("Quotations by sport", styles["SectionHeading"]))
        story.append(
            _rows_table(
                styles, ["Sport", "Count", "Total amount"],
                [[s, r.get("count", 0), r.get("total_amount", 0)] for s, r in quo["by_sport"].items()],
            )
        )
        story.append(Spacer(1, 4 * mm))
    if est.get("rejected_by_reason"):
        story.append(Paragraph("Estimates rejected by reason", styles["SectionHeading"]))
        story.append(_rows_table(styles, ["Reason", "Count"], list(est["rejected_by_reason"].items())))
    return story


def _margin_to_pdf_story(styles, content: dict) -> list:
    summary = content.get("summary", {})
    story = [
        _kv_table(
            styles,
            [
                ("Period", f"{content.get('period_from')} to {content.get('period_to')}"),
                ("Count", summary.get("count", 0)),
                ("Total cost", summary.get("total_cost", 0)),
                ("Total selling", summary.get("total_selling", 0)),
                ("Average margin %", summary.get("average_margin_percent")),
                ("Below floor count", summary.get("below_floor_count", 0)),
            ],
        ),
        Spacer(1, 6 * mm),
    ]
    quotations = content.get("quotations", [])
    if quotations:
        story.append(Paragraph("Quotations", styles["SectionHeading"]))
        story.append(
            _rows_table(
                styles, ["Document no.", "Margin %", "Below floor", "Selling after discount"],
                [
                    [q.get("document_no"), q.get("margin_percent"), q.get("below_floor"), q.get("selling_after_discount")]
                    for q in quotations
                ],
            )
        )
    return story


def _override_summary_to_pdf_story(styles, content: dict) -> list:
    story = [
        _kv_table(
            styles,
            [
                ("Period", f"{content.get('period_from')} to {content.get('period_to')}"),
                ("Total overrides", content.get("total_overrides", 0)),
            ],
        ),
        Spacer(1, 6 * mm),
    ]
    rows = content.get("rows", [])
    if rows:
        story.append(Paragraph("Overrides by setting", styles["SectionHeading"]))
        story.append(
            _rows_table(
                styles, ["Setting key", "Override count", "Most common value", "Document types"],
                [
                    [r.get("setting_key"), r.get("override_count"), r.get("most_common_override_value"),
                     ", ".join(r.get("document_types", []))]
                    for r in rows
                ],
            )
        )
    return story


_PDF_BUILDERS = {
    ReportType.PIPELINE: _pipeline_to_pdf_story,
    ReportType.MARGIN: _margin_to_pdf_story,
    ReportType.OVERRIDE_SUMMARY: _override_summary_to_pdf_story,
}


@router.get("/{report_id}/pdf")
def export_report_pdf(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ALL_REPORT_ROLES)),
):
    """A formatted PDF over this report's own content -- same gate and
    same "this is the shareable form, not the raw JSON" reasoning as
    GET .../export (Excel)."""
    from app.api.pdf_documents import _pdf_response, _styles  # local: avoids a circular import at module load time

    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if current_user.role.value not in VISIBLE_ROLES[report.report_type]:
        raise HTTPException(status_code=403, detail="This role cannot view this report type")

    styles = _styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=(210 * mm, 297 * mm), topMargin=15 * mm, bottomMargin=15 * mm)
    title = f"{report.report_type.value.replace('_', ' ').title()} Report"
    story = [
        Paragraph("NESTAPRIME SPORTS INFRASTRUCTURE", styles["CompanyHeader"]),
        Paragraph(title, styles["DocTitle"]),
        Spacer(1, 4 * mm),
        *_PDF_BUILDERS[report.report_type](styles, report.content),
    ]
    doc.build(story)
    filename = f"{report.report_type.value}_{report.period_from.isoformat()}_{report.period_to.isoformat()}.pdf"
    return _pdf_response(buffer, filename)


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
