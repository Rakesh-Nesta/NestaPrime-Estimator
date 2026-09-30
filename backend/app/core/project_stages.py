"""P4 contract v7, Section 3: stage evidence capture -- the state machine and seeding helper.

    not_started -> in_progress          automatic, a side effect of the first Attachment upload
    in_progress -> evidence_submitted   explicit "mark ready for review" action
    evidence_submitted -> reviewed      explicit review action (PM/Director)
    evidence_submitted -> rejected      explicit review action, with a required reason
    rejected -> in_progress             automatic once new evidence is uploaded (resubmission)
    reviewed -> evidence_submitted      automatic on new evidence upload or supersede -- a stale
                                         sign-off is never left in place (matches Quotation
                                         revision resetting approval, Estimate revision resetting
                                         option statuses)

"mark ready for review" is refused server-side if zero Attachments exist against the stage --
there is nothing to review.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.attachment import Attachment
from app.models.construction_sequence_step import ConstructionPhase
from app.models.project_construction_stage import ProjectConstructionStage, StageStatus
from app.models.setting import DocumentType

CONSTRUCTION_PHASES: tuple[str, ...] = tuple(phase.value for phase in ConstructionPhase)


def seed_stages_for_project(db: Session, project_id: uuid.UUID) -> None:
    """Called once, inside create_project, for every new project going forward. Existing
    projects were backfilled once, migration-time (509d1202ac03) -- this function is never
    called for them again, and a read-only request never creates a row as a side effect."""
    for phase in CONSTRUCTION_PHASES:
        db.add(ProjectConstructionStage(project_id=project_id, phase=phase, status=StageStatus.NOT_STARTED.value))


def advance_stage_on_evidence_upload(db: Session, stage: ProjectConstructionStage) -> None:
    """Called after a successful Attachment upload/supersede against a stage (attachments.py).
    not_started/rejected both move to in_progress (a rejected stage's resubmission path);
    reviewed moves back to evidence_submitted (a stale sign-off is never left in place);
    in_progress/evidence_submitted are left exactly as they are -- more evidence arriving while
    already mid-flight or already pending review changes nothing about the stage's own status."""
    if stage.status in (StageStatus.NOT_STARTED.value, StageStatus.REJECTED.value):
        if stage.status == StageStatus.NOT_STARTED.value:
            stage.started_at = datetime.now(UTC)
        stage.status = StageStatus.IN_PROGRESS.value
    elif stage.status == StageStatus.REVIEWED.value:
        stage.status = StageStatus.EVIDENCE_SUBMITTED.value
        stage.evidence_submitted_at = datetime.now(UTC)


def has_current_evidence(db: Session, stage_id: uuid.UUID) -> bool:
    return (
        db.query(Attachment)
        .filter(
            Attachment.doc_type == DocumentType.PROJECT_STAGE,
            Attachment.doc_id == stage_id,
            Attachment.superseded_by_id.is_(None),
        )
        .first()
        is not None
    )
