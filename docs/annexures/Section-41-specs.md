# Section 41 — Spec Doc

## Amendment No. 35 — Site Survey Has No Forward Navigation, a Genuine Dead End for Sales

**Registered scope:** see `docs/annexures/Annexure-2.md`, Amendment No. 35 (registered 22
September 2026, from `docs/planning/2026-09-Sales-Experience-and-Dashboard-Plan.md`
Section A.4).

### Current state

`frontend/src/App.jsx:478-495`:

```jsx
{!TOP_LEVEL_SCREENS.includes(screen) && activeProject && screen === "scope" && (
  <ScopeChecklist
    token={accessToken}
    project={activeProject}
    onBack={() => setScreen("scope")}
    onNext={() => setScreen("tender")}
    onDocuments={() => setScreen("documents")}
    onSiteSurvey={() => setScreen("site_survey")}
  />
)}
{!TOP_LEVEL_SCREENS.includes(screen) && activeProject && screen === "site_survey" && (
  <SiteSurvey
    token={accessToken}
    project={activeProject}
    role={user.role}
    onBack={() => setScreen("scope")}
  />
)}
```

`ScopeChecklist` is a routing hub with three forward destinations (`tender`,
`documents`, `site_survey`) plus back. `SiteSurvey` is reachable from it but has
only `onBack` wired -- no `onNext` prop exists at all, and
`frontend/src/SiteSurvey.jsx:190-194` renders only a "← Back" button, confirmed
by direct read. A Sales rep who opens Site Survey from Scope Checklist, fills it
in, and taps "Mark Completed" (`frontend/src/SiteSurvey.jsx:144`,
`disabled={survey.photo_count < 4}`) has no button anywhere on the screen to move
forward -- the only way out is Back to Scope Checklist, then choosing a different
menu item from there.

Ruled out during the same investigation (no fix needed): the survey's fields are
not all mandatory. Only `photo_count >= 4` gates "Mark Completed"
(`backend/app/api/site_surveys.py:24`, `MIN_PHOTOS_TO_COMPLETE = 4`); every other
field on `SiteSurvey` (`backend/app/models/site_survey.py:53-77`) is already
nullable, matching `SiteSurveyUpdate`'s all-optional schema
(`backend/app/api/site_surveys.py:35-59`).

### Proposed spec

1. Add an `onNext` prop to `SiteSurvey`, passed from `App.jsx` as `() =>
   setScreen("documents")` -- the same destination `ScopeChecklist`'s own
   `onDocuments` already routes to, so both paths converge on the Cost
   Sheet/Estimate/Quotation stage.
2. Add a "Next →" button in `SiteSurvey.jsx`, placed beside the existing "← Back"
   button (`SiteSurvey.jsx:190-194`).
3. The Next button is **always enabled**, not gated on "Mark Completed" or
   `photo_count >= 4` -- matching this app's existing navigation convention
   (`ScopeChecklist`'s own nav links are always-enabled regardless of checklist
   completion, per this project's earlier UX audit). Site Survey is a
   supplementary record, not a hard gate on the document workflow; nothing
   downstream (Cost Sheet, Estimate, Quotation) reads or blocks on Site Survey
   completion today, and this amendment does not change that.
4. No backend change. This is frontend-only wiring.

**Acceptance criteria:**
- From Site Survey, a "Next →" button is visible and takes the user to the
  Documents screen (Cost Sheet/Estimate/Quotation stage) for the same project.
- The button is clickable regardless of how many photos have been uploaded or
  whether "Mark Completed" has been pressed.
- "← Back" continues to work exactly as today (returns to Scope Checklist).
- No change to `SiteSurveyUpdate`, `complete_site_survey`, or any backend
  endpoint -- this amendment is UI navigation only.

### Open decisions

1. **Next button destination: Documents (proposed default) vs. back to Scope
   Checklist's own menu.** Documents is proposed because it's the same
   destination `ScopeChecklist`'s `onDocuments` already uses, and is very
   likely where a Sales rep actually wants to go after a site visit (begin
   Cost Sheet /Estimate/Quotation next). Proposed default: **Documents.**
2. **Should the Next button be visually emphasized (e.g. gold, matching this
   app's primary-action styling) once "Mark Completed" has been pressed, to
   nudge the rep toward finishing the survey first without blocking early
   navigation?** Proposed default: **no special emphasis** -- keep it a plain
   secondary-style button identical in weight to "← Back," consistent with
   this amendment's minimal-scope, navigation-only intent. A visual nudge can
   be added later if real usage shows reps skipping the survey.

## Approval

☐ Approved — pending Director decision.

---
Prepared by: R. Patni (with AI development assistance) | Date: 22 September 2026
