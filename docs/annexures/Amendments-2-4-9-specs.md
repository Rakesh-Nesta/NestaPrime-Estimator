# Amendments 2, 4, 9 — Draft Specifications for Director Approval

**Date: 12 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change Process
(Part 1): "Director approves → complete amended specification prepared. Only then implement."
Implementation starts next session, pending item-by-item sign-off below.**

Scope note: these are the three amendments the Director's 12 Sep handoff brief scoped for
today ("Task 3 -- prepare the SPECS for approval today; implementation starts next session").
Amendment 4's scope below folds in the four navigation gaps found live on production during
today's Task 2 validation run (see the Task 2 report) -- they are exactly what Amendment 4
already exists to fix, so this spec treats them as the concrete acceptance criteria rather
than a separate ask.

---

## Amendment No. 2 — Simplified "New Project Setup" Form

**Registered scope (Annexure 2, §2):** Blind-quoting principle -- 5 required fields (Client,
Sport, City, Dimensions, Base scope/status); soil type, distance, court count, site access,
power/water removed to T&C; Quick vs Detailed modes.

### Current state (as verified live today)
The New Project Setup screen asks for all of these before a project can be created: Project
type, Client, City, Site address, Nearest hub, Distance from hub, Site condition, Soil type,
Building status, Site access, Power available, Water available, Number of courts, Unit
system, Package, Safe bearing capacity -- 15 fields, one screen, no tiering.

### Proposed spec: two modes

**Quick mode (new default).** Five fields only:

| Field | Behaviour |
|---|---|
| Client | Required -- existing New/Existing client toggle unchanged |
| Sport | Required -- moved up from the current second screen into this same step |
| City | Required -- unchanged (10 confirmed cities + Other) |
| Dimensions | Required, but pre-filled with the sport's standard build size; one click accepts it, or "Customize" reveals L/W (this is also Amendment 9's UI, reused here) |
| Base scope / status | Required -- project_type (New Build/Resurfacing/Repair/Supply only) |

Submitting Quick mode creates the project and the sport selection in one step, using these
defaults for every field it hides:

| Hidden field | Quick-mode default | Where it's disclosed |
|---|---|---|
| Site address | blank | T&C: "Site address to be confirmed before survey" |
| Hub / Distance from hub | blank | T&C: "Distance-based logistics costed at actuals" |
| Site condition | Level | T&C: "Site assumed level pending physical survey" |
| Soil type | Normal | T&C: "Soil test required before construction if site conditions differ (D.4)" |
| Building status | Open air | Carried from the Sport step's building-status selector (unavoidable -- D.4's soil-test/rock-breaking triggers and the sport build matrix both depend on it, so it can't be fully hidden; it rides along with the Sport field, not the T&C list) |
| Site access | Good | T&C: "Site access assumed unrestricted; narrow-road/no-crane surcharge applies if not" |
| Power / Water available | Yes / Yes | T&C: "Power and water assumed available on site" |
| Number of courts | 1 | Editable later, before Documents stage |
| Unit system | Feet | Editable later |
| Package | B.2 auto-default by client type (unchanged) | Shown, editable |
| Safe bearing capacity | blank | Unchanged -- already blank until a soil report exists |

The T&C block above prints on the Quotation footer (new content, ties into the existing PDF
generation) so blind-quoting assumptions are visible to the client, not just internal.

**Detailed mode.** A toggle/link ("Need more detail? Switch to Detailed setup") reveals every
field the form has today, in the same layout as now. Government/Tender clients and any client
type without a package default still get routed to Detailed mode automatically, since B.2's
tender-specific fields (EMD/BG/DLP/cess) need the fuller form.

**Acceptance criteria:** a Quick-mode project can be created in 5 field-fills; a Detailed-mode
project behaves exactly as today's form does; T&C text for every hidden field appears on the
generated Quotation PDF.

---

## Amendment No. 4 — Main Dashboard + Guided Navigation

**Registered scope (Annexure 2, §2):** Business-summary dashboard; link back to dashboard from
every section; guided step-path with progress bar; menu grouped Daily Work / Management /
Admin. "The app itself is the training."

**Why this is more urgent than its Section-1 ranking already implied:** today's Task 2 run hit
the same class of gap four separate times on the live app:
1. No logout control anywhere in the UI (found in an earlier session).
2. No screen to browse/list existing users (found in an earlier session, User Management gap).
3. No screen to browse/list existing projects -- confirmed twice today (New Project Setup's
   "Existing client" picker only starts a *new* project against that client; the Clients
   directory has no per-client project links, only compliance toggles).
