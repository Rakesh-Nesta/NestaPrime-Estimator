# Section 18 — Draft Specifications for Director Approval

**Date: 18 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: Part 2 of Amendment No. 16 (Sport Build Guide) — the step-by-step
construction *sequence* that Section 16's own spec explicitly deferred: *"real, separate,
new content that doesn't exist anywhere in the app yet... deferred to a later wave rather
than invented now."* Director instruction: *"build the construction sequence for the
Sport Build Guide."*

---

## Amendment No. 16, Part 2 — Construction Sequence

**Registered scope (Section 16 spec, Decision 3):** the order things are physically
built — excavate, then sub-base, then flooring, then structure, then lighting, then
accessories — per sport, shown alongside Part 1's existing-data Build Guide screen.

### Why this can't be built the way Part 1 was

Part 1 was a pure assembly task: every fact it shows (dimensions, accessories, flooring
spec, package description) already existed in a Director-verified table driving real
Cost Sheets. A construction sequence is different in kind — it is a genuinely new piece
of domain content (what order a court gets built in, by whom, with what dependencies)
that does not exist anywhere in this app's data today. Two honest ways to get it exist,
and only one matches how this project already handles exactly this situation:

- **Someone writes it from scratch**, sport by sport, with real construction expertise —
  accurate, but the entire reason Amendment 13 exists (AI-assisted content) is that
  hand-authoring this kind of content for every sport is slow and this project has
  already chosen not to do that where an AI-assisted, human-reviewed alternative exists.
- **AI-drafted, Director-reviewed before it's ever shown to a Sales user** — the exact
  pattern Amendment 13 established for Cover Notes, client messages, and report
  summaries: *"AI-drafted content must always be human-reviewed before it is sent or
  saved as final -- no auto-send."* This proposal follows that precedent rather than
  inventing a new one.

### Proposed spec

1. **New table `ConstructionSequenceStep`** (`sport_id`, `step_order`, `phase`,
   `description`) — one row per step, per sport. Six fixed `phase` values matching the
   Director's own scenario almost verbatim (*"base, flooring, lighting, pole, Dunkin
   ring... all things and process"*): `site_prep`, `sub_base`, `flooring`,
   `structure_fixtures`, `lighting`, `accessories_finishing`. Director/Admin-editable
   from Sports & Scope Admin, same place `FlooringGuide`/`AccessoryCatalogItem`/
   `PackageContent` are already managed — not a new admin surface, an extra tab on the
   existing one.
2. **"Draft with AI" in Sports & Scope Admin**, same pattern as Amendment 13's Cover
   Note / message / report-summary buttons: calls `ai_content.py` (already wired,
   already fails fast if `ANTHROPIC_API_KEY` is unset) grounded in *that sport's own*
   real data — its dimensions, its `AccessoryCatalogItem` rows, its `FlooringGuide`
   spec, its `PackageContent` description — never invented from nothing. Produces a
   draft ordered step list into the six phases above. **Nothing is saved until the
   Director reviews and explicitly saves it** — identical to how a drafted Cover Note or
   message never auto-sends.
3. **Build Guide screen gains a "Construction Sequence" section** (Education, same
   screen as Part 1) — shown only for a sport that actually has saved steps. A sport with
   no authored sequence yet shows nothing for this section, the same no-fabrication
   guardrail already proven in Amendment 15's chat ("I don't know, check Sport
   Selection" rather than inventing a number) — never a placeholder implying content
   exists when it doesn't.
4. **Standing disclaimer** on the Construction Sequence section, always shown alongside
   real content: *"General build sequence — confirm against site conditions with a
   qualified site engineer before execution."* This is physical/safety-relevant content
   in a way Part 1's reference data isn't; the disclaimer says plainly that this is
   guidance, not a site-specific method statement.
5. **Chat assistant's grounding data extends to include saved sequences** once a sport
   has them — same single-source-of-truth principle Section 15/16 Part 1 already
   established, so a freeform question ("what order do we build outdoor basketball?")
   never disagrees with the structured screen.
6. **Same read role gate as the rest of the Build Guide** (`sales`, `pm`, `director`,
   `procurement`, `site_engineer`, not `ca_tax`); authoring/editing gated the same as the
   rest of Sports & Scope Admin (Director/Admin only).

**Acceptance criteria:** Director can open Sports & Scope Admin for a sport, click "Draft
with AI," see a six-phase draft grounded in that sport's real accessory/flooring/package
data, edit and save it; the Build Guide screen then shows that sport's Construction
Sequence section with the disclaimer, in phase order; a sport with nothing saved shows no
section at all (not an empty one); a Sales user can read it, `ca_tax` cannot reach Build
Guide at all (unchanged from Part 1); nothing is AI-published without an explicit
Director save, matching Amendment 13's no-auto-send rule.

### Open decisions — need Director input before implementation

1. **Fixed six phases (as proposed) vs. free-form steps** the Director defines per sport.
   Fixed phases keep every sport's sequence comparable and match the Director's own
   scenario wording closely; free-form is more flexible but a new Sales user gets a less
   consistent screen sport-to-sport. Proposed: fixed six phases.
2. **Authoring order** — author sequences for all sports currently in the Build Guide
   before this ships, or ship the feature now and let sports gain a sequence over time
   (same as how `FlooringGuide`/`AccessoryCatalogItem` were filled in gradually, not all
   at once). Proposed: ship now, fill in per-sport as the Director gets to each one —
   consistent with point 3 above (a sport with nothing saved just shows nothing).
3. **Disclaimer wording** — confirm the exact text in point 4, or supply alternate
   wording.
4. **Confirm the AI-draft-then-review pattern** (point 2) is the intended approach, vs.
   the Director writing every sport's sequence directly with no AI assist.

---

## Approval

Amendment 16, Part 2 (Construction Sequence — six-phase `ConstructionSequenceStep`
table, AI-draft-then-Director-review authoring, Build Guide display + chat grounding):
☐ Pending Director approval.

Decision 1 (fixed six phases): ☐ Pending.
Decision 2 (ship now, author sports incrementally): ☐ Pending.
Decision 3 (disclaimer wording): ☐ Pending.
Decision 4 (AI-draft-then-review authoring): ☐ Pending.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 18 September 2026
