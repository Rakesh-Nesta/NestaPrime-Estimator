"""Amendment 60 (Section 63): own-records visibility -- the one place that decides "may this person see this?".

When the Director switches it on (Master Setting `sales_own_records_only`), a **Sales** user sees only the clients,
projects and opportunities they own, and everything hanging off them (cost sheets, estimates, quotations, attachments,
messages, sport selections, signatories, reports they generated). PM, Director and every other role are unchanged. It
is off by default: nothing changes for anyone until the Director has reviewed how many records still have no owner.

Two mechanisms, both server-side, both here:

* **By id.** `enforce_own_records` is a global dependency: for a Sales user, any request whose URL names a record
  (`/projects/{project_id}/...`, `/quotations/{quotation_id}`, ...) is refused with **404** unless that record's
  project is theirs. A record that does not exist and a record that is someone else's are answered identically, so the
  answer cannot be used to find out which ids exist. New id parameters must be listed in `COVERED_PATH_PARAMS`; a test
  fails if a Sales-reachable route uses one that is not.
* **Lists, searches, creates.** Each list handler calls `scoping_applies` and narrows its query; creates set the owner.
"""

import uuid

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole

SWITCH_KEY = "sales_own_records_only"
SCOPED_ROLES = (UserRole.SALES,)
NOT_FOUND = "Not found"

# Path parameters that name a record whose ownership matters -> how it is resolved below. `client_type` is a plain
# value, not a record, and is deliberately absent (see UNSCOPED_PATH_PARAMS).
COVERED_PATH_PARAMS = frozenset(
    {
        "project_id",
        "client_id",
        "opportunity_id",
        "estimate_id",
        "quotation_id",
        "cost_sheet_id",
        "option_id",
        "row_id",
        "selection_id",
        "project_sport_id",
        "signatory_id",
        "contact_id",  # P2 (Client 360 contract)
        "site_id",  # P2 (Client 360 contract)
        "attachment_id",
        "report_id",
        "work_order_id",
        "stage_id",  # P4 contract v7
        "session_id",  # P4 contract v7
        "doc_id",  # P4 contract v7 -- resolved against its sibling `doc_type` path param
        "message_id",  # resend: a message belongs to the project of the document it was sent about
        "exclusion_id",  # restoring a PDF image: an exclusion belongs to the project of its document
    }
)
# `doc_type` is a plain value (which table doc_id names), not a record; `chunk_index` is a bare
# integer offset into a session's chunks, never an id of its own -- both P4 contract v7.
UNSCOPED_PATH_PARAMS = frozenset({"client_type", "doc_type", "chunk_index"})


def switch_is_on(db: Session) -> bool:
    from app.api.settings import get_current_setting_value  # deferred: settings imports this package

    return (get_current_setting_value(db, SWITCH_KEY) or "").strip().lower() in ("on", "true", "1", "yes")


def is_scoped_role(user: User) -> bool:
    return user.role in SCOPED_ROLES


def scoping_applies(db: Session, user: User) -> bool:
    """True when this user must only see their own records right now."""
    return is_scoped_role(user) and switch_is_on(db)


# --- who owns what -------------------------------------------------------------------------------------------


def project_id_for_document(db: Session, doc_type: str, doc_id: uuid.UUID) -> uuid.UUID | None:
    """The project a generic document reference (attachments, messages) belongs to, or None if it has none."""
    from app.models.document import CostSheet, Estimate, EstimateOption, Quotation
    from app.models.project_construction_stage import ProjectConstructionStage
    from app.models.site_survey import SiteSurvey
    from app.models.technical_bid_checklist import TechnicalBidChecklistItem
    from app.models.work_order import WorkOrder

    if doc_type == "estimate_option":
        option = db.get(EstimateOption, doc_id)
        estimate = db.get(Estimate, option.estimate_id) if option else None
        return estimate.project_id if estimate else None
    model = {
        "cost_sheet": CostSheet,
        "estimate": Estimate,
        "quotation": Quotation,
        "work_order": WorkOrder,
        "technical_bid_checklist_item": TechnicalBidChecklistItem,
        "site_survey": SiteSurvey,
        "project_stage": ProjectConstructionStage,  # P4 contract v7, Section 2/3
    }.get(doc_type)
    if model is None:
        return None
    row = db.get(model, doc_id)
    return getattr(row, "project_id", None) if row else None


