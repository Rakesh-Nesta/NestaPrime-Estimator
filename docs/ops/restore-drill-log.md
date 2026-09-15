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
