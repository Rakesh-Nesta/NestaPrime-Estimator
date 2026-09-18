# Section 16 — Draft Specifications for Director Approval

**Date: 18 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: a direct follow-on from live-testing Amendment 15 (Education tab AI
assistant) — the Director's own new-hire scenario surfaced a real gap the chat alone
doesn't close well: a completely new Sales person doesn't know what a sport even *needs*
to quote it, and has to interrupt someone senior to find out.

---

## Amendment No. 16 — Sport Build Guide (Education)

**Registered scope (Annexure 2, §2):** a structured, per-sport reference in Education
showing what a court/facility needs from scratch to ready-to-play — base, flooring,
lighting, accessories (pole, ring, net, etc.) — split Indoor/Outdoor, built from the
app's own real data rather than written fresh.

### Current state

Checked before proposing anything, per this session's own discipline of verifying
against the actual code rather than assuming: a real, Director-maintained, per-sport
build reference **already exists**, spread across four tables that already drive real
Cost Sheets today, none of which currently reach Education:

- **`Sport`** (`GET /sports`) — `category` (indoor/outdoor), `playing_dims`/`build_dims`.
  Confirmed directly in the seed data: `basketball_indoor` and `basketball_outdoor` are
  already two separate catalog rows (not one sport with a toggle) — exactly the
  Indoor/Outdoor split asked for, already true of the data model, not something new to
  build. Several other sports (volleyball, tennis-family, etc.) split the same way.
- **`AccessoryCatalogItem`** (`GET /accessory-catalog?sport_id=`) — item name, unit,
  quantity per court. Indoor basketball's own row already includes "Basketball goal
  (backboard + ring), 2 nos." -- exactly the pole/ring/net-type items the Director's
  scenario named directly.
- **`FlooringGuide`** (`GET /flooring-guides?sport_id=`) — primary/secondary/budget
  spec *and the rationale for each*, one row per sport. Indoor basketball: "Maple 22mm /
  PU 6mm / Vinyl 4mm, tournament standard." Outdoor: "Acrylic 3mm / PU 5mm / concrete +
  coating, weather[-resistant]."
- **`PackageContent`** (`GET /package-contents?sport_id=`) — structure/lighting/scope
  description text per sport × package tier (Budget/Standard/Premium), plus warranty
  years.
- **Lighting standards** (`GET /lighting-standards/lux`, `/pole-counts`) exist too, but
  are grouped by a lux *category* (court/football_cricket/pool/gym) derived from a
  sport's key via a code-level function (`_sport_lux_category()`), not stored directly
  per-sport — more work to surface cleanly than the other four sources. Proposed as
  optional/secondary for this wave; `PackageContent.lighting_description` alone already
  gives a plain-language lighting summary per sport × tier, which covers the Build
  Guide's actual need on its own.

All five read endpoints already grant `sales` read access (`READ_ROLES`/
`CATALOG_READ_ROLES` = sales, pm, director, procurement, site_engineer — only `ca_tax`
excluded, which has no real use for a construction reference anyway). **No new backend
endpoints are needed for the data itself** — this is close to a pure frontend assembly
task against data and access that already exist.

**Explicitly not covered by any of this**: the physical build *sequence* (excavate,
then sub-base, then flooring, then structure, then lighting, then accessories, in what
order, by whom) doesn't exist anywhere in the app today. Nothing here can be assembled
from existing data — it would be new content, written once by someone with real
construction expertise. Per Director instruction, this is Part 2, deferred to a later
wave, not attempted now.

### Proposed spec (Part 1 only)

1. **A "Build Guide" panel in Education**, alongside the existing chat (both, per
   Director instruction) — a sport picker (Indoor/Outdoor shown as their real, separate
   catalog entries wherever a sport has both) that, on selection, assembles and displays:
   playing/build dimensions, the accessory list with quantities, the flooring
   recommendation (all three tiers + rationale), and the structure/lighting/scope
   description for each package tier — one clean read-only reference view, built by
   calling the four existing GET endpoints above for the chosen `sport_id`, no new
   backend work.
2. **Same role gate as the underlying data** (`sales`, `pm`, `director`, `procurement`,
   `site_engineer` — not `ca_tax`), narrower than Education's own current fully-open
   gate. This is a deliberate, small exception: the Build Guide surfaces real catalog/
   construction data that already has its own established gate elsewhere in the app: the
   chat panel stays open to every role as today.
3. **The chat assistant's context gains the same data**, not a separate copy — when a
   sport is mentioned or selected, the assistant's grounding material includes that
   sport's real accessory/flooring/package-tier data too, so a freeform question ("what
   does outdoor basketball need?") and the structured Build Guide screen never disagree
   with each other. Single source of truth, same principle Section 15 already
   established for the static handbook.
4. **Part 2 (construction sequence) is out of scope for this wave** — flagged here so
   it's on record as the intended next step, not forgotten, but not built until someone
   actually authors that content.

**Acceptance criteria:** picking "Basketball (Indoor)" and "Basketball (Outdoor)" in the
Build Guide shows two different, correct accessory/flooring/package-tier breakdowns,
matching what Sports & Scope Admin's own records currently say; a Sales user can reach
and read the Build Guide (not `ca_tax`); asking the chat assistant about a sport's
requirements gives an answer consistent with what the Build Guide screen shows for that
same sport; nothing here writes to the database — it's read-only, same as Education's
chat.

### Open decisions — need Director input before implementation

1. **Confirm the role gate narrowing** (Build Guide: sales/pm/director/procurement/
   site_engineer, not ca_tax) vs. keeping it as open as the chat panel (every role,
   including ca_tax) for consistency with the rest of Education. Proposed: match the
   underlying data's existing gate, per above.
2. **Lighting lux/pole-count standards** — include now (needs the extra
   `_sport_lux_category()` mapping step) or rely on `PackageContent.lighting_description`
   alone for this wave, adding the raw standards later if actually needed. Proposed:
   `lighting_description` alone is enough for this wave.
3. **Confirm Part 2 stays deferred** — construction sequence as a distinct future wave,
   not attempted now, since it needs new content authored by someone with real
   construction expertise, not assembled from existing data.

---

## Approval

Amendment 16 (Sport Build Guide, Part 1 -- existing-data assembly, chat + structured
screen both): ☐ Approved ☐ Changes ☐ Later

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 18 September 2026
