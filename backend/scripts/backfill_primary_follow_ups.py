"""WP5 integration (correction plan, 2026-09-28): backfill a matching FollowUp row
(purpose_key="primary_reminder") for every existing Client/Opportunity that already
has a legacy next_follow_up_date set, so the shared /follow-ups API and the central
Follow-ups screen see the organisation's existing reminders, not just ones created
after this integration shipped.

Idempotent by design, safe to run more than once: it only creates a row for an
entity that has no primary-reminder FollowUp row yet (regardless of that row's
status), so a record already covered -- whether by an earlier backfill run or by
the live sync path (app/core/follow_up_sync.py) picking it up on its own next
edit -- is never duplicated.

created_by_id is required (NOT NULL) on FollowUp. Opportunity always has its own
created_by_id; Client has none, so its backfilled row uses the Client's owner_id
when set. A handful of unassigned Clients that somehow still carry a legacy
reminder (Amendment 60's cleanup left the codebase's own real 2026-09-27 dev/prod
data with none, but a script must not assume that stays true forever) have no id
to attribute the row to and are skipped -- reported at the end, not silently
dropped.

Dry-run by default: prints what it would create, touches nothing. Pass --confirm
to actually write, inside one transaction (a failure partway rolls back everything).
"""

import argparse

from app.db.session import SessionLocal
from app.models.client import Client
from app.models.follow_up import FollowUp, FollowUpEntityType
from app.models.opportunity import Opportunity


def _has_primary(db, entity_type: FollowUpEntityType, entity_id) -> bool:
    return (
        db.query(FollowUp.id)
        .filter(
            FollowUp.entity_type == entity_type,
            FollowUp.entity_id == entity_id,
            FollowUp.purpose_key == "primary_reminder",
        )
        .first()
        is not None
    )


def run(confirm: bool) -> None:
    db = SessionLocal()
    created = 0
    skipped_no_owner = []
    try:
        opportunities = db.query(Opportunity).filter(Opportunity.next_follow_up_date.isnot(None)).all()
        for o in opportunities:
            if _has_primary(db, FollowUpEntityType.OPPORTUNITY, o.id):
                continue
            print(f"  + opportunity {o.id} ({o.lead_name}): due {o.next_follow_up_date}")
            if confirm:
                db.add(
                    FollowUp(
                        entity_type=FollowUpEntityType.OPPORTUNITY,
                        entity_id=o.id,
                        purpose_key="primary_reminder",
                        owner_id=o.owner_id,
                        next_action=o.follow_up_note or "Follow up",
                        due_date=o.next_follow_up_date,
                        created_by_id=o.created_by_id,
                    )
                )
            created += 1

        clients = db.query(Client).filter(Client.next_follow_up_date.isnot(None)).all()
        for c in clients:
            if _has_primary(db, FollowUpEntityType.CLIENT, c.id):
                continue
            if c.owner_id is None:
                skipped_no_owner.append(str(c.id))
                continue
            print(f"  + client {c.id} ({c.name}): due {c.next_follow_up_date}")
            if confirm:
                db.add(
                    FollowUp(
                        entity_type=FollowUpEntityType.CLIENT,
                        entity_id=c.id,
                        purpose_key="primary_reminder",
                        owner_id=c.owner_id,
                        next_action=c.follow_up_note or "Follow up",
                        due_date=c.next_follow_up_date,
                        created_by_id=c.owner_id,
                    )
                )
            created += 1

        if confirm:
            db.commit()
            print(f"Backfilled {created} FollowUp row(s).")
        else:
            print(f"Dry run: would backfill {created} FollowUp row(s). Pass --confirm to write.")

        if skipped_no_owner:
            print(
                f"Skipped {len(skipped_no_owner)} unassigned client(s) with a legacy reminder but no owner_id "
                f"to attribute created_by_id to -- not backfilled, review manually: {', '.join(skipped_no_owner)}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", action="store_true", help="Actually write; default is dry-run.")
    args = parser.parse_args()
    run(confirm=args.confirm)
