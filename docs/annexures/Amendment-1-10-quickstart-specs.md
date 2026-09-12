# Amendment 1 + Amendment 10 (Quick Start card) — Draft Specifications

**Date: 12 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves -> complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: Section 4 of Annexure 2's own priority sequencing pairs "No. 1 (branding) +
No. 10 (handbook quick-start card)" — only the one-page Quick Start card, not the full
handbook (that's Section 5's "No. 10 full handbook + No. 6a/6c").

---

## Amendment No. 1 — Brand-Themed and Animated UI

**Registered scope (Annexure 2, §2):** "Dark premium theme, gold `#c9a227` accents,
animated sport-tile selection with court diagram, subtle motion (0.2-0.3s). 'The user is
not bored and wants to work.' Frontend styling only." (Match Company Website.)

I don't have the company website's own URL to match against pixel-for-pixel -- if you
have the link, I'll pull real reference values from it (exact fonts, imagery style,
logo usage) and revise this spec before implementing. Absent that, this spec commits
fully to the annexure's own explicit values (dark theme, `#c9a227` gold, 0.2-0.3s motion)
as the source of truth, with the remaining choices (neutrals, typography, exact motion
curves) made here as concrete decisions rather than left vague.

**Update (implementation, same day):** two real reference mockups were supplied mid-
build -- a polished marketing-page concept (gold-on-black, uppercase tracked nav, a
labelled court-diagram card, pill-style sport selector) and an earlier concept using a
flat, distinct color per sport as tile fills. Implementation below follows the first as
the system (nav, buttons, cards) and keeps the second's per-sport-color idea as a
candidate for the Sport Selection tile grid specifically, not yet built.