4. The "Back to project" nav button always opens a blank New Project Setup screen, regardless
   of whether a project is actually in progress -- it does not resume anything.

All four are the same underlying problem: screens exist individually with no connective
navigation between them. Amendment 4 is the fix already scoped for exactly this; the four
items below are its acceptance criteria, not scope creep.

### Proposed spec

**New Dashboard screen** (becomes the post-login landing page, replacing "wherever the last
click left you"):
- Summary tiles: open projects, pending estimates, pending quotations, overdue clients
  (Part O's overdue_flag), this month's won value.
- **Recent projects list** -- last N projects, each row clickable through to that project's
  Documents / Cost Sheet / Estimate stage. This is the direct fix for gap #3.
- Recent activity feed (last N audit-log-visible events).

**Guided step-path**, shown as a persistent breadcrumb/progress bar on every project screen:
`Setup → Sport → Scope → Documents → Cost Sheet → Estimate → Quotation`, each completed step
clickable to jump back into it.

**Every section gets a "← Dashboard" link**, distinct from the existing "← Back" (previous
step). Fixes the "dead end with only a Back button" pattern behind gaps #3 and #4.

**Nav menu regrouped:**
- *Daily Work*: Dashboard, Pricing Calculator, current project shortcuts.
- *Management*: Clients, Reports, Price Requests.
- *Admin*: Master Settings, Sports & Scope Admin, User Management, Audit Log.

**Fix for gap #4:** "Back to project" is replaced by the Dashboard's recent-projects list (a
real, server-persisted resume path) rather than a client-side "remember the last project"
patch -- so it survives a login, a page reload, or a different device, not just the current
browser tab's React state.

**Fix for gap #1:** Logout becomes a permanent, visible control next to the user's name/role
in the top-right of the nav bar on every screen (currently absent entirely).

**Fix for gap #2:** covered by User Management's own existing screen -- Amendment 4 adds it to
the Admin nav group above so it's reachable, closing the last piece of that gap.

**Acceptance criteria:** from a fresh login, a Director can open a project created a week ago
without recreating it; every screen has both a Back and a Dashboard link; Logout is visible
everywhere; User Management is reachable from the nav.

---

## Amendment No. 9 — Flexible Court Sizing

**Registered scope (Annexure 2, §2):** Standard sizes become configurable suggestions per
sport -- adjustable smaller/larger per project; admin-editable (links to Amendment 5).

### Current state (as verified live today)
Each take-off calculator (Acrylic/PU, Base, Lighting, etc.) already has optional, per-line
"Build L (ft)" / "Build W (ft)" fields that default to the sport's standard size (confirmed
today: Badminton defaults to 52×30 ft club build) if left blank. The override exists, but it's
buried inside each individual take-off form -- there is no single, visible "this project's
court size" decision point, and no admin screen to change what the sport-wide standard even is.

### Proposed spec

- **New "Court size" step** in Sport Selection, shown right after a sport is picked and before
  Additional Scope: displays the sport's standard playing and build dimensions, with a
  "Customize size" toggle. Leaving it alone carries the standard size through every take-off
  automatically (as today); toggling it opens L/W fields that then apply as the default for
  every take-off line for that sport on that project (removing the need to re-enter the same
  override on each individual calculator).
- **Validation floor:** custom dimensions may not go below the sport's federation *playing*
  dimensions (e.g. BWF Badminton's 44×20 ft playing area is fixed by the sport itself) --
  only the *build* (surround/clearance) dimensions are adjustable. Enforced the same way D.4's
  other hard constraints are today.
- **Admin-editable standard sizes:** Sports & Scope Admin gets a per-sport default-dimensions
  editor (Director/Admin only), so the *standard* Badminton build size itself can be tuned
  without a code change -- this is the piece that "links to Amendment No. 5" in the register,
  since it's the same admin-controlled-defaults pattern that amendment introduces.
- No change needed to the cost-sheet calculation engine itself: today's take-offs already read
  Build L/W per line (confirmed during today's Cost Sheet build for the Pathankot validation
  run) -- this amendment is UI surfacing plus an admin editor, not new arithmetic.

**Acceptance criteria:** a Director can change Badminton's standard build size once in Sports &
Scope Admin and see it reflected as the new default on the next project's Court Size step; a
Sales/PM user can override size once per project and have it apply across every take-off for
that sport without re-entering it per calculator; playing-dimension floors are enforced.

---

## Approval

Amendment 2: ☐ Approved ☐ Changes ☐ Later
Amendment 4: ☐ Approved ☐ Changes ☐ Later
Amendment 9: ☐ Approved ☐ Changes ☐ Later

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 12 September 2026
