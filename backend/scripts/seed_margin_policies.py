"""Seeds Part K.2's margin floor policy per client type from
app/seed_data.py. Re-run safe: skips a client type that already exists.
"""

from app.db.session import SessionLocal
from app.models.margin_policy import MarginPolicy
from app.seed_data import MARGIN_POLICY_SEED

db = SessionLocal()
try:
    created = 0
    for client_type, floor_margin_percent, competitive_segment in MARGIN_POLICY_SEED:
        if db.query(MarginPolicy).filter(MarginPolicy.client_type == client_type).first():
            continue
        db.add(
            MarginPolicy(
                client_type=client_type,
                floor_margin_percent=floor_margin_percent,
                competitive_segment=competitive_segment,
            )
        )
        created += 1
    db.commit()
    print(f"Seeded {created} new margin policies ({len(MARGIN_POLICY_SEED) - created} already existed).")
finally:
    db.close()
