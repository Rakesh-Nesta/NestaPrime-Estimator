"""Amendment 50 (Section 54): everything the Payments header shows is derived
here, in one place, from two kinds of figure a person entered -- expected
payments (WorkOrderPaymentMilestone: amount + due date) and receipts
(WorkOrderPaymentEntry: money actually received). Nothing in this module is
stored, so a status can never disagree with the receipts behind it, and
nothing is inferred (no schedule is guessed from the client's free-text
payment terms; "overdue" exists only where someone entered a due date).

Reconciliation only, per Part O's BILLING note: this never computes GST, TDS
or invoices. gst_tds_amount is a figure the payer's certificate showed; here
it is only added to what has been "settled" (open decision 3 in the spec: the
payer has paid that part to the government on the vendor's behalf)."""
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.document import Quotation
from app.models.project import Project
from app.models.work_order import WorkOrder, WorkOrderPaymentEntry, WorkOrderPaymentMilestone

ZERO = Decimal("0")
OVERVIEW_MONTHS = 6


def _d(value) -> Decimal:
    return ZERO if value is None else Decimal(str(value))


def _f(value: Decimal) -> float:
    return float(value)


def order_value(db: Session, work_order: WorkOrder) -> Decimal:
    """A Work Order has no value field of its own: it is one-per-Won-Quotation
    and its value is that Quotation's frozen, GST-inclusive quotation_total."""
    quotation = db.query(Quotation).filter(Quotation.id == work_order.quotation_id).first()
    return _d(quotation.quotation_total) if quotation else ZERO


def milestone_status(amount_due: Decimal, settled: Decimal) -> str:
    if settled >= amount_due:
        return "paid"
    if settled > ZERO:
        return "part_paid"
    return "pending"


def derive_milestone(
    milestone: WorkOrderPaymentMilestone, received: Decimal, tds: Decimal, today: date
) -> dict:
    amount_due = _d(milestone.amount_due)
    settled = received + tds
    status = milestone_status(amount_due, settled)
    return {
        "id": milestone.id,
        "work_order_id": milestone.work_order_id,
        "name": milestone.name,
        "amount_due": _f(amount_due),
        "due_date": milestone.due_date,
        "notes": milestone.notes,
        "received_amount": _f(received),
        "tds_amount": _f(tds),
        "settled_amount": _f(settled),
        "outstanding_amount": _f(max(amount_due - settled, ZERO)),
        "status": status,
        "overdue": milestone.due_date < today and status != "paid",
        "created_by_id": milestone.created_by_id,
        "created_at": milestone.created_at,
    }


def _entry_totals_by_milestone(entries) -> dict:
    totals: dict = defaultdict(lambda: [ZERO, ZERO])
    for entry in entries:
        if entry.milestone_id is not None:
            totals[entry.milestone_id][0] += _d(entry.amount_received)
            totals[entry.milestone_id][1] += _d(entry.gst_tds_amount)
    return totals


def milestones_for_work_order(db: Session, work_order_id, today: date) -> list[dict]:
    milestones = (
        db.query(WorkOrderPaymentMilestone)
        .filter(WorkOrderPaymentMilestone.work_order_id == work_order_id)
        .order_by(WorkOrderPaymentMilestone.due_date, WorkOrderPaymentMilestone.created_at)
        .all()
    )
    entries = db.query(WorkOrderPaymentEntry).filter(WorkOrderPaymentEntry.work_order_id == work_order_id).all()
    totals = _entry_totals_by_milestone(entries)
    return [derive_milestone(m, *totals.get(m.id, (ZERO, ZERO)), today) for m in milestones]


