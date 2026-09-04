"""Seeds Part I's 30-item scope checklist from app/seed_data.py.
Re-run safe: skips a scope item key that already exists.
"""

from app.db.session import SessionLocal
from app.models.scope_item import ScopeItem
from app.seed_data import SCOPE_ITEMS_SEED

db = SessionLocal()
try:
    created = 0
    for key, order, group, name in SCOPE_ITEMS_SEED:
        if db.query(ScopeItem).filter(ScopeItem.key == key).first():
            continue
        db.add(
            ScopeItem(
                key=key,
                display_order=order,
                group=group,
                name=name,
            )
        )
        created += 1
    db.commit()
    print(f"Seeded {created} new scope items ({len(SCOPE_ITEMS_SEED) - created} already existed).")
finally:
    db.close()
