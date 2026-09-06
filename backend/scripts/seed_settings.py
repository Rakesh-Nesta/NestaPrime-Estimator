"""Seeds Part Q's initial Master Settings from app/seed_data.py.
Re-run safe: skips a key that already has a row at the same effective_from.
"""

from datetime import date

from app.db.session import SessionLocal
from app.models.setting import Setting, SettingScope
from app.models.user import User, UserRole
from app.seed_data import SETTINGS_SEED

db = SessionLocal()
try:
    director = db.query(User).filter(User.role == UserRole.DIRECTOR).first()
    if not director:
        raise SystemExit("No Director user found — run seed_test_user.py first.")

    created = 0
    for key, value, unit, effective_from in SETTINGS_SEED:
        exists = (
            db.query(Setting)
            .filter(Setting.key == key, Setting.effective_from == date.fromisoformat(effective_from))
            .first()
        )
        if exists:
            continue
        db.add(
            Setting(
                key=key,
                scope=SettingScope.GLOBAL,
                value=value,
                unit=unit,
                effective_from=date.fromisoformat(effective_from),
                changed_by_id=director.id,
                reason="Initial seed from blueprint defaults",
            )
        )
        created += 1
    db.commit()
    print(f"Seeded {created} new settings ({len(SETTINGS_SEED) - created} already existed).")
finally:
    db.close()
