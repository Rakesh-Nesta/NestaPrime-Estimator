"""Seeds Part C's 30-sport master list from app/seed_data.py.
Re-run safe: skips a sport key that already exists.
"""

from app.db.session import SessionLocal
from app.models.sport import Sport
from app.seed_data import SPORTS_SEED

db = SessionLocal()
try:
    created = 0
    for (
        key, order, name, category, playing, build,
        playing_l, playing_w, build_l, build_w,
        min_height, body,
    ) in SPORTS_SEED:
        if db.query(Sport).filter(Sport.key == key).first():
            continue
        db.add(
            Sport(
                key=key,
                display_order=order,
                name=name,
                category=category,
                playing_dims=playing,
                build_dims=build,
                playing_l_ft=playing_l,
                playing_w_ft=playing_w,
                build_l_ft=build_l,
                build_w_ft=build_w,
                min_clear_height_ft=min_height,
                governing_body=body,
            )
        )
        created += 1
    db.commit()
    print(f"Seeded {created} new sports ({len(SPORTS_SEED) - created} already existed).")
finally:
    db.close()
