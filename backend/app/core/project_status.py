"""One definition of a project's open/won/lost status, shared by the Dashboard tiles and the Projects list.

Amendment 28 Part A: a project is *closed* only when **every** Quotation on it has reached Won or Lost; a project with a
newer, still-active Quotation is Open regardless of an older Lost one (a re-bid), and a project with no Quotations is never
closed. A closed project is "won" when at least one of its Quotations is Won, otherwise "lost".

The Dashboard ("Open projects" tile) and GET /projects (status filter, per-row status) previously computed this
independently -- the list called a project "lost"/"won" if *any* quotation was, so an older Lost + newer Draft project was
Open on the Dashboard but "lost" (and absent from the Open filter) in the list, and the two counts disagreed. Both now call
this module. Nothing is stored: this only classifies existing quotation rows.

Compatibility decisions this module PRESERVES (existing Dashboard policy, not new rules; pinned by
tests/test_project_status_production_shape.py):
  * Won + a newer live quotation  -> the project is Open (not every quotation is Won/Lost).
  * Stored SUPERSEDED / EXPIRED rows count as "not yet closed", exactly as the Dashboard always counted them. (EXPIRED is
    normally a read-time label -- the stored status stays SENT -- so such a project is Open too.) A project whose only
    non-terminal rows are superseded revisions of a Won quotation therefore reads as Open; changing that would change the
    Dashboard rule itself and is a separate business decision.
Known separate inconsistency, not changed here: the Dashboard's "Recent projects" panel lists calibration projects (it calls
GET /projects without include_calibration=false) although every Dashboard tile excludes them.
"""
import uuid

from sqlalchemy.orm import Query, Session

from app.models.document import Quotation, QuotationStatus

_TERMINAL = (QuotationStatus.WON, QuotationStatus.LOST)

OPEN = "open"
WON = "won"
LOST = "lost"


def closed_project_ids(db: Session) -> Query:
    """Subquery of project ids whose quotations are ALL Won/Lost (and that have at least one)."""
    with_active_quotation = db.query(Quotation.project_id).filter(~Quotation.status.in_(_TERMINAL))
    return (
        db.query(Quotation.project_id)
        .filter(~Quotation.project_id.in_(with_active_quotation))
        .distinct()
    )


def won_project_ids(db: Session) -> Query:
    return db.query(Quotation.project_id).filter(Quotation.status == QuotationStatus.WON).distinct()


def project_statuses(db: Session, project_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """status per project id: open / won / lost, by the rule above."""
    if not project_ids:
        return {}
    closed = {pid for (pid,) in closed_project_ids(db).filter(Quotation.project_id.in_(project_ids)).all()}
    won = {pid for (pid,) in won_project_ids(db).filter(Quotation.project_id.in_(project_ids)).all()}
    return {pid: (WON if pid in won else LOST) if pid in closed else OPEN for pid in project_ids}
