"""P4 contract v7, Section 2: search across attachments.

A UNION ALL across one subquery per doc_type, each with its OWN real join to Project (mirroring
ownership.project_id_for_document's own per-doc_type resolution, expressed in SQL). Step 1
(revision 4 fix): which doc_type branches is this user's ROLE even permitted to see at all --
computed BEFORE building the union, not relied on to fall out of the ownership filter alone. An
excluded doc_type contributes no branch to the union at all, not a branch that's merely filtered
down to zero rows. total is computed on the fully-filtered union, before pagination -- the same
total=q.count()-before-.limit() shape search.py's own group functions already use."""

from sqlalchemy import String, literal
from sqlalchemy.orm import Session

from app.api.attachments import _DOC_TABLE, _roles_for
from app.core import ownership
from app.models.attachment import Attachment
from app.models.document import CostSheet, Estimate, EstimateOption, Quotation
from app.models.project import Project
from app.models.project_construction_stage import ProjectConstructionStage
from app.models.setting import DocumentType
from app.models.site_survey import SiteSurvey
from app.models.technical_bid_checklist import TechnicalBidChecklistItem
from app.models.work_order import WorkOrder

# EstimateOption has no project_id of its own -- only its parent Estimate does (same nuance
# ownership.project_id_for_document already carries for this one doc_type). PRICE_REQUEST is
# deliberately absent: PriceRequest has no project_id column and no reliable indirect link exists
# (PriceRequestItem.rate_item_id only references the shared rate-master catalog used across many
# projects' Cost Sheets) -- an already-documented gap in this codebase (P2 correction plan), not
# something P4 can resolve. It is excluded from search's permitted branches below, not merely
# left unjoinable and crashing -- the same real gap already means ownership.
# project_id_for_document has no "price_request" entry either, so a scoped Sales user already
# cannot see price_request attachments today regardless of this search feature.
_DIRECT_PROJECT_MODELS = {
    DocumentType.COST_SHEET: CostSheet,
    DocumentType.ESTIMATE: Estimate,
    DocumentType.QUOTATION: Quotation,
    DocumentType.WORK_ORDER: WorkOrder,
    DocumentType.TECHNICAL_BID_CHECKLIST_ITEM: TechnicalBidChecklistItem,
    DocumentType.SITE_SURVEY: SiteSurvey,
    DocumentType.PROJECT_STAGE: ProjectConstructionStage,
}
_SEARCHABLE_DOC_TYPES = frozenset(_DIRECT_PROJECT_MODELS) | {DocumentType.ESTIMATE_OPTION}


def _branch_for(db: Session, doc_type: DocumentType, query_text: str | None, requested_doc_type: DocumentType | None):
    model = _DOC_TABLE[doc_type]
    if doc_type == DocumentType.ESTIMATE_OPTION:
        q = (
            db.query(
                Attachment.id.label("attachment_id"),
                literal(doc_type.value, type_=String).label("doc_type"),
                Project.id.label("project_id"),
                Project.owner_id.label("owner_id"),
            )
            .join(model, Attachment.doc_id == model.id)
            .join(Estimate, model.estimate_id == Estimate.id)
            .join(Project, Estimate.project_id == Project.id)
        )
    else:
        project_model = _DIRECT_PROJECT_MODELS[doc_type]
        q = (
            db.query(
                Attachment.id.label("attachment_id"),
                literal(doc_type.value, type_=String).label("doc_type"),
                Project.id.label("project_id"),
                Project.owner_id.label("owner_id"),
            )
            .join(project_model, Attachment.doc_id == project_model.id)
            .join(Project, project_model.project_id == Project.id)
        )
    q = q.filter(Attachment.doc_type == doc_type, Attachment.superseded_by_id.is_(None))
    if query_text:
        q = q.filter(Attachment.original_filename.ilike(f"%{query_text}%"))
    if requested_doc_type is not None:
        q = q.filter(Attachment.doc_type == requested_doc_type)
    return q


def search_attachments(
    db: Session, current_user, query_text: str | None, requested_doc_type: DocumentType | None,
    limit: int, offset: int,
) -> dict:
    # Step 1 (revision 4 fix): compute permitted branches BEFORE building the union. Restricted
    # to doc_types with a resolvable Project join -- see _SEARCHABLE_DOC_TYPES's own note on
    # why PRICE_REQUEST is never a candidate branch at all.
    permitted = [dt for dt in _SEARCHABLE_DOC_TYPES if current_user.role.value in _roles_for(dt)]
    if requested_doc_type is not None and requested_doc_type not in permitted:
        return {"total": 0, "items": []}

    branches = [_branch_for(db, dt, query_text, requested_doc_type) for dt in permitted]
    union_q = branches[0].union_all(*branches[1:]) if len(branches) > 1 else branches[0]
    subq = union_q.subquery()

    outer = db.query(subq.c.attachment_id, subq.c.doc_type, subq.c.project_id, subq.c.owner_id)
    if ownership.scoping_applies(db, current_user):
        outer = outer.filter(subq.c.owner_id == current_user.id)

    total = outer.count()  # from the fully-filtered union, before pagination
    rows = outer.order_by(subq.c.attachment_id.desc()).offset(offset).limit(limit).all()

    attachment_ids = [row.attachment_id for row in rows]
    attachments_by_id = {
        a.id: a for a in db.query(Attachment).filter(Attachment.id.in_(attachment_ids)).all()
    } if attachment_ids else {}
    items = [attachments_by_id[row.attachment_id] for row in rows if row.attachment_id in attachments_by_id]
    return {"total": total, "items": items}
