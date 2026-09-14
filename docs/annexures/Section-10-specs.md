# Section 10 — Draft Specification for Director Approval

**Date: 14 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

---

## Amendment No. 11 — Rate Card & Margin Policy Tuning (from Note R1's Findings)

**Registered scope (Annexure 2, §2):** three evidence-backed candidates surfaced by Note
R1's 14 September recreate-and-compare exercise (Indian Army–Mathura Basketball, NHAI–
Noida Badminton PU Court) — rate-table gaps, labour-category % assumptions, and the flat
margin target — each requiring its own Director-approved spec before any change lands.

This spec is honest about its evidence base: **two real projects, one data point each**
for the labour-category and margin findings. That is Note R1's own registered scope
("recreate **one or two** past projects") — enough to raise a real, specific question,
not enough to treat any single percentage below as proven. Every recommendation is
scoped accordingly: narrower changes where the evidence is closer to conclusive, open
questions (not silent defaults) where it isn't.

### Part A — The three parked rate-table gaps

**Current state:** `RateItem` has no seeded rate for asphalt base, acrylic/PU court
coating, or basketball pole+board equipment. The 13 September starter-rate-card review
parked these pending accountant sign-off; the two full project rebuilds just
independently hit the exact same three gaps from a completely different data source.

**What this spec does NOT do:** propose specific ₹/unit rates. Mathura's real accounts
give *lump* costs for these categories (Acrylic Material ₹2,47,000; Ashphalt Material
₹3,47,423; BB Pole with Transport ₹78,300) but not the underlying quantities (coated
sqft, base sqm, pole count) needed to derive a defensible per-unit rate — the same
reason these were parked in the first place. Fabricating a rate from a lump sum would be
worse than leaving the gap visible.

**Proposed spec:** add three `RateItem` rows in the existing Manual/unverified state
(same pattern as the 20 September-seeded rates) with `rate = null` — present in the rate
table, sport-tagged, HSN/SAC classified where CBIC has a confident match, but not usable
in a Cost Sheet's auto-populated take-off until a PM/Director enters a real, quantity-
backed rate. This turns "no rate exists" into "a rate exists and is visibly waiting for a
number" — closes the *visibility* gap Note R1 found without inventing numbers Note R1
explicitly said it couldn't defend.

**Acceptance criteria:** the three items appear in the Rate Sheet screen with status
"awaiting rate," selectable by a PM/Director once a real figure is entered; the Cost
Sheet Builder's Base/Acrylic-PU/Structures take-off tabs surface them once rated, exactly
like every other confirmed `RateItem`.

### Part B — Labour-category % assumptions

Checked against Mathura's real material/labour split (the only project split
granular enough to isolate per-category ratios):

| Category | Current default | Mathura real | Gap |
|---|---|---|---|
| Civil / base / site prep | 30% | 21.85% | assumption too high |
| MS fabrication & erection | 22% | 6.4% (pole *installation* only) | assumption too high for installation work |
| Acrylic / PU | 20% | 22.7% | close, slightly low |
| Turf laying | 12% | 25.4% | assumption roughly half of real |
| Electrical | 25% | 31.4% | somewhat low |

**Proposed spec — two separate decisions, not one blanket change:**

**B1. MS fabrication & erection — split, don't just re-number.** The 6.4% figure is for
installing a *pre-fabricated* basketball pole+board set (bolt down, wire up) — genuinely
different work from fabricating structural steel from raw stock, which the 22% default
was presumably calibrated for. Proposed: add a second labour category, "Equipment
installation (pre-fab)," defaulted at a rate closer to the observed 6.4–10% range (leaving
headroom since N=1), and leave "MS fabrication & erection" at 22% for genuine fabrication
work. This resolves the gap without weakening a category that may be correctly priced for
what it actually describes.

**B2. The other four — flag for wider validation before changing a global default.**
Civil/base, Acrylic/PU, Turf laying, and Electrical all show real divergence, but each is
a single data point from a single project, and a global default change affects every
Cost Sheet in the system going forward. Proposed: **do not change these four defaults
from this spec alone.** Instead, add each as a named line in Note R1's own "recreate one
or two" register entry as **still open** — the next 1–2 project rebuilds (the Note
already lists Tirupati Infra Ujjain, the Volleyball court, and Turf Ujjain as unused
candidates) should specifically target Turf and Electrical-heavy scopes to either confirm
or contradict the Mathura ratios before a global default moves. This is slower but
matches the same "don't move a system-wide number off one sample" discipline the margin
question below needs.

### Part C — The flat 15% Government-competitive margin target

**The finding:** Mathura's real margin was 11.0% (below the app's own 12% floor); Noida's
was 22.9% (well above the 15% target). Both are Government/competitive-segment projects
under today's single flat policy.

**This is a business-strategy decision, not an engineering one** — I have no basis to
recommend a specific new number, and won't propose one. What I can offer is the decision
shape:

- **Keep 15% flat.** Treat Mathura as a 2022 deal that was underpriced relative to
  today's standard, and Noida as this policy correctly working as intended (the target
  being a floor for negotiation, not a prediction of every real outcome).
- **Lower the floor/target for this segment.** If Mathura-like pricing pressure is
  typical for competitive Government bids, 12%/15% may be systematically too high to win
  work at, and the policy should move — a real risk of the app quietly pricing NestaPrime
  out of deals it used to win.
- **Leave flat, but log the divergence going forward.** No policy change now; instead,
  each Quotation `below_floor` (already tracked) and each margin >5 points above target
  gets flagged for the Director's existing monthly override review (Q.2 rule 2's own
  mechanism), building a real dataset before touching the number.

**Acceptance criteria:** whichever option the Director picks, it's a single, auditable
change to `MarginPolicy`/`SportMarginPolicy` (or explicitly, a decision to make no change
yet) — not a silent default drift.

---

## Approval

Part A (three rate rows, null rate, awaiting-rate state): ☐ Approved ☐ Changes ☐ Later
Part B1 (split pre-fab installation labour category): ☐ Approved ☐ Changes ☐ Later
Part B2 (flag 4 categories, no default change yet): ☐ Approved ☐ Changes ☐ Later
Part C (margin policy): ☐ Keep 15% flat ☐ Lower floor/target ☐ Flat + log divergence
for review ☐ Later

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 14 September 2026
