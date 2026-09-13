"""Seeds Amendment 3's starter cross-sell add-on catalog (CROSS_SELL_ADDON_SEED)
from app/seed_data.py. Re-run safe: skips a `name` that already exists, and
re-tags a row's sports to match the seed list every run (idempotent, not
additive) so a re-run stays in sync if the seed list changes.

Only Fencing ships active (real cost from Note R1); Lighting/Seating/AMC
seed inactive with cost=None per Section 7's Director decision -- a PM/
Director still has to enter a real cost and activate each one from the
Cross-Sell admin screen, per J.1's "unverified rates never become defaults."
"""

from app.db.session import SessionLocal
from app.models.cross_sell_addon import CrossSellAddon, CrossSellAddonSport
from app.models.sport import Sport
from app.seed_data import CROSS_SELL_ADDON_SEED

db = SessionLocal()
try:
    created = 0
    tagged = 0
    for name, category, description, cost, unit, margin_percent, all_sports, is_active, sport_keys in CROSS_SELL_ADDON_SEED:
        addon = db.query(CrossSellAddon).filter(CrossSellAddon.name == name).first()
        if addon is None:
            addon = CrossSellAddon(
                name=name,
                category=category,
                description=description,
                cost=cost,
                unit=unit,
                margin_percent=margin_percent,
                all_sports=all_sports,
                is_active=is_active,
            )
            db.add(addon)
            db.flush()
            created += 1

        db.query(CrossSellAddonSport).filter(CrossSellAddonSport.addon_id == addon.id).delete()
        for key in sport_keys:
            sport = db.query(Sport).filter(Sport.key == key).first()
            if sport is None:
                raise ValueError(f"Sport key {key!r} not found -- run seed_sports.py first")
            db.add(CrossSellAddonSport(addon_id=addon.id, sport_id=sport.id))
            tagged += 1

    db.commit()
    print(
        f"Seeded {created} new cross-sell addons "
        f"({len(CROSS_SELL_ADDON_SEED) - created} already existed), "
        f"{tagged} sport tags applied."
    )
finally:
    db.close()