**Implemented so far:** shared design tokens (`frontend/src/index.css` `@theme` block:
`--color-base #0f1115`, `--color-surface #181b21`, `--color-surface-raised #20242c`,
`--color-border-dark #2c313b`, `--color-text-primary #f2f0ea`, `--color-text-secondary
#9ca3af`, `--color-gold #c9a227`, `--color-gold-hover #dbb542`, `--color-gold-muted`
-- a 10% (not 20%) alpha gold wash, dropped from the first pass because 20% read
muddy/brown over the dark base rather than premium); Sora/Inter via Google Fonts. Every
one of the app's 20 component files was migrated from the old light-mode Tailwind
classes to these tokens (a scripted, consistent class-for-class swap, then a second
pass specifically for semantic status colors -- amber/green/red warning and badge
boxes kept their hue but moved from light tints (`bg-amber-50` etc., illegible-clashing
on dark) to translucent dark-friendly versions (`bg-amber-500/10` etc.) plus lighter
text shades (`-700`/`-800` to `-400`) for contrast. Verified live across Dashboard,
login, Quick/Detailed Project Setup, Sport Selection, Documents/Cost Sheet Builder, and
Sports & Scope Admin.

**Not yet built:** the animated, per-sport SVG court-diagram on Sport Selection's tiles
and its hover/select motion (this section's own "Animated sport-tile selection with
court diagram" clause) -- next increment.

### Color tokens

| Token | Value | Use |
|---|---|---|
| `--bg-base` | `#0f1115` | Page background |
| `--bg-surface` | `#181b21` | Cards, panels, header |
| `--bg-surface-raised` | `#20242c` | Hover/active surface, inputs |
| `--border` | `#2c313b` | Card/input borders |
| `--text-primary` | `#f2f0ea` | Headings, primary text |
| `--text-secondary` | `#9ca3af` | Labels, secondary text |
| `--accent-gold` | `#c9a227` | Primary accent -- CTAs, active nav, selected states |
| `--accent-gold-hover` | `#dbb542` | Hover on gold elements |
| `--accent-gold-muted` | `#c9a22733` (20% alpha) | Gold-tinted backgrounds (selected card fill) |
| `--status-green` | `#4ade80` | Unchanged -- semantic status colors stay separate from the gold accent, not replaced by it (a green "Verified" badge must still read as green) |
| `--status-amber` | `#fbbf24` | Unchanged |
| `--status-red` | `#f87171` | Unchanged |

Gold is the *accent*, not the base -- it marks what's active, selected, or actionable
(primary buttons, the current nav item, a selected sport tile), not decoration on every
surface. Overusing it on a dark ground reads as gaudy rather than premium.

### Typography

- Headings: **Sora** (Google Fonts) -- a geometric sans with more character than the
  current default, still highly legible at small sizes for a dense data app.
  Fallback: `"Sora", "Segoe UI", sans-serif`.
- Body/UI: **Inter** stays (already the effective default via Tailwind's system stack) --
  changing the body face on a form-dense app this size is a bigger risk than it's worth;
  the heading face alone carries most of the brand identity.
- Numerals (money, quantities, project numbers): `font-variant-numeric: tabular-nums`
  wherever digits line up in a column (cost sheet lines, reports) -- not new to this
  amendment, but worth stating since the dark theme is the moment every table gets
  visually rebuilt anyway.

### Motion

- Sport tile hover/select: 0.25s ease-out on background-color, border-color, and a
  `translateY(-2px)` lift. Selecting a tile (Add) flashes the gold accent border once
  (0.3s) before settling into the "Selected" list state.
- Nav active-item underline: 0.2s ease-out width/opacity transition, not an abrupt
  color swap.
- Respect `prefers-reduced-motion`: every transition above collapses to an instant
  state change when set, no exceptions.

### "Animated sport-tile selection with court diagram"

The annexure names a *court diagram* specifically, not just a color animation. Scope for
v1: each `SportCard` (Sport Selection screen) gets a small inline SVG court outline
(the sport's own build/playing rectangle, drawn to a fixed aspect ratio from
`playing_l_ft`/`playing_w_ft` where numeric, a generic placeholder outline otherwise)
rendered in the gold accent line-work, replacing the current plain text-only card. This
is real, sport-specific content (not decoration) since the ratio is drawn from each
sport's own real dimensions -- a badminton tile's rectangle is visibly different from a
football tile's.

### Scope of the re-theme

Applies globally -- every screen shares one theme (that's the point: consistency, not
a Dashboard-only skin). Implementation order to keep review manageable, each its own
PR: (1) shared tokens + nav/header + Dashboard, (2) Project Setup + Sport Selection
(where the court-diagram animation lives), (3) remaining screens (Documents, Cost Sheet
Builder, Reports, admin screens).

**Acceptance criteria:** every screen renders against the dark palette with gold-accented
actionable elements; a sport tile shows its own court-shape outline and animates on
hover/select within the 0.2-0.3s range; semantic status colors (green/amber/red) are
never replaced by gold; `prefers-reduced-motion` is respected.

---

## Amendment No. 10 — Quick Start card (Section 4 scope only)

**Registered scope (Annexure 2, §2, item 1 of 4):** "One-page QUICK START card (the
5-step daily path, printable, kept at each desk)." The full handbook, per-role guides,
and FAQ (items 2-4) are Section 5, not built here.

### Content

The 5-step daily path, matching the app's own real screen graph (confirmed by
Amendment 4's breadcrumb, not invented fresh):

1. **Setup** -- New Project (Quick, 5 fields) or Detailed for a Government/Tender client.
2. **Sport** -- pick the sport(s), confirm or customize court size.
3. **Scope** -- tick Additional Scope items that apply; Site Survey if needed.
4. **Documents** -- build the Cost Sheet, verify it, create the Estimate.
5. **Quotation** -- release, send, and track to Won/Lost.

Each step: the screen name, one line on what it does, and the one thing a new estimator
most often gets wrong there (drawn from the "Blueprint Ledger" gaps and this session's
own findings -- e.g. step 1's line calls out that "Existing client" only starts a *new*
project, doesn't reopen one; step 4 calls out that Rate Sheet may be empty and manual
rates are the estimator's own responsibility until Note R1's rate card lands).

### Format

- A dedicated `/help` screen inside the app (new "Help" nav entry, Daily Work group --
  everyone's daily reference, not an admin tool) rendering the card using the same
  design tokens as Amendment 1.
- A "Print / Save as PDF" button on that screen using the browser's own print dialog
  (`window.print()` with print-specific CSS -- `@media print` hides the nav/chrome,
  keeps only the card), so "printable, kept at each desk" doesn't require a new PDF-
  generation backend endpoint for a document this simple.

**Acceptance criteria:** a new Sales/PM user can open Help from the nav, see the 5-step
card without leaving the app, and print exactly the card (no chrome) to a single page.

---

## Approval

Amendment 1: ☐ Approved ☐ Changes ☐ Later
Amendment 10 (Quick Start card only): ☐ Approved ☐ Changes ☐ Later

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 12 September 2026
