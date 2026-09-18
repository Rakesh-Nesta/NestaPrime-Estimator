# Section 20 — Draft Specifications for Director Approval

**Date: 18 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: Amendment 10 (User Handbook), re-verified today rather than trusting this
register's own older text. Corrects a real error made earlier today (this session
described the handbook as its "largest gap" based on a stale note; a prior v3 pass, 16
September, had already closed most of it — see the corrected Amendment 10 entry above
this one). What's below is the genuinely remaining gap, now precisely scoped.

---

## Amendment No. 10, continued — Handbook Currency Pass

**Registered scope:** the handbook's own maintenance rule ("every shipped amendment
wave updates the relevant chapter") applied to Amendments 15/16/17/19, which shipped
after the last handbook pass (16-18 September touch-up).

### Current state (verified against `frontend/src/handbookData.js`, not assumed)

**Already correct, contrary to this entry's older text — no action needed:** All
Quotations, Vendors Admin, Messages Panel, Price Requests, Purchase Orders,
Cross-Sell Admin, and Hindi/Hinglish terms (*mazdoori*, *saaman*, *dhanda*) are all
already present, added in the 16 September v3 pass this register never recorded.

**Genuinely missing — two chapters never written:**
1. **Education** (Amendment 15/16) — no chapter at all for either of Education's two
   tabs: the Chat assistant (`POST /education/ask`, grounded only in the handbook
   itself) or the Sport Build Guide (per-sport dimensions/accessories/flooring/package
   data, plus Section 18's Construction Sequence section with its safety disclaimer).

**Genuinely stale — three passages describing pre-fix behavior:**
2. **Documents chapter's `watch` text** (`handbookData.js:144`) still says email
   "delivers nothing" — wrong since Section 17 (PR #89) wired up real SMTP sending.
3. **Clients chapter** (`handbookData.js:210-216`) doesn't mention the per-client
   project list Section 19 (PR #96) added.
4. **FAQ Q18** (`handbookData.js:415-418`) explicitly asserts the per-client project
   list "remains a gap" — the exact claim Section 19 closed.

**Smaller, lower-priority items found along the way (not part of Amendments 15-19,
pre-existing):**
5. Sports & Scope Admin chapter's `fields` list doesn't mention the Construction
   Sequence tab (added today, alongside item 1 above, so natural to fold in together).
6. Quick Start's in-app label still reads "v1" (`Help.jsx:142`) despite rendering v3
   content.
7. Simple Calculator and Tender Mode have never had their own chapters (referenced only
   in passing elsewhere).
8. Amendment 14's Quotation PDF "Reference Images" feature isn't mentioned in the
   Documents chapter.
9. Amendment 11's nullable "awaiting rate" state and the new "Equipment installation
   (pre-fab)" labour category aren't mentioned in the Rate Sheet chapter.

### Proposed spec

1. **Add one new "Education" chapter** to `FULL_HANDBOOK`, covering both tabs (Chat
   assistant, Sport Build Guide including its Construction Sequence section and
   disclaimer) in the same `{screen, what, fields, whenMissing, watch}` shape every
   other chapter uses — written directly from the real screen behavior (I implemented
   Sections 15, 16, and 18 this session and know their actual behavior firsthand,
   the same standard this file's own header comment sets: "drawn from the app's own
   real screen graph and behavior... not guessed").
2. **Fix the three stale passages** (items 2-4 above) to describe current behavior.
3. **Fold in the two directly-related small items** (5 and 6 above) while already
   editing this file, since they cost nothing extra to fix alongside the real work.
4. **Items 7-9 (Simple Calculator, Tender Mode, Reference Images, Amendment 11's rate
   sheet notes) are proposed out of scope for this pass** — none are regressions from
   Amendments 15-19, and bundling them in risks turning a tight, verifiable currency
   pass into a much larger content-authoring effort. Flagged here so they're on record,
   not silently dropped.
5. **No AI-drafted content, no new AI-draft-then-review flow** — unlike Section 18,
   this is direct authorship against verified current behavior (the same way the
   original handbook and its v3 pass were written), not new domain content needing a
   review gate.

**Acceptance criteria:** the Education chapter accurately describes both tabs including
the Construction Sequence disclaimer; the Documents/Clients/FAQ passages match current
app behavior with no factual claim contradicted by the code; the Sports & Scope Admin
chapter's field list includes Construction Sequence; the Quick Start label reads v4 (or
whatever version number follows the file's own existing scheme); nothing else in the
file changes.

### Open decisions — need Director input before implementation

1. **Confirm items 7-9 stay out of scope for this pass** (proposed), vs. folding them
   in now while the file is already open.
2. **Confirm no AI-draft-then-review step is needed** (proposed) — this is direct
   content authorship against code I verified myself this session, not new domain
   content requiring the Amendment 13 pattern.

---

## Approval

Amendment 10 continuation (handbook currency pass — one new Education chapter, three
stale-passage fixes, two small items folded in, items 7-9 deferred): ☑ Approved —
"approve as proposed, both decisions" (18 September 2026)

Decision 1 (items 7-9 stay out of scope for this pass): ☑ Resolved as proposed.
Decision 2 (no AI-draft-then-review step needed): ☑ Resolved as proposed.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 18 September 2026
