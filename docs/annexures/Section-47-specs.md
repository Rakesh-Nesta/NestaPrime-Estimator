# Section 47 — Spec Doc

## Amendment No. 41 — Overview Visual Reskin (Serif/Amber Theme, Live Clock, Motion)

**Registered scope:** see `docs/annexures/Annexure-2.md`, Amendment No. 41. **Director-
confirmed constraint: visual/theme only.** Every layout position already shipped in
Amendment 36 (breadcrumb top-left, top bar top-right, tab strip, KPI tile grid, two-panel
row, Recent Projects + Your Next Moves) stays exactly where it is. This amendment changes
how things look, not where they sit.

### Current state

`frontend/src/index.css` (Amendment 1): dark base (`#0f1115`), gold accent (`#c9a227`),
Sora/Inter fonts, no live clock, no entrance/count-up/sparkline motion beyond the existing
hover-lift transitions. Reference: a Director-supplied standalone HTML/CSS/JS file
(`Desktop\NPS-APP\HTML_Code.html`), confirmed via side-by-side browser comparison against
the live Overview page as the actual expectation behind the original "dynamic and
interactive" request.

### Proposed spec

1. **New theme tokens** in `index.css`, replacing/extending Amendment 1's -- near-black
   background variants, an amber accent family (`--amber`, `--amber-hi`, `--amber-dim`,
   `--amber-line`), a serif display font for headings, a monospace font for labels/data
   (the reference's own "Iowan Old Style" is an Apple-only system font with no
   cross-platform equivalent -- a real, loadable Google Fonts serif with a similar warm,
   editorial character is substituted; exact face confirmed against a live preview, not
   locked here -- see Open Decision 1).
2. **Live clock + time-of-day greeting** ("Good evening, {name}") in the top bar --
   pure client-side, real system time, no backend change. Honest by construction: it's
   just the clock.
3. **Motion**: entrance animation on page load (cards rising into place), animated
   count-up on the two already-real KPI numbers (Pending Quotations, Active Projects) --
   real data, just animated on arrival, not fabricated. Card hover lift extended to match
   the reference's weight.
4. **Pill-style status badges** (e.g. "Open" badge on Recent Projects rows) -- cosmetic
   only, no data change.
5. **Sparkline chrome on KPI tiles**: reserved visual space, but **no line is drawn**
   for Pending Quotations/Active Projects -- there is no stored historical trend data
   (no daily snapshot of these counts anywhere in the schema) to draw a real one from,
   and drawing an arbitrary line would be fabricated data. Revisit once real trend
   history exists.
6. **Live activity ticker: NOT built in this amendment**, pending Open Decision 2 below.
7. **Blast radius**: `index.css`'s tokens are global (`:root`), and the Sidebar/top bar
   are already persistent app-wide chrome -- so the new palette and fonts will be visible
   on every screen immediately, not just Overview, even though this amendment's
   *functional* additions (clock, count-up, motion) are scoped to Dashboard.jsx/
   Sidebar.jsx/App.jsx's top bar only. This is treated as intentional (see Open Decision
   3), avoiding a jarring two-tone app with old-gold and new-amber screens coexisting.

**Acceptance criteria:**
- No layout position changes anywhere -- confirmed by a direct before/after comparison
  against the current live Overview.
- The two real KPI numbers still show real data, now with a count-up animation on load.
- No fabricated data anywhere: no drawn sparkline trend line, no activity ticker unless
  Open Decision 2 approves one sourced from real Audit Log data.
- `prefers-reduced-motion` is respected (matching Amendment 1's own existing acceptance
  criterion for this app) -- every animation collapses to an instant state change.
- Clean production build, no new console errors, verified on both director and sales
  roles.

### Open decisions

1. **Exact serif/mono font substitutes for "Iowan Old Style"/the reference's mono
   labels.** Proposed default: **Fraunces** (serif display, warm/editorial character,
   available on Google Fonts, pairs well with the existing Inter body face) and keep
   the existing system monospace stack for labels. Confirmed against a live preview
   before merge, not locked purely on paper.
2. **Live activity ticker -- build it or not?** This is functionally the same concept as
   the "Recent Activity" feed Amendment 12 explicitly *removed* from this Dashboard for
   being "noise, not signal, in real usage." Proposed default: **do not build it in this
   amendment** -- keep the live clock/greeting (new, genuinely useful, low-noise) but
   drop the ticker specifically, given it already failed once in real usage. If the
   Director wants to revisit it, that's a deliberate, separate decision, not a default.
3. **Global token replacement (proposed default) vs. scoping the new palette/fonts to
   only Overview's own components, leaving every other screen on the old gold theme
   until each gets its own future pass?** Proposed default: **global replacement** --
   the Sidebar is already visible on every screen regardless of scoping choice here, so
   a "scoped" approach still can't avoid the new look appearing everywhere; better to
   have one consistent theme than two clashing ones mid-transition.

## Approval

☑ Approved — "approve as proposed, all decisions" (22 September 2026).

---
Prepared by: R. Patni (with AI development assistance) | Date: 22 September 2026
