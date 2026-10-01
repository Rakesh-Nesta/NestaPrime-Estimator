"""One-off cleanup (2026-09-27): delete confirmed test/throwaway clients from production, and everything
that hangs off their projects and enquiries. Written for the Amendment 60 own-records review, where these
records' only distinguishing feature was having no owner -- ownership review surfaced that most of what had
no owner was leftover verification data from past Amendments' live-verification steps, never cleaned up.

Deletes ONLY the exact client ids in CLIENT_IDS below -- never by name matching -- which the Director
confirmed by name against a read-only listing before this script was written. Two records that looked
similar (a client that reads as real historical calibration data, and a client with no test marker at all)
were deliberately left out and are NOT in this list.

Dry-run by default: prints what it would delete, touches nothing. Pass --confirm to actually delete, inside
one transaction (a failure partway rolls back everything). Run --confirm once against a local copy of
production data before ever running it against the real database.
"""

import argparse
import uuid

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.attachment import Attachment
from app.models.attachment_upload_session import AttachmentUploadChunk, AttachmentUploadSession
from app.models.client import Client
from app.models.client_signatory import ClientSignatory
from app.models.document import (
    CostSheet,
    CostSheetLine,
    Estimate,
    EstimateOption,
    EstimateOptionAddon,
    Quotation,
    QuotationLine,
)
from app.models.message import Message
from app.models.opportunity import Opportunity
from app.models.project import Project
from app.models.p5 import (
    Agreement,
    ProjectExecutionAuthorization,
    ProjectMilestone,
    ProjectSiteIssue,
    ProjectTask,
    ProjectTeamMember,
)
from app.models.project_construction_stage import ProjectConstructionStage
from app.models.rate_history import RateHistory
from app.models.scope_item import ProjectScopeItem
from app.models.setting import DocumentType
from app.models.site_survey import SiteSurvey
from app.models.skip_request import SkipRequest
from app.models.sport import ProjectSport
from app.models.technical_bid_checklist import TechnicalBidChecklistItem
from app.models.tender_details import TenderCompetitorBid, TenderDetails
from app.models.purchase_order import PurchaseOrder, PurchaseOrderLine
from app.models.work_order import WorkOrder, WorkOrderPaymentEntry, WorkOrderPaymentMilestone

# Confirmed by the Director against `SELECT ... FROM clients WHERE owner_id IS NULL` on 2026-09-27 --
# every one of these is either "(delete me)"/"Verify" test data, or one of the six identical unlabeled
# "Home Solutions" rows the Director also confirmed as test. Left OUT on purpose (the Director asked these
# be kept): "Pathankot Badminton Court (FY23-24 actual, calibration)", "Imperial International School".
CLIENT_IDS = [
    "c7f7dd26-2095-43c4-a47b-d751010ea720",  # Home Solutions
    "b0174888-7c8b-497d-9bdc-4c947cb81a03",  # Home Solutions
    "762243c4-3be3-4476-a920-9588ace20fc4",  # Home Solutions
    "417328ca-46a5-4a46-953b-cfe925a56b0b",  # Home Solutions
    "96ce34c9-bb7c-4058-a512-1ed5c890b310",  # Home Solutions
    "38a7c028-e098-4847-9c95-69d2369c4134",  # Home Solutions
    "ffeea25d-fc69-45a4-acb0-67aa54bb482e",  # Smoke Test Client (delete me)
    "f8fd2b2c-00f3-4e72-9c34-8e740f3e1007",  # Smoke Test Client 2 (delete me)
    "78044ddf-839f-4980-a793-7a43d8b93be5",  # Deploy Smoke Test Client (delete me)
    "517dc842-9dd6-4d0b-9396-02bd5266a437",  # Deploy Smoke Test Client 2 (delete me)
    "d43e7461-fe5f-4587-9bee-f1ba6508b5aa",  # Deploy Smoke Test Client 2 (delete me)
    "0d24cd9d-fabf-477e-bff5-20b2a4d2e0b6",  # Amendment 28 Verify (delete me)
    "703fe7c5-2f6c-4ea9-8821-b53e3c87b978",  # Amendment 28 Verify (delete me)
    "ea6190ed-c5b5-4b35-bfe4-32bcd9aed09a",  # Amendments 29-31 Verify (delete me)
    "7447fb30-b573-4062-b45d-8fe4b436e27d",  # Amendment 33 Verify (delete me)
    "a6893c8a-ce23-41f8-83d0-a97258bf15c1",  # Amendment 33 Verify (delete me)
    "7243675b-e77b-417c-bfcb-cc42eda17230",  # Greenwood International School (delete me)
    "8d952558-854f-4d83-915a-71df22c64b20",  # Amendment 45 Verify Client
]


