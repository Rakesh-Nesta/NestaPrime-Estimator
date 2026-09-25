# Section 60 — Amendment No. 57 Spec

## Amendment No. 57 — Multi-Sport Quotation

### Registered scope
The Director's instruction (25 September 2026): register and spec being able to put **more than one sport in
one Quotation** -- a question the Director says has come up many times without being built. Evidence is in
`docs/annexures/Annexure-2.md`, Amendment No. 57. In short: the backend already prices and prints a
multi-sport Quotation (a test proves it), but the Documents screen can only ever build a one-sport
Estimate, so a multi-sport Quotation cannot be made from the app -- and behind that gap is a hazard the
screen has so far hidden: nothing stops one Quotation from including two packages of the *same* sport.

### Governing principles
- **One Quotation, one lump-sum total, several sports.** A multi-sport Quotation is priced exactly as the
  backend already prices it (K.1/K.2: summed cost, cost-weighted floor and target, one GST, one
  discount); this amendment adds no new pricing rule.
- **A sport appears once.** A Quotation carries at most one package per sport; alternatives (Budget,
  Standard, Premium) live on the Estimate for the client to compare, and exactly one is chosen when the
  Quotation is made.
- **See what will be quoted.** The person creating a Quotation is shown which sports and packages it will
  include, instead of the screen silently including "whatever is approved".
- **Cost stays with PM and Director (K.3).** Nothing here shows a cost or margin to a role that could not
  already see it.

### Proposed spec

**Part A -- Backend**
1. **`POST /estimates/{id}/options` (PM/Director)** adds one option (sport, package, cost) to an Estimate
   that is still **Draft**, with the same checks as creating an Estimate (the sport is on the project, the
   cost is above zero, the client is not blacklisted) and the same per-option pricing. Any other status
   answers 400 -- editing a Sent Estimate stays "create a revision" (M.2 rule 4).
2. **`DELETE /estimates/{id}/options/{option_id}` (PM/Director)** removes an option from a Draft Estimate;
   the last option cannot be removed, and an option that already has a client decision cannot be removed.
3. **Duplicates:** creating an Estimate, or adding an option, with the *same sport and the same package*
   twice is refused (400). The same sport with a *different* package is allowed -- those are the
   alternatives the client compares.
4. **A Quotation includes at most one option per sport.** `POST /projects/{id}/quotations` (and the
   revise path) refuses, with a message naming the sport and the packages, when two included options
   are for the same sport ("Choose one package for Badminton: Standard and Premium are both approved"),
   and refuses a repeated option id. Nothing else about pricing changes.
5. **Tests:** add-option on Draft prices the option like a created one and appears on the Estimate;
   refused on Sent, on a wrong-project sport and for Sales/other roles; remove works on Draft, refuses the
   last option and a decided option; same sport+package refused, same sport different package allowed;
   a two-sport Quotation from an Estimate with an added option totals the summed cost with the
   cost-weighted floor (as `test_margin_floor_by_sport` already asserts for created options); two approved
   packages of one sport refused with the message; a repeated option id refused; existing tests unchanged.

**Part B -- Frontend (Documents screen)**
6. **Create Estimate takes several sports at once.** The single sport/package/cost row becomes a short
   list with **"+ Add another sport"** and a Remove on each extra row; the sports on the project not yet
   used are offered first; a running **"Options total Rs X"** sits beneath (PM/Director only, as now).
   One "Create Estimate" click creates one Estimate holding every row.
7. **A Draft Estimate can be extended:** **"+ Add sport option"** (the same three fields) and a Remove on
   an option that has no client decision yet, calling item 1 and item 2. A Sent Estimate shows neither.
8. **A non-blocking reconciliation note** when the options' total differs from the active Cost Sheet's
   total ("Options total Rs X; Cost Sheet Rs Y") -- information only, never a block, because a Quotation may
   legitimately cover a subset of the sports.
9. **Create Quotation shows what it will include** -- a short list, "Badminton -- Standard, Basketball --
   Premium" -- and, where a sport has more than one approved package, a choice for that sport (Create stays
   off until every such sport has exactly one), then sends exactly the chosen options.
