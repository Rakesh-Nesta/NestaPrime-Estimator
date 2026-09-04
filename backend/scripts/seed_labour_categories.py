"""Seeds Part J.2's labour category fallback percentages from
app/seed_data.py. Re-run safe: skips a category key that already exists.
"""

from app.db.session import SessionLocal
from app.models.rate_item import LabourCategory
from app.seed_data import LABOUR_CATEGORIES_SEED

db = SessionLocal()
try:
    created = 0
    for key, name, default_percent in LABOUR_CATEGORIES_SEED:
        if db.query(LabourCategory).filter(LabourCategory.key == key).first():
            continue
        db.add(LabourCategory(key=key, name=name, default_percent=default_percent))
        created += 1
    db.commit()
    print(f"Seeded {created} new labour categories ({len(LABOUR_CATEGORIES_SEED) - created} already existed).")
finally:
    db.close()