def build_rows(db: Session, today: date, work_order_ids: list | None = None) -> list[dict]:
    """One row per Work Order (project, client, order value, received, TDS,
    outstanding, next due date, overdue amount). Outstanding is order value
    less what has been received and what the payer withheld as TDS, never
    below zero; anything beyond order value is reported as over_received, not
    refused (advances, extra work)."""
    query = (
        db.query(WorkOrder, Project, Client, Quotation)
        .join(Project, WorkOrder.project_id == Project.id)
        .join(Client, Project.client_id == Client.id)
        .join(Quotation, WorkOrder.quotation_id == Quotation.id)
    )
    if work_order_ids is not None:
        query = query.filter(WorkOrder.id.in_(work_order_ids))
    found = query.all()
    ids = [wo.id for wo, _p, _c, _q in found]
    if not ids:
        return []

    entries = db.query(WorkOrderPaymentEntry).filter(WorkOrderPaymentEntry.work_order_id.in_(ids)).all()
    milestones = (
        db.query(WorkOrderPaymentMilestone).filter(WorkOrderPaymentMilestone.work_order_id.in_(ids)).all()
    )
    entries_by_wo: dict = defaultdict(list)
    for entry in entries:
        entries_by_wo[entry.work_order_id].append(entry)
    milestones_by_wo: dict = defaultdict(list)
    for milestone in milestones:
        milestones_by_wo[milestone.work_order_id].append(milestone)

    rows = []
    for work_order, project, client, quotation in found:
        wo_entries = entries_by_wo.get(work_order.id, [])
        received = sum((_d(e.amount_received) for e in wo_entries), ZERO)
        tds = sum((_d(e.gst_tds_amount) for e in wo_entries), ZERO)
        value = _d(quotation.quotation_total)
        totals = _entry_totals_by_milestone(wo_entries)
        derived = [derive_milestone(m, *totals.get(m.id, (ZERO, ZERO)), today) for m in milestones_by_wo.get(work_order.id, [])]
        unpaid = [m for m in derived if m["status"] != "paid"]
        overdue_amount = sum((_d(m["outstanding_amount"]) for m in derived if m["overdue"]), ZERO)
        rows.append(
            {
                "work_order_id": work_order.id,
                "project_id": project.id,
                "project_no": project.project_no,
                "client_name": client.name,
                "quotation_document_no": quotation.document_no,
                "work_order_status": work_order.status,
                "awarded_at": work_order.awarded_at,
                "order_value": _f(value),
                "total_received": _f(received),
                "total_tds": _f(tds),
                "outstanding": _f(max(value - received - tds, ZERO)),
                "over_received": (received + tds) > value,
                "milestone_count": len(derived),
                "milestones_total": _f(sum((_d(m["amount_due"]) for m in derived), ZERO)),
                "next_due_date": min((m["due_date"] for m in unpaid), default=None),
                "overdue_amount": _f(overdue_amount),
                "overdue": any(m["overdue"] for m in derived),
                "overdue_milestones_count": sum(1 for m in derived if m["overdue"]),
            }
        )
    return rows


def sort_rows(rows: list[dict]) -> list[dict]:
    """Overdue first, then soonest next due date, then project number."""
    return sorted(
        rows,
        key=lambda r: (not r["overdue"], r["next_due_date"] is None, r["next_due_date"] or date.max, r["project_no"]),
    )


def _month_key(d) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _last_months(today: date, count: int) -> list[str]:
    year, month = today.year, today.month
    keys = []
    for _ in range(count):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(keys))


def build_overview(db: Session, today: date) -> dict:
    """The Overview's "Payments overdue" tile and "Orders & collections"
    panel. The chart's "won value" side is anchored on WorkOrder.awarded_at
    because Quotation has no won date; Won Quotations that have no Work Order
    yet are therefore not counted (open decision 8)."""
    rows = build_rows(db, today)
    months = _last_months(today, OVERVIEW_MONTHS)
    awarded = {key: ZERO for key in months}
    cash = {key: ZERO for key in months}
    for row in rows:
        key = _month_key(row["awarded_at"])
        if key in awarded:
            awarded[key] += _d(row["order_value"])
    all_entries = db.query(WorkOrderPaymentEntry).all()
    for entry in all_entries:
        key = _month_key(entry.received_date)
        if key in cash:
            cash[key] += _d(entry.amount_received)
    tracked = db.query(WorkOrderPaymentMilestone).count()
    return {
        "tracked_milestones_count": tracked,
        "overdue_count": sum(1 for r in rows if r["overdue"]),
        "overdue_milestones_count": sum(r["overdue_milestones_count"] for r in rows),
        "overdue_amount": sum(r["overdue_amount"] for r in rows),
        "work_orders_count": len(rows),
        "awarded_value_total": sum(r["order_value"] for r in rows),
        "cash_received_total": sum(r["total_received"] for r in rows),
        "tds_total": sum(r["total_tds"] for r in rows),
        "outstanding_total": sum(r["outstanding"] for r in rows),
        "months": [
            {"month": key, "awarded_value": _f(awarded[key]), "cash_received": _f(cash[key])} for key in months
        ],
    }
