# Restore Drill Log (Note R2)

**Registered scope (Annexure 2, Note R2):** "Quarterly: restore a Lightsail snapshot to
a test instance and confirm app + data return correctly. A backup never restored is a
hope, not a backup."

See [`deploy/README.md`](../../deploy/README.md#backups--restore-drill-note-r2) for the
backup setup and the drill procedure itself. This file is just the record that it
actually happened, on schedule -- the "recurring, provably done" half of Note R2, not
just the capability to do it once.

Every entry: who ran it, when, which half (pg_dump drill via `restore_drill.sh`, and/or
the full Lightsail instance-snapshot restore), and the outcome. A FAIL is not a reason to
delete the row -- it's the whole reason this log exists; note what was found and what
fixed it.

| Date | Run by | pg_dump drill (`restore_drill.sh`) | Instance-snapshot drill | Notes |
|---|---|---|---|---|
| 2026-09-15 | R. Patni (with AI development assistance) | ☑ Pass | ☑ Skipped (no Lightsail/AWS console access from this session -- annual, not this quarter) | `backup_db.sh` produced a 72K gzip-integrity-checked dump of the live dev database; `restore_drill.sh` restored it into a throwaway, isolated `postgres:16` container and tore it down cleanly. Every one of 55 tables came back with its real row count intact (`users`=6, `sports`=31, `rate_items`=27 -- including the 3 awaiting-rate items and the new pre-fab labour category from Amendment 11, confirming that schema change round-trips through a real dump/restore correctly). No corruption, no empty tables, no manual fixes needed. |
| 2026-09-15 | R. Patni (with AI development assistance) | ☑ Pass | ☐ Skipped (no Lightsail/AWS console access from this session -- annual, not this quarter) | Second drill the same day, this time against **real production data** (65.1.234.78) now that SSH access existed. `backup_db.sh` produced a 28K dump; `restore_drill.sh` restored it cleanly (`users`=4, `sports`=30). **Found a real gap in the process, not the backup itself:** `labour_categories`=9 and `rate_items`=20 -- the Amendment 11 database migration had gone out with the earlier deploy, but its two one-off seed scripts (`seed_labour_categories.py`, `seed_rate_items.py`) were never run against production, only local dev. Fixed immediately: ran both scripts against production (`docker compose exec -T -e PYTHONPATH=/app backend python scripts/seed_*.py`), confirmed `labour_categories`=10 and `rate_items`=23 match local dev. Exactly the kind of gap a real drill is supposed to catch -- a migration deploying cleanly said nothing about whether its seed data went out too. |
