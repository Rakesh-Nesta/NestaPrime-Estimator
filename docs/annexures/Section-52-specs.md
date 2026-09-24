# Section 52 — Amendment No. 47 Spec

## Amendment No. 47 — Complete the First Three Headers (Lead/Client Details, Leads & Clients Tabs, Phone Layout)

### Registered scope
The Director's decision (24 September 2026): finish Overview, Leads & Clients and Opportunities
before starting the next header, by closing three open items from Amendment 46's audit:
1. editing lead details, 2. Lead/Client tabs on Leads & Clients, 3. the phone layout.
Evidence and root causes are in `docs/annexures/Annexure-2.md`, Amendment No. 47.

### Proposed spec

**Part A -- Editing details (backend + UI)**
1. `PATCH /opportunities/{id}/details` -- `lead_name` (required, must not be blank after
   trimming), `lead_phone`, `lead_email`. Roles: `sales`/`pm`/`director` (same as every other
   Opportunity write). Allowed at **any stage** including Won/Lost -- it corrects a typo, it is
   not a workflow step. Not audit-logged (same convention as follow-up/notes).
2. `PATCH /clients/{id}/details` -- `name` (required, non-blank), `contact_name`, `phone`,
   `email`. Roles: `sales`/`pm`/`director` (the `create_client` gate; **not** the Director-only
   flags gate). **Client type is deliberately not editable here** -- it drives the default package
   and payment terms, so changing it is a different, riskier action. Billing/GST fields are out
   of scope. A change to `name` **is audit-logged** (a client name prints on issued Quotations, so
   a rename is a fact worth a trail); contact/phone/email changes are not.
3. UI: an "Edit details" toggle on each lead and client card opens inline inputs with
   Save/Cancel; on the Opportunities screen too, not only on Leads & Clients.

**Part B -- Leads & Clients restructure (frontend, reuses existing endpoints)**
4. Tabs **All / Leads / Clients**, each with a count. **Leads** = lead-only Opportunities
   (`GET /opportunities?relationship=lead`) that are not Lost. **Clients** = today's client
   cards. **All** = leads first (soonest follow-up first) then clients (A-Z), each row carrying a
   "Lead" or "Client" relationship badge (the reference's per-row badge).
5. Lead rows show name, phone/email, stage pill, follow-up date (red if overdue), notes, with
   actions: Edit details, "Open in Opportunities ->" (stage changes and linking stay on the
   Opportunities screen -- this page is a directory, that one is the pipeline). A Won lead with no
   client shows the existing "link a client to start a Project" hint.
6. A search box (name/phone/email, client-side) above the list.
7. "Add Enquiry" and "Add a client" become two buttons at the top that expand their existing
   forms in place and collapse after a successful save, so the list is visible without scrolling
   past two forms. Form fields and behaviour are unchanged.
8. Restyled to match the newer screens (`max-w-[1000px]`, the same breadcrumb/title/Back header) --
   visual only. Retitle stays "Leads & Clients".

**Part C -- Phone layout (frontend)**
9. **Root cause:** `App.jsx:150` becomes `flex flex-col sm:flex-row` so the Sidebar's mobile top
   bar sits *above* the content on phones instead of becoming a left column. Desktop unchanged.
10. Make the four screens fit a phone: header rows wrap (Overview title + Reports/New project
    buttons, every "<- Back"); inline control clusters `flex-wrap`; fixed widths (`w-32`,
    `min-w-[8rem]`) become responsive (full-width on phones); cards stack their controls;
    selects `max-w-full`. Desktop appearance unchanged.
11. **Verification method (recorded in the register):** the real-Chrome mobile-emulation audit
    used to find this, re-run after the fix at **375px and 414px**, plus a **768px** tablet and a
    desktop regression pass, as `sales` -- acceptance is "the width each screen needs is <= the
    viewport width" on all four screens, the hamburger opens and every nav item works, zero JS
    errors.

**Sequencing (one Amendment number, three ordered PRs, shell-first as before):**
PR 1 = Part C (phone layout; frontend-only, fixes the most widely felt problem first);
PR 2 = Part A (detail editing; backend + UI + tests); PR 3 = Part B (Leads & Clients
restructure, which builds on Part A's edit action). Each is deployed and live-verified before the
next header starts.

### Explicitly out of scope
- Editing Client type, billing address, GST/PAN, credit limit, or payment terms.
- Deleting or merging leads/clients; duplicate detection.
- Changing the Opportunities screen's pipeline behaviour (stages, follow-up rules) -- untouched.
- A native app or PWA; this is responsive web only.

### Acceptance criteria
- A typo in a lead's or client's name/phone/email can be corrected in place; a blank name is
  refused; only `sales`/`pm`/`director` can; a client rename appears in the audit log.
- Leads & Clients has All/Leads/Clients tabs with counts and a Lead/Client badge on every row;
  leads appear there; search filters by name/phone/email; the list is visible immediately
  without scrolling past the add forms.
- On a 375px and a 414px phone, Overview, Leads & Clients, Opportunities and Follow-ups need no
  more width than the screen has, the hamburger menu is reachable and works, nothing is cut off.
- Desktop and tablet layouts are visually unchanged apart from the Leads & Clients restyle.
- No existing test regresses; new tests cover both details endpoints (validation, role gate,
  any-stage edit, audit entry on client rename only).

### Open decisions (proposed defaults)
1. **Also let clients' details be edited (item 2)**, not only leads' -- you raised leads, but
   clients have the identical gap. Proposed: **yes** (drop item 2 if you want leads only).
2. **Audit-log client renames only** (not contact/phone/email). Proposed: **yes**.
3. **Leads tab hides Lost leads** (they stay visible on Opportunities). Proposed: **yes**.
4. **Search box, collapsible add forms and the restyle (items 6-8)** are included in Part B.
   Proposed: **yes** -- they are what makes the tabs usable with 100+ records; each can be
   dropped without affecting the rest.
5. **Lead editing lives on both screens** (Leads & Clients and Opportunities). Proposed: **yes**.
6. **Phone targets:** 375px and 414px, with 768px as a sanity check. Proposed: **yes**.

### Approval
☑ Approved as proposed, all decisions
☐ Approved with changes (noted above)
☐ Not approved

**Prepared by:** R. Patni (with AI development assistance)
**Date:** 24 September 2026
