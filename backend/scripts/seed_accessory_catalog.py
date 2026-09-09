"""Seeds Part I's accessory catalog from app/seed_data.py (the former
ACCESSORY_CATALOG dict in accessories.py). Re-run safe: skips a
(sport_key, item_name) pair that already exists.
"""

from app.db.session import SessionLocal
from app.models.accessory_catalog_item import AccessoryCatalogItem
from app.models.sport import Sport
from app.seed_data import ACCESSORY_CATALOG_SEED

db = SessionLocal()
try:
    sport_id_by_key = {s.key: s.id for s in db.query(Sport).all()}
    created = 0
    for sport_key, item_name, unit, quantity_per_court in ACCESSORY_CATALOG_SEED:
        sport_id = sport_id_by_key.get(sport_key)
        if sport_id is None:
            print(f"Skipping '{item_name}' -- no seeded sport with key '{sport_key}'")
            continue
        exists = (
            db.query(AccessoryCatalogItem)
            .filter(AccessoryCatalogItem.sport_id == sport_id, AccessoryCatalogItem.item_name == item_name)
            .first()
        )
        if exists:
            continue
        db.add(
            AccessoryCatalogItem(
                sport_id=sport_id,
                item_name=item_name,
                unit=unit,
                quantity_per_court=quantity_per_court,
            )
        )
        created += 1
    db.commit()
    print(f"Seeded {created} new accessory catalog items ({len(ACCESSORY_CATALOG_SEED) - created} already existed).")
finally:
    db.close()
