# Blueprint Ledger — audit closure notes

An internal completion audit ("Blueprint Ledger") checked this codebase against
`FINAL_NESTAPRIME_MASTER_BLUEPRINT_v5.1.14.md` line-by-line and produced a
19-item ranked gap list. All 19 are now closed. This note records what each
gap actually was, the commit that closed it, and — for the handful that
needed a real judgment call rather than a straightforward build — why that
call was made. It exists so a future audit doesn't have to re-derive context
that only existed in a chat session.

## The 19 gaps, in ranked order

| # | Gap | Closed in |
|---|---|---|
| 1 | Estimate/Quotation revision on an already-Sent document (M.2 rule 4) | `25e0af1` |
| 2 | A jobs runner (check-on-read, not a scheduler) for expiry/SLA/reminders | `ec29756` |
| 3 | Client-side consent tracking for Messages | `6ace676` |
| 4 | Internal-document domain restriction (Cost Sheet/Consumption/BOM never leave the company domain) | `9805786` |
| 5 | Regional multipliers actually applied to a rate computation | `6a30b2e` |
| 6 | Small-job fast-track (M.2 rule 8) | `f5a4dfc` (PR #4) |
| 7 | Procurement-safe Consumption Sheet / BOM exports (K.3) | `89cefa4` (PR #5) |
| 8 | PACKAGES content-master table | `91ddd55` |
| 9 | Director-editable technical catalogues | `f57192a` (PR #6) — **scope narrowed, see below** |
| 10 | D.4 site-preparation take-offs (priced lines, not just flags) | `f9cc9e9` |
| 11 | Rate-sheet bulk actions | `337ace4` |
| 12 | E.3 netting grade catalogue (N1–N4) | `ff217b6` |
| 13 | HUBS master table | `0c715dd` |
| 14 | Client-type auto-defaults (B.2) | `5d60051` |
| 15 | Freight tonnage → trips, and the >100 km site-establishment uplift | `653ba40` |
| 16 | Message template library | `5db72d8` |
| 17 | Company logo upload, embedded in PDFs | `05e2896` |
| 18 | Tender GST inclusive/exclusive toggle & live L1 view | `c1185b8` — **built despite a blueprint contradiction, see below** |
| 19 | Granular (category-grouped) Tender BOQ | `4211d65` — **scope decided explicitly, see below** |

## Judgment calls worth remembering

### #9 — "Director-editable technical catalogues" was narrower than it read

The audit's one-line description named five catalogues: `FLOORING_MASTER`,
`STRUCTURE_MASTER`, `NETTING_MASTER`, `FIXTURE_MASTER`, `EQUIPMENT_CATALOGUE`.
Before building anything, each was traced to its real code:

- **`NETTING_MASTER`** and **`EQUIPMENT_CATALOGUE`** were already closed —
  `NettingGrade` and `AccessoryCatalogItem` (gap #12) had already replaced
  the hardcoded dicts these two names referred to. Nothing left to do.
- **`STRUCTURE_MASTER`** (`STRUCTURE_DEFAULTS`, `PIPE_WEIGHT_KG_PER_M` in
  `structures.py`) is real IS 1239 engineering data — pipe weights and
  foundation defaults, not a business figure a Director tunes. The
  codebase's own `AccessoryCatalogItem` docstring had already made this
  argument when gap #12 was built, explicitly excluding these two constants
  from that migration. Re-confirmed and left hardcoded, on the same
  reasoning — this was raised with the user, who agreed to leave it out of
  scope rather than override that existing judgment.
- **`FLOORING_MASTER`** (`_FLOORING_TABLE`) and **`FIXTURE_MASTER`**
  (`_LUX_TABLE`, `_POLE_COUNT`, `_FIXTURE_LUMENS`/`_FIXTURE_SPEC`) were the
  two genuine gaps, and are what `f57192a` actually built: `FlooringGuide`,
  `LightingLuxStandard`, `SportPoleCount` tables, plus two Master Settings
  keys for the (single, global) default fixture spec.

So "gap #9 closed" means two of five named catalogues were built as tables;
two were already done under a different gap number; and one was confirmed,
not converted, to stay hardcoded — a real, considered outcome, not a partial
miss.

### #18 — Part L's GST toggle contradicts K.4's later "flat rate" decision

Part L's Tender Mode table has a "Price basis" row calling for a per-document
inclusive/exclusive GST toggle. K.4, later in the same document (and citing
a dated "Director decision"), says GST is a flat, Master-Settings-only rate
with **no per-document override** — reinforced by the v5.1.9 data-model note
that a `gst_mode` field was deliberately *removed* from `QUOTATIONS`.

Both readings are explicit and dated; neither is a stray earlier draft. This
was raised with the user directly rather than silently picking a side. The
decision: build both — treat Tender Mode as a deliberate, documented
carve-out from K.4, scoped so `gst_mode=inclusive` only becomes selectable
on a Tender Mode (Government client) project. Every private Quotation keeps
K.4's exclusive-only behaviour untouched. See `GstMode`'s docstring in
`backend/app/models/document.py` for the full reasoning kept in the code
itself.

### #19 — how granular is "granular"?

The audit's own text for this gap already flagged it as defensible as a
lump-sum line, since no client-facing per-material take-off exists anywhere
else in the app either. Making it granular meant exposing internal
`CostSheetLine` data (K.3-protected, cost-side only) on a client-facing PDF
for the first time — a real architectural decision, not a bug fix. Given a
choice between full per-line detail, category-grouped rows, or leaving it
deferred, the user chose **category-grouped**: one BOQ row per
work-package/category, apportioned by cost share from the sport's own
selling total, never printing a raw cost rate. See
`_granular_boq_rows_for_sport`'s docstring in
`backend/app/api/pdf_documents.py`.

## Where to look for more detail

Every gap's own commit message has the full build/test/live-verification
account. The original audit itself (title "Blueprint Ledger") is a published
artifact — ask whoever ran the audit session for the link if you need the
full per-Part scoring detail behind the ranked list.
