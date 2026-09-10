"""Seeds Parts F.1/F.2's flooring guide from app/seed_data.py (the former
_FLOORING_TABLE dict in sports.py). Re-run safe: skips a sport that
already has a FlooringGuide row.
"""

from app.db.session import SessionLocal
from app.models.flooring_guide import FlooringGuide
from app.models.sport import Sport
from app.seed_data import FLOORING_GUIDES_SEED

db = SessionLocal()
try:
    sport_id_by_key = {s.key: s.id for s in db.query(Sport).all()}
    existing_sport_ids = {row.sport_id for row in db.query(FlooringGuide).all()}
    created = 0
    for sport_key, primary_spec, secondary_spec, budget_spec, rationale in FLOORING_GUIDES_SEED:
        sport_id = sport_id_by_key.get(sport_key)
        if sport_id is None:
            print(f"Skipping '{sport_key}' -- no seeded sport with that key")
            continue
        if sport_id in existing_sport_ids:
            continue
        db.add(
            FlooringGuide(
                sport_id=sport_id,
                primary_spec=primary_spec,
                secondary_spec=secondary_spec,
                budget_spec=budget_spec,
                rationale=rationale,
            )
        )
        created += 1
    db.commit()
    print(f"Seeded {created} new flooring guides ({len(FLOORING_GUIDES_SEED) - created} already existed).")
finally:
    db.close()