10. **The PDFs need no change** (a row per sport on the Estimate and the Quotation, a Scope of work per sport
    from Amendment 54); the acceptance checks a real two-sport and three-sport PDF.
11. **Help handbook:** the Documents entry and the Quick start describe building a multi-sport Estimate and
    Quotation -- checked by name **and** by wording about what a Quotation contains.
12. **Phone layout:** the option rows and the summary fit at 375 and 414px (plus 768px and a desktop pass).

**Sequencing (one Amendment number, two ordered PRs):** PR 1 = Part A (backend + tests); PR 2 = Part B
(frontend, depends on PR 1). Each is deployed and live-verified before the close-out.

### Explicitly out of scope
- **Fast-track** (Resurfacing/Repair under the small-job limit) stays single-sport, refused for multi-sport
  projects as today.
- **Adding or dropping a sport on a Quotation already sent** -- still a new Quotation (a Sent document is
  read-only; M.2 rule 4).
- **A discount per sport, or a different margin per sport on one Quotation** -- one discount on the total and
  the K.2 cost-weighted floor, as today.
- Changing how a sport is added to a project (the sport selection step), per-sport cost entry on the Cost
  Sheet, or the Work Order/payment flow.
- Any pricing rule, margin, GST or role gate.

### Acceptance criteria
- As PM (or Director), on a project with three sports and a Verified Cost Sheet: one "Create Estimate" click
  with two sports creates one Estimate with two options; "+ Add sport option" adds the third to the Draft;
  Remove takes one off; a Sent Estimate offers neither.
- With the client's approval recorded on each option, "Create Quotation" lists the sports and packages it will
  include; the resulting Quotation has one line per sport, the summed cost, and the K.2 cost-weighted floor
  and target; its PDF shows one Particulars row per sport and a Scope of work for each.
- Approving both Standard and Premium of one sport does not double-count: the screen asks for one, and the
  API refuses both with a message naming the sport.
- Sales cannot add or remove options (403) and sees no cost; a Sent Estimate and a Sent Quotation cannot be
  changed by these calls.
- Opening every affected screen as each of the six roles causes zero refused (4xx) calls.
- At 375px and 414px the option rows and the summary need no more width than the phone has (the Estimate
  rows on Documents overflowed a 375px phone before this amendment; the new rows must not, and where the
  existing rows still do, that is recorded, not hidden).
- The existing backend suite passes.

### Open decisions (proposed defaults)
1. **Build multi-sport into the Estimate:** several sports in Create Estimate, and add/remove on a Draft.
   Proposed: **yes.**
2. **Two new PM/Director endpoints** to add and remove options on a Draft Estimate. Proposed: **yes.**
3. **A Quotation includes at most one package per sport,** enforced by the API and in the screen.
   Proposed: **yes.** (This fixes a hazard that exists today for any Estimate holding several packages of one
   sport.)
4. **Create Quotation shows a summary and a per-sport choice** instead of silently including every approved
   option. Proposed: **yes.**
5. **A non-blocking note when the options' total differs from the Cost Sheet's total.** Proposed: **yes.**
6. **The PDF keeps printing each sport's apportioned share** in the Particulars table, as it does today for
   any quotation, with one discount and one total. Proposed: **keep.** (Alternative: for a multi-sport
   Quotation show only the single lump-sum total, in line with the plan's "lump sum, no itemised prices"
   constraint -- a change to the existing PDF.)
7. **Fast-track stays single-sport.** Proposed: **yes.**
8. **A sport cannot be added to a Sent Quotation** -- create a new one. Proposed: **yes.**
9. **Roles unchanged:** PM/Director build and edit Estimates; Sales creates Quotations but never sees cost.
   Proposed: **yes.**
10. **Two ordered PRs** (backend, then frontend). Proposed: **yes.**

### Approval
☑ Approved — "approve as proposed, all decisions" (25 September 2026)
☐ Approved with changes (noted above)
☐ Not approved

**Prepared by:** R. Patni (with AI development assistance)
**Date:** 25 September 2026