def _owner_of_project(db: Session, project_id: uuid.UUID | None) -> uuid.UUID | None:
    from app.models.project import Project

    project = db.get(Project, project_id) if project_id else None
    return project.owner_id if project else None


def may_see_project(db: Session, user: User, project_id: uuid.UUID | None) -> bool:
    owner = _owner_of_project(db, project_id)
    return owner is not None and owner == user.id


def may_see_document(db: Session, user: User, doc_type: str, doc_id: uuid.UUID) -> bool:
    """Attachments and messages point at a document by (type, id); it is visible when its project is."""
    return may_see_project(db, user, project_id_for_document(db, doc_type, doc_id))


def require_visible_document(db: Session, user: User, doc_type: str, doc_id: uuid.UUID) -> None:
    if scoping_applies(db, user) and not may_see_document(db, user, doc_type, doc_id):
        raise HTTPException(status_code=404, detail=NOT_FOUND)


def require_own_client(db: Session, user: User, client_id: uuid.UUID) -> None:
    """A Sales user may only build on a client they own (a new project, a linked enquiry, ...)."""
    from app.models.client import Client

    if not scoping_applies(db, user):
        return
    client = db.get(Client, client_id)
    if client is None or client.owner_id != user.id:
        raise HTTPException(status_code=404, detail=NOT_FOUND)


OWNER_ROLES = (UserRole.SALES, UserRole.PM, UserRole.DIRECTOR)


def require_valid_owner(db: Session, owner_id: uuid.UUID) -> User:
    """Records can be held by an active Sales, PM or Director user -- not by an Admin, not by someone deactivated."""
    owner = db.get(User, owner_id)
    if owner is None or not owner.is_active or owner.role not in OWNER_ROLES:
        raise HTTPException(status_code=422, detail="Choose an active Sales, PM or Director user as the owner")
    return owner


def require_own_opportunity(db: Session, user: User, opportunity_id: uuid.UUID) -> None:
    from app.models.opportunity import Opportunity

    if not scoping_applies(db, user):
        return
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None or opportunity.owner_id != user.id:
        raise HTTPException(status_code=404, detail=NOT_FOUND)


# --- the global by-id guard ----------------------------------------------------------------------------------


