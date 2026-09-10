"""Seeds Part H's lux table and pole table from app/seed_data.py (the
former _LUX_TABLE and _POLE_COUNT dicts in sports.py). Re-run safe: skips
a category/sport that already has a row.
"""

from app.db.session import SessionLocal
from app.models.lighting_standard import LightingLuxStandard, SportPoleCount
from app.models.sport import Sport
from app.seed_data import LIGHTING_LUX_STANDARDS_SEED, SPORT_POLE_COUNTS_SEED

db = SessionLocal()
try:
    existing_categories = {row.category for row in db.query(LightingLuxStandard).all()}
    lux_created = 0
    for category, lux_practice, lux_match, lux_tournament in LIGHTING_LUX_STANDARDS_SEED:
        if category in existing_categories:
            continue
        db.add(
            LightingLuxStandard(
                category=category, lux_practice=lux_practice, lux_match=lux_match, lux_tournament=lux_tournament,
            )
        )
        lux_created += 1

    sport_id_by_key = {s.key: s.id for s in db.query(Sport).all()}
    existing_pole_sport_ids = {row.sport_id for row in db.query(SportPoleCount).all()}
    pole_created = 0
    for sport_key, pole_count in SPORT_POLE_COUNTS_SEED:
        sport_id = sport_id_by_key.get(sport_key)
        if sport_id is None:
            print(f"Skipping pole count for '{sport_key}' -- no seeded sport with that key")
            continue
        if sport_id in existing_pole_sport_ids:
            continue
        db.add(SportPoleCount(sport_id=sport_id, pole_count=pole_count))
        pole_created += 1

    db.commit()
    print(f"Seeded {lux_created} new lux standards ({len(LIGHTING_LUX_STANDARDS_SEED) - lux_created} already existed).")
    print(f"Seeded {pole_created} new pole counts ({len(SPORT_POLE_COUNTS_SEED) - pole_created} already existed).")
finally:
    db.close()
