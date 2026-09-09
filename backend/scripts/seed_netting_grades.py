"""Seeds Part E.3's netting grade catalogue from app/seed_data.py.
Re-run safe: skips a key that already exists.
"""

from app.db.session import SessionLocal
from app.models.netting_grade import NettingGrade
from app.seed_data import NETTING_GRADES_SEED

db = SessionLocal()
try:
    existing_keys = {g.key for g in db.query(NettingGrade).all()}
    created = 0
    for key, name, material, twine, mesh, uv_stabilized, typical_use, rate_per_sqm in NETTING_GRADES_SEED:
        if key in existing_keys:
            continue
        db.add(
            NettingGrade(
                key=key,
                name=name,
                material=material,
                twine=twine,
                mesh=mesh,
                uv_stabilized=uv_stabilized,
                typical_use=typical_use,
                rate_per_sqm=rate_per_sqm,
            )
        )
        created += 1
    db.commit()
    print(f"Seeded {created} new netting grade(s) ({len(NETTING_GRADES_SEED) - created} already existed).")
finally:
    db.close()