def _resolve_owner_ok(db: Session, user: User, key: str, value: uuid.UUID) -> bool:
    """Does the record named by this path parameter belong to `user` (through its project or client)?"""
    from app.models.attachment import Attachment
    from app.models.client import Client
    from app.models.client_contact import ClientContact
    from app.models.client_signatory import ClientSignatory
    from app.models.client_site import ClientSite
    from app.models.document import CostSheet, Estimate, EstimateOption, EstimateOptionAddon, Quotation
    from app.models.opportunity import Opportunity
    from app.models.report import Report
    from app.models.sport import ProjectSport
    from app.models.work_order import WorkOrder

    if key == "project_id":
        return may_see_project(db, user, value)
    if key == "client_id":
        client = db.get(Client, value)
        return client is not None and client.owner_id == user.id
    if key == "opportunity_id":
        opportunity = db.get(Opportunity, value)
        return opportunity is not None and opportunity.owner_id == user.id
    if key == "signatory_id":
        signatory = db.get(ClientSignatory, value)
        client = db.get(Client, signatory.client_id) if signatory else None
        return client is not None and client.owner_id == user.id
    if key == "contact_id":
        contact = db.get(ClientContact, value)
        client = db.get(Client, contact.client_id) if contact else None
        return client is not None and client.owner_id == user.id
    if key == "site_id":
        site = db.get(ClientSite, value)
        client = db.get(Client, site.client_id) if site else None
        return client is not None and client.owner_id == user.id
    if key == "report_id":
        report = db.get(Report, value)
        return report is not None and report.generated_by_id == user.id
    if key == "attachment_id":
        attachment = db.get(Attachment, value)
        if attachment is None:
            return False
        return may_see_document(db, user, attachment.doc_type.value, attachment.doc_id)
    if key in ("estimate_id", "quotation_id", "cost_sheet_id", "work_order_id", "selection_id", "project_sport_id"):
        model = {
            "estimate_id": Estimate,
            "quotation_id": Quotation,
            "cost_sheet_id": CostSheet,
            "work_order_id": WorkOrder,
            "selection_id": ProjectSport,
            "project_sport_id": ProjectSport,
        }[key]
        row = db.get(model, value)
        return row is not None and may_see_project(db, user, row.project_id)
    if key == "option_id":
        option = db.get(EstimateOption, value)
        estimate = db.get(Estimate, option.estimate_id) if option else None
        return estimate is not None and may_see_project(db, user, estimate.project_id)
    if key == "row_id":  # an add-on row on an estimate option
        addon = db.get(EstimateOptionAddon, value)
        option = db.get(EstimateOption, addon.estimate_option_id) if addon else None
        estimate = db.get(Estimate, option.estimate_id) if option else None
        return estimate is not None and may_see_project(db, user, estimate.project_id)
    if key == "stage_id":  # P4 contract v7, Section 3
        from app.models.project_construction_stage import ProjectConstructionStage

        stage = db.get(ProjectConstructionStage, value)
        return stage is not None and may_see_project(db, user, stage.project_id)
    if key == "session_id":  # P4 contract v7, Section 4
        from app.models.attachment_upload_session import AttachmentUploadSession

        session = db.get(AttachmentUploadSession, value)
        return session is not None and may_see_document(db, user, session.doc_type, session.doc_id)
    if key == "message_id":
        from app.models.message import Message

        message = db.get(Message, value)
        return message is not None and may_see_document(db, user, message.doc_type.value, message.doc_id)
    if key == "exclusion_id":
        from app.models.pdf_image_exclusion import PdfImageExclusion

        exclusion = db.get(PdfImageExclusion, value)
        return exclusion is not None and may_see_document(db, user, exclusion.doc_type, exclusion.doc_id)
    return True  # a parameter this rule does not cover is not silently treated as hidden; the test guards new ones


def _user_from_bearer(request: Request, db: Session) -> User | None:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    payload = decode_access_token(header[7:].strip())
    if not payload or "sub" not in payload:
        return None
    # Amendment 61 (Section 64) item 4: the subject is the user's id, not their email.
    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, TypeError):
        return None
    user = db.query(User).filter(User.id == user_id).first()
    return user if user is not None and user.is_active else None


def enforce_own_records(request: Request, db: Session = Depends(get_db)) -> None:
    """Global dependency: refuse (404) a Sales user's request that names a record they do not own, while the switch
    is on. Anything else -- another role, an unsigned request, a URL naming no record -- passes straight through, and
    the route's own authentication answers as it always has."""
    named = COVERED_PATH_PARAMS & request.path_params.keys()
    if not named:
        return
    user = _user_from_bearer(request, db)
    if user is None or not scoping_applies(db, user):
        return
    for key in named:
        try:
            value = uuid.UUID(str(request.path_params[key]))
        except ValueError:
            continue  # not an id: the route's own validation answers 422
        if key == "doc_id":
            # Resolved against its sibling `doc_type` path param (e.g. /attachments/{doc_type}/
            # {doc_id}/lineages) -- doc_type alone carries no record, so it is not itself covered.
            doc_type = request.path_params.get("doc_type")
            if doc_type is None or not may_see_document(db, user, str(doc_type), value):
                raise HTTPException(status_code=404, detail=NOT_FOUND)
            continue
        if not _resolve_owner_ok(db, user, key, value):
            raise HTTPException(status_code=404, detail=NOT_FOUND)
