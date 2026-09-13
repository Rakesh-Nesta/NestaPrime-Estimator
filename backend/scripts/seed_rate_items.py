"""Seeds Note R1's starter rate card (RATE_ITEM_SEED) from app/seed_data.py.
Re-run safe: skips a (category, item_name, spec) combo that already exists.

Every row lands as Manual/unverified (RateItem's own default) -- per J.1,
"unverified rates never become defaults." A PM/Director still has to review
and confirm each one from the Rate Sheet screen before it can drive a real
quotation.
"""

from app.db.session import SessionLocal
from app.models.rate_item import RateItem
from app.seed_data import RATE_ITEM_SEED

db = SessionLocal()
try:
    created = 0
    for category, item_name, spec, unit, hsn_sac, rate, gst_percent in RATE_ITEM_SEED:
        exists = (
            db.query(RateItem)
            .filter(
                RateItem.category == category,
                RateItem.item_name == item_name,
                RateItem.spec == spec,
            )
            .first()
        )
        if exists:
            continue
        db.add(
            RateItem(
                category=category,
                item_name=item_name,
                spec=spec,
                unit=unit,
                hsn_sac=hsn_sac,
                rate=rate,
                gst_percent=gst_percent,
            )
        )
        created += 1
    db.commit()
    print(f"Seeded {created} new rate items ({len(RATE_ITEM_SEED) - created} already existed).")
finally:
    db.close()
