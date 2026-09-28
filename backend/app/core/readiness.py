"""WP7 (correction plan, 2026-09-28): readiness checks before document issuance. Never
blocks a screen -- Documents.jsx's own draft/edit/navigation flows are entirely
unaffected; only the send_estimate and release_quotation actions themselves consult
this, at the moment they're called (see app/api/documents.py).

Three WAIVABLE checks (Site Survey completed, Scope confirmed, a sport selected) --
each can be satisfied by a Director recording an exception directly, or a PM requesting
one that then needs Director approval (ReadinessException, mirroring SkipRequest's own
proven shape). Cost Sheet not Verified and a below-floor margin are deliberately NOT
part of this module -- they are already separate, pre-existing hard/Director-only gates
in release_quotation and mark_quotation_won, untouched here.

One NON-waivable check (client identity: a linked Client with a name, a contact-person
name, and a phone or email) -- no exception path exists for it at all, matching the
design's own "Missing mandatory client identity fields ... Not waivable." Deliberately
narrow: GSTIN stays the existing informational-only field it already was (per
Client.gstin's own docstring) -- this is about identifying who the document is for and
how to reach them, not an invoicing/tax-compliance requirement, which the correction
plan explicitly keeps separate from this decision."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.project import Project
from app.models.readiness_exception import (
    ReadinessCheckKey,
    ReadinessDocumentType,
    ReadinessException,
    ReadinessExceptionStatus,
)
from app.models.scope_item import ProjectScopeItem
from app.models.site_survey import SiteSurvey, SiteSurveyStatus
from app.models.sport import ProjectSport

WAIVABLE_CHECK_LABELS = {
    ReadinessCheckKey.SITE_SURVEY: "Site Survey completed",
    ReadinessCheckKey.SCOPE: "Scope confirmed (or explicitly confirmed as no additional scope)",
    ReadinessCheckKey.SPORT: "At least one sport selected",
}


@dataclass
class ReadinessCheckResult:
    key: str
    label: str
    passed: bool
    waivable: bool
    # Only meaningful when passed is False and waivable is True: the ReadinessException
    # row governing this check for this exact document, if one has ever been created.
    exception: ReadinessException | None = None


@dataclass
class ClientIdentityResult:
    passed: bool
    missing: list[str]


def _site_survey_completed(db: Session, project_id) -> bool:
    return (
        db.query(SiteSurvey)
        .filter(SiteSurvey.project_id == project_id, SiteSurvey.status == SiteSurveyStatus.COMPLETED)
        .first()
        is not None
    )


def _scope_confirmed(db: Session, project: Project) -> bool:
    if project.scope_confirmed_empty_at is not None:
        return True
    return db.query(ProjectScopeItem).filter(ProjectScopeItem.project_id == project.id).first() is not None


def _sport_selected(db: Session, project_id) -> bool:
    return db.query(ProjectSport).filter(ProjectSport.project_id == project_id).first() is not None


def check_client_identity(client: Client | None) -> ClientIdentityResult:
    """The one non-waivable check. `client` may be None defensively (Project.client_id is
    itself NOT NULL at the schema level, so this should never actually happen through the
    API -- but a readiness check that silently trusted that invariant forever would be
    the wrong kind of check to write)."""
    missing = []
    if client is None:
        return ClientIdentityResult(passed=False, missing=["Client"])
    if not (client.name or "").strip():
        missing.append("Client name")
    if not (client.contact_name or "").strip():
        missing.append("Contact person name")
    if not ((client.phone or "").strip() or (client.email or "").strip()):
        missing.append("A phone or email to reach the contact")
    return ClientIdentityResult(passed=not missing, missing=missing)


def _existing_exception(
    db: Session, document_type: ReadinessDocumentType, document_id, check_key: ReadinessCheckKey
) -> ReadinessException | None:
    return (
        db.query(ReadinessException)
        .filter(
            ReadinessException.document_type == document_type,
            ReadinessException.document_id == document_id,
            ReadinessException.check_key == check_key,
            ReadinessException.status != ReadinessExceptionStatus.REJECTED,
        )
        .order_by(ReadinessException.requested_at.desc())
        .first()
    )


def compute_waivable_checks(
    db: Session, project: Project, document_type: ReadinessDocumentType, document_id
) -> list[ReadinessCheckResult]:
    """`document_id` is the specific Estimate or Quotation row send/release is being
    attempted on -- pass None to preview readiness before that document exists yet (the
    frontend's own pre-flight panel does this; no ReadinessException can exist yet in
    that case, so nothing is ever shown as waived)."""
    raw = {
        ReadinessCheckKey.SITE_SURVEY: _site_survey_completed(db, project.id),
        ReadinessCheckKey.SCOPE: _scope_confirmed(db, project),
        ReadinessCheckKey.SPORT: _sport_selected(db, project.id),
    }
    results = []
    for key, passed in raw.items():
        exception = None
        if not passed and document_id is not None:
            exception = _existing_exception(db, document_type, document_id, key)
            if exception is not None and exception.status == ReadinessExceptionStatus.APPROVED:
                passed = True
        results.append(
            ReadinessCheckResult(key=key.value, label=WAIVABLE_CHECK_LABELS[key], passed=passed, waivable=True, exception=exception)
        )
    return results


def blocking_waivable_checks(results: list[ReadinessCheckResult]) -> list[ReadinessCheckResult]:
    return [r for r in results if not r.passed]