def _ids(rows) -> list[uuid.UUID]:
    return [r.id for r in rows]


def run(db: Session, confirm: bool) -> None:
    client_ids = [uuid.UUID(x) for x in CLIENT_IDS]
    clients = db.query(Client).filter(Client.id.in_(client_ids)).all()
    found_ids = {c.id for c in clients}
    missing = set(client_ids) - found_ids
    if missing:
        raise SystemExit(f"Refusing to run: {len(missing)} id(s) in CLIENT_IDS were not found: {sorted(missing)}")

    projects = db.query(Project).filter(Project.client_id.in_(client_ids)).all()
    project_ids = _ids(projects)

    cost_sheets = db.query(CostSheet).filter(CostSheet.project_id.in_(project_ids)).all() if project_ids else []
    cost_sheet_ids = _ids(cost_sheets)
    estimates = db.query(Estimate).filter(Estimate.project_id.in_(project_ids)).all() if project_ids else []
    estimate_ids = _ids(estimates)
    options = db.query(EstimateOption).filter(EstimateOption.estimate_id.in_(estimate_ids)).all() if estimate_ids else []
    option_ids = _ids(options)
    quotations = db.query(Quotation).filter(Quotation.project_id.in_(project_ids)).all() if project_ids else []
    quotation_ids = _ids(quotations)
    work_orders = (
        db.query(WorkOrder)
        .filter(or_(WorkOrder.project_id.in_(project_ids), WorkOrder.quotation_id.in_(quotation_ids)))
        .all()
        if project_ids
        else []
    )
    work_order_ids = _ids(work_orders)
    tender_details = db.query(TenderDetails).filter(TenderDetails.project_id.in_(project_ids)).all() if project_ids else []
    tender_details_ids = _ids(tender_details)
    checklist_items = (
        db.query(TechnicalBidChecklistItem).filter(TechnicalBidChecklistItem.project_id.in_(project_ids)).all()
        if project_ids
        else []
    )
    checklist_item_ids = _ids(checklist_items)
    site_surveys = db.query(SiteSurvey).filter(SiteSurvey.project_id.in_(project_ids)).all() if project_ids else []
    site_survey_ids = _ids(site_surveys)
    purchase_orders = (
        db.query(PurchaseOrder).filter(PurchaseOrder.cost_sheet_id.in_(cost_sheet_ids)).all() if cost_sheet_ids else []
    )
    purchase_order_ids = _ids(purchase_orders)
    opportunities = (
        db.query(Opportunity)
        .filter(or_(Opportunity.client_id.in_(client_ids), Opportunity.project_id.in_(project_ids)))
        .all()
    )
    opportunity_ids = _ids(opportunities)
    # P4: every new project is seeded with 6 construction-stage rows (seed_stages_for_project) --
    # these reference project_id with no cascade, so a project can't be deleted while any remain.
    stages = db.query(ProjectConstructionStage).filter(ProjectConstructionStage.project_id.in_(project_ids)).all() \
        if project_ids else []
    stage_ids = _ids(stages)
    # P5: agreements, execution authorizations, team members, milestones, tasks and site issues all
    # reference projects/quotations/work orders/attachments with no cascade.
    agreements = db.query(Agreement).filter(Agreement.project_id.in_(project_ids)).all() if project_ids else []
    agreement_ids = _ids(agreements)
    authorizations = (
        db.query(ProjectExecutionAuthorization).filter(ProjectExecutionAuthorization.project_id.in_(project_ids)).all()
        if project_ids else []
    )
    team_members = db.query(ProjectTeamMember).filter(ProjectTeamMember.project_id.in_(project_ids)).all()         if project_ids else []
    tasks = db.query(ProjectTask).filter(ProjectTask.project_id.in_(project_ids)).all() if project_ids else []
    milestones = db.query(ProjectMilestone).filter(ProjectMilestone.project_id.in_(project_ids)).all()         if project_ids else []
    site_issues = db.query(ProjectSiteIssue).filter(ProjectSiteIssue.project_id.in_(project_ids)).all()         if project_ids else []
    site_issue_ids = _ids(site_issues)

    # Every document id a doc_type/doc_id attachment or message could point at, across all of the above.
    doc_ids_by_type = {
        DocumentType.COST_SHEET: cost_sheet_ids,
        DocumentType.ESTIMATE: estimate_ids,
        DocumentType.ESTIMATE_OPTION: option_ids,
        DocumentType.QUOTATION: quotation_ids,
        DocumentType.WORK_ORDER: work_order_ids,
        DocumentType.TECHNICAL_BID_CHECKLIST_ITEM: checklist_item_ids,
        DocumentType.SITE_SURVEY: site_survey_ids,
        DocumentType.PROJECT_STAGE: stage_ids,
        DocumentType.AGREEMENT: agreement_ids,
        DocumentType.SITE_ISSUE: site_issue_ids,
    }
    attachments = [
        a
        for a in db.query(Attachment).filter(Attachment.doc_type.in_(list(doc_ids_by_type.keys()))).all()
        if a.doc_id in set(doc_ids_by_type.get(a.doc_type, []))
    ]
    attachment_ids = _ids(attachments)
    messages = [
        m
        for m in db.query(Message).filter(Message.doc_type.in_(list(doc_ids_by_type.keys()))).all()
        if m.doc_id in set(doc_ids_by_type.get(m.doc_type, []))
    ]
    # Upload sessions (P4) have a doc_type/doc_id pair of their own (a plain String column, not
    # the Enum type Attachment/Message use -- compared against doc_type.value, not the member
    # itself) AND a resulting_attachment_id FK straight to attachments.id: a completed session
    # still pointing at one of the attachments above would block deleting it, same FK-violation
    # shape as the project_construction_stages gap this script was already missing.
    doc_values_by_type = {dt.value: ids for dt, ids in doc_ids_by_type.items()}
    upload_sessions = [
        s
        for s in db.query(AttachmentUploadSession).filter(AttachmentUploadSession.doc_type.in_(doc_values_by_type.keys())).all()
        if s.doc_id in set(doc_values_by_type.get(s.doc_type, [])) or s.resulting_attachment_id in set(attachment_ids)
    ]
    upload_session_ids = _ids(upload_sessions)

    print(f"Clients:                 {len(clients)}")
    for c in clients:
        print(f"  - {c.name} ({c.id})")
    print(f"Projects:                {len(projects)}")
    print(f"Opportunities/enquiries: {len(opportunities)}")
    print(f"Cost sheets:             {len(cost_sheets)}")
    print(f"Estimates:               {len(estimates)}  (options: {len(options)})")
    print(f"Quotations:              {len(quotations)}")
    print(f"Work orders:             {len(work_orders)}")
    print(f"Attachments:             {len(attachments)}")
    print(f"Messages:                {len(messages)}")
    print(f"Site surveys:            {len(site_surveys)}")
    print(f"Tender details:          {len(tender_details)}")
    print(f"Technical bid items:     {len(checklist_items)}")
    print(f"Purchase orders:         {len(purchase_orders)}")
    print(f"Construction stages:     {len(stages)}")
    print(f"Upload sessions:         {len(upload_sessions)}")
    print(f"Agreements:              {len(agreements)}")
    print(f"Execution authorizations:{len(authorizations)}")
    print(f"Team members:            {len(team_members)}")
    print(f"Milestones/tasks/issues: {len(milestones)}/{len(tasks)}/{len(site_issues)}")

    if not confirm:
        print("\nDry run only -- nothing deleted. Re-run with --confirm to actually delete.")
        return

    # 1. Messages first -- a Message can point at an Attachment.
    for m in messages:
        db.delete(m)
    db.flush()

    # 1b. P5 rows, children before parents: tasks (-> team members, milestones), authorizations
    # (-> agreements), agreements (-> attachments, itself via supersedes_id), then the rest. All of
    # these must go before the attachments / work orders / quotations / projects they reference.
    for t in tasks:
        db.delete(t)
    db.flush()
    for a in authorizations:
        db.delete(a)
    db.flush()
    for ag in agreements:
        ag.supersedes_id = None
    db.flush()
    for ag in agreements:
        db.delete(ag)
    for m in team_members:
        db.delete(m)
    for ms in milestones:
        db.delete(ms)
    for si in site_issues:
        db.delete(si)
    db.flush()

    # 2. Upload-session chunks, then the sessions themselves (their resulting_attachment_id FK
    # would otherwise block deleting an Attachment below), then break the Attachment
    # self-reference (superseded_by_id), then delete Attachments.
    if upload_session_ids:
        db.query(AttachmentUploadChunk).filter(AttachmentUploadChunk.session_id.in_(upload_session_ids)).delete(
            synchronize_session=False
        )
    for s in upload_sessions:
        db.delete(s)
    db.flush()
    for a in attachments:
        a.superseded_by_id = None
    db.flush()
    for a in attachments:
        db.delete(a)
    db.flush()

    # 3. Payment ledger under the work orders, then the work orders themselves.
    if work_order_ids:
        db.query(WorkOrderPaymentEntry).filter(WorkOrderPaymentEntry.work_order_id.in_(work_order_ids)).delete(
            synchronize_session=False
        )
        db.query(WorkOrderPaymentMilestone).filter(WorkOrderPaymentMilestone.work_order_id.in_(work_order_ids)).delete(
            synchronize_session=False
        )
    for wo in work_orders:
        db.delete(wo)
    db.flush()

    # 4. Quotation lines, then quotations.
    if quotation_ids:
        db.query(QuotationLine).filter(QuotationLine.quotation_id.in_(quotation_ids)).delete(synchronize_session=False)
    for q in quotations:
        db.delete(q)
    db.flush()

    # 5. Estimate option add-ons, then options, then estimates.
    if option_ids:
        db.query(EstimateOptionAddon).filter(EstimateOptionAddon.estimate_option_id.in_(option_ids)).delete(
            synchronize_session=False
        )
    for o in options:
        db.delete(o)
    db.flush()
    for e in estimates:
        db.delete(e)
    db.flush()

    # 6. Purchase order lines, then purchase orders; cost sheet lines and skip requests, then cost sheets.
    if purchase_order_ids:
        db.query(PurchaseOrderLine).filter(PurchaseOrderLine.purchase_order_id.in_(purchase_order_ids)).delete(
            synchronize_session=False
        )
    for po in purchase_orders:
        db.delete(po)
    db.flush()
    if cost_sheet_ids:
        db.query(CostSheetLine).filter(CostSheetLine.cost_sheet_id.in_(cost_sheet_ids)).delete(synchronize_session=False)
        db.query(SkipRequest).filter(SkipRequest.resulting_cost_sheet_id.in_(cost_sheet_ids)).delete(
            synchronize_session=False
        )
    if project_ids:
        db.query(SkipRequest).filter(SkipRequest.project_id.in_(project_ids)).delete(synchronize_session=False)
    for cs in cost_sheets:
        db.delete(cs)
    db.flush()

    # 7. Tender competitor bids, then tender details.
    if tender_details_ids:
        db.query(TenderCompetitorBid).filter(TenderCompetitorBid.tender_details_id.in_(tender_details_ids)).delete(
            synchronize_session=False
        )
    for td in tender_details:
        db.delete(td)
    db.flush()

    # 8. Everything else keyed directly by project_id.
    for item in checklist_items:
        db.delete(item)
    for sv in site_surveys:
        db.delete(sv)
    if project_ids:
        db.query(ProjectScopeItem).filter(ProjectScopeItem.project_id.in_(project_ids)).delete(synchronize_session=False)
        db.query(RateHistory).filter(RateHistory.project_id.in_(project_ids)).delete(synchronize_session=False)
        db.query(ProjectSport).filter(ProjectSport.project_id.in_(project_ids)).delete(synchronize_session=False)
        db.query(ProjectConstructionStage).filter(ProjectConstructionStage.project_id.in_(project_ids)).delete(
            synchronize_session=False
        )
    db.flush()

    # 9. Break the Project<->Opportunity cross-link, delete enquiries, then projects, then signatories/clients.
    for p in projects:
        p.opportunity_id = None
    db.flush()
    for o in opportunities:
        db.delete(o)
    db.flush()
    for p in projects:
        db.delete(p)
    db.flush()
    if client_ids:
        db.query(ClientSignatory).filter(ClientSignatory.client_id.in_(client_ids)).delete(synchronize_session=False)
    for c in clients:
        db.delete(c)

    db.commit()
    print("\nDeleted.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", action="store_true", help="Actually delete (default is a dry run).")
    args = parser.parse_args()
    session = SessionLocal()
    try:
        run(session, args.confirm)
    finally:
        session.close()
