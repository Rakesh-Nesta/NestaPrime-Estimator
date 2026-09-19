# Section 21 — Draft Specifications for Director Approval

**Date: 19 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: Amendment 2's remaining gap, re-verified today rather than trusting the
register's own older text (same discipline used on several other entries this week) --
this time the verification confirmed the gap is real, not stale.

---

## Amendment No. 2, continued — Quick Mode's Missing Dimension Step

**Registered scope:** Quick mode asks only 4 fields, not the spec'd 5 (Client, Sport,
City, Dimensions, Base scope/status) -- Dimensions is shown as read-only text, never
something the user actually enters.

### Current state (verified against `frontend/src/ProjectSetup.jsx` and `App.jsx`)

The register's literal framing -- "add a 5th input field" -- doesn't match how
dimensions actually work in this app, and a spec written to that framing would fight
the existing architecture:

- Dimensions are not a `Project`-level concept anywhere in this app. They live on
  `ProjectSport` (`custom_build_l_ft`/`custom_build_w_ft`, `actual_l_ft`/`actual_w_ft`),
  set via `CourtSize`/`ActualDimensions` on `SportSelection.jsx` -- true for **both**
  Quick and Detailed mode. Detailed mode's own form (`ProjectSetup.jsx` lines 403-554)
  has no literal "Dimensions" field either.
- The real difference is routing. `App.jsx:461-462`:
  ```js
  onProjectCreated={(project) => { setActiveProject(project); setScreen("sports"); }}      // Detailed
  onQuickSetupComplete={(project) => { setActiveProject(project); setScreen("scope"); }}   // Quick
  ```
  Detailed mode always passes through Sport Selection -- the one screen where dimension
  customization genuinely happens -- before Scope. Quick mode skips straight to Scope.
  The only way back is an easy-to-miss "← Back to Sport Selection" link on the Scope
  screen, not a step of the Quick flow itself.
- Quick mode's own on-screen copy compounds this: *"Dimensions: standard build {X} ft
  (customizable once Amendment 9 ships)"* -- Amendment 9 shipped the same day as this
  copy was written (12 September); it's been stale the entire time, actively telling
  users a capability isn't available when it is, one screen away that Quick mode never
  reaches.

### Proposed spec

1. **Quick mode routes through Sport Selection too**, matching Detailed mode exactly --
   change `onQuickSetupComplete` to route to `screen="sports"` instead of
   `screen="scope"` (one line, `App.jsx`). The sport Quick setup already adds via
   `addProjectSport` (standard build size, 1 court) shows up there exactly as it would
   coming from Detailed mode, fully editable -- same screen, same component, no
   duplicated logic.
2. **Fix the stale copy** on `ProjectSetup.jsx`'s Quick form: replace "(customizable
   once Amendment 9 ships)" with something accurate, e.g. "customize on the next
   screen" -- since after point 1, that's literally true.
3. **No backend change** -- `addProjectSport`'s call already exists and is unaffected;
   this is a pure frontend routing + copy fix.
4. **The Quick Start handbook's own Setup step already half-describes this correctly**
   (`Help.jsx`: *"court size is set on the next screen, Sport Selection, not here"*) --
   that line was arguably aspirational/inaccurate against today's actual Quick-mode
   routing; after this ships it becomes true, no handbook change needed.

**Acceptance criteria:** completing Quick setup lands on Sport Selection, not Scope,
showing the sport just picked with its standard build size pre-filled and a working
"Customize size" control, identical to what Detailed mode already provides; the stale
"(customizable once Amendment 9 ships)" text no longer appears; Scope is still reachable
immediately after (same "Continue" action Sport Selection already offers for Detailed
mode); nothing about client/sport/city/base-scope entry changes.

### Open decisions — need Director input before implementation

1. **Confirm this is the intended fix** (route Quick mode through Sport Selection, not
   add a literal 5th text field to the Quick form) -- proposed, since it reuses the
   exact validated dimension-entry path Detailed mode already has, rather than building
   a second, divergent one.
2. **Replacement copy for the stale line** -- proposed: "customize on the next screen."
   Confirm or supply alternate wording.

---

## Approval

Amendment 2 continuation (Quick mode routes through Sport Selection instead of
skipping it; stale copy fixed): ☑ Approved — "approve as proposed, both decisions"
(19 September 2026)

Decision 1 (route through Sport Selection, not a literal 5th field): ☑ Resolved as
proposed.
Decision 2 (replacement copy wording, "customize on the next screen"): ☑ Resolved as
proposed.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 19 September 2026
