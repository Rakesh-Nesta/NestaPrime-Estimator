"""Seeds Part O REGIONAL_MULTIPLIERS from app/seed_data.py.
Re-run safe: skips a city that already exists.
"""

from app.db.session import SessionLocal
from app.models.regional_multiplier import RegionalMultiplier
from app.seed_data import REGIONAL_MULTIPLIER_SEED

db = SessionLocal()
try:
    created = 0
    for city, labour, transport, material, climate, rainfall, coastal, wind, seismic, confirmed in REGIONAL_MULTIPLIER_SEED:
        if db.query(RegionalMultiplier).filter(RegionalMultiplier.city == city).first():
            continue
        db.add(
            RegionalMultiplier(
                city=city,
                labour_multiplier=labour,
                transport_multiplier=transport,
                material_multiplier=material,
                climate_zone=climate,
                rainfall_zone=rainfall,
                coastal=coastal,
                wind_zone=wind,
                seismic_zone=seismic,
                is_confirmed=confirmed,
            )
        )
        created += 1
    db.commit()
    print(f"Seeded {created} new cities ({len(REGIONAL_MULTIPLIER_SEED) - created} already existed).")
finally:
    db.close()
