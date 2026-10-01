"""P5 contract revision 7, Section 7: separately authorized backfill that records pre-P5 Work Orders.

An existing Work Order proves a historical HANDOFF, not a captured agreement. For every
(Quotation, Work Order) pair that already existed when the P5 migration ran, this creates exactly one
Agreement row with status 'legacy_adopted' -- a placeholder that can never satisfy the executed-
Agreement check (app.core.p5.compute_readiness requires status == 'executed').

* Durable boundary: eligibility is `WorkOrder.created_at <= p5_migration_marker.deployed_at`, the single
  immutable row the migration wrote. A Work Order created after P5 shipped is never eligible, no
  matter when this script runs or how often.
* Per-pair idempotency: a pair is skipped only if THAT quotation already has any Agreement revision.
  One adopted pair never short-circuits another pair on the same project.
* Scope: only the existing quotation/Work Order pair; a future Won quotation on the same project gets
  no exemption, because it has no pre-P5 Work Order.
* Dry-run by default (prints what it would do). --confirm writes, in ONE transaction, taking the
  shared P5 lock order (projects in ascending id) per pair; a failure rolls everything back.
  --actor-email (an active Director) is required with --confirm: it is recorded as created_by_id and as
  the audit-log actor.
"""

import argparse

from sqlalchemy import select

from app.core import p5
from app.db.session import SessionLocal
from app.models.document import Quotation
from app.models.p5 import Agreement, AgreementStatus, P5MigrationMarker
from app.models.user import User, UserRole
from app.models.work_order import WorkOrder
from app.api.audit_log import write_audit_log_entry


def run(db, confirm: bool, actor_email: str | None) -> dict:
    marker = db.get(P5MigrationMarker, 1)
    if marker is None:
        raise SystemExit("Refusing to run: the P5 migration marker row is missing (has the P5 migration been applied?)")
    actor = None
    if confirm:
        if not actor_email:
            raise SystemExit("--actor-email (an active Director) is required with --confirm")
        actor = db.query(User).filter(User.email == actor_email).first()
        if actor is None or not actor.is_active or actor.role != UserRole.DIRECTOR:
            raise SystemExit("--actor-email must be an active Director")

    pairs = db.execute(
        select(WorkOrder, Quotation)
        .join(Quotation, Quotation.id == WorkOrder.quotation_id)
        .where(WorkOrder.created_at <= marker.deployed_at)
        .order_by(Quotation.project_id, Quotation.id)
    ).all()

    result = {"eligible": len(pairs), "adopted": 0, "already_adopted": 0, "skipped_other_agreement": 0}
    for work_order, quotation in pairs:
        existing = db.execute(select(Agreement).where(Agreement.quotation_id == quotation.id)).scalars().all()
        if any(a.status == AgreementStatus.LEGACY_ADOPTED for a in existing):
            result["already_adopted"] += 1
            continue
        if any(a.status not in AgreementStatus.NOT_CURRENT for a in existing):
            print(f"  ! quotation {quotation.id}: already has a current Agreement; not adopting")
            result["skipped_other_agreement"] += 1
            continue
        print(f"  + adopt quotation {quotation.id} / work order {work_order.id} (project {quotation.project_id})")
        if confirm:
            p5.lock_quotation_scope(db, quotation.id)
            agreement = Agreement(
                quotation_id=quotation.id,
                project_id=quotation.project_id,
                status=AgreementStatus.LEGACY_ADOPTED,
                created_by_id=actor.id,
            )
            db.add(agreement)
            db.flush()
            write_audit_log_entry(
                db, actor, "agreement", agreement.id, "status", old_value=None,
                new_value=AgreementStatus.LEGACY_ADOPTED,
                reason=f"pre-P5 Work Order {work_order.id} recorded as a legacy handoff (not a signed agreement)",
            )
        result["adopted"] += 1
    if confirm:
        db.commit()
    else:
        print("\nDry run only -- nothing written. Re-run with --confirm --actor-email <director> to write.")
    print(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--actor-email")
    args = parser.parse_args()
    session = SessionLocal()
    try:
        run(session, args.confirm, args.actor_email)
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
