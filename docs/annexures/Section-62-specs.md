# Section 62 — Amendment No. 59 Spec

## Amendment No. 59 — The Admin Role, and Who Can Do What

### Registered scope
The Director's instruction (26 September 2026): **"admin - director or PM - User admin has all right; director / PM
has user rights and approval rights; user has creation rights -- because director has no technical ability or no
time for admin work, so admin and director are two separate things."** In short: the administration of the system
(people, access, technical settings) moves to a new **Admin**; the **Director and PM** keep the business decisions
and approvals; the **other users** keep their day-to-day creation rights. Evidence is in
`docs/annexures/Annexure-2.md`, Amendment No. 59.

Today the Director is the only role that does the admin jobs: **users** (list, create, change role, deactivate,
reset a password), the **audit log**, the **Role & Permissions** screen, company details, message templates and every
master-data and settings screen. That is 43 of the 247 gated routes. The Director does not want that work.

### Governing principles
- **Administration is not approval.** Admin can run the system; Admin does not approve, release, waive or price. An
  account that can both administer and approve would let one person check their own work, so it is not built that way.
- **Business decisions that set a price stay with the Director.** Margin floors, contingencies, GST, the rate sheet and
  catalogue rates, validity periods and the quotation terms decide what a client is quoted; they are the Director's.
- **Cost and margin stay hidden from anyone who could not already see them (K.3).** Admin sees no cost, margin or
  quotation content.
- **One person cannot grant power they do not hold.** Each role may create only the roles named below.
- **Everything an Admin does is on the record**, and the Director can see it.
- **Nothing that works today stops working for the roles that use it today.**

### Proposed spec

**Part A -- Backend (one migration)**
1. **A seventh role, `admin`,** added to the role list (a database migration that adds the value). No existing account
   changes role. At least one Admin must always exist (guardrail 9), so the first Admin is created by the Director
   through a one-time step (item 10).
2. **Who may do what with users:**

   | Action | Admin | Director | PM | Others |
   | --- | --- | --- | --- | --- |
   | List users | yes | yes | yes | no |
   | Create a user | any role | any role **except** Admin | Sales, Procurement, Site Engineer, CA/Tax only | no |
   | Reset a password, deactivate / reactivate, change a role | any user | any **non-Admin** user | no | no |

   A PM can never create a Director, a PM or an Admin; a Director can never create or touch an Admin; requests outside
   these limits are refused 403 with a plain reason.
3. **Admin's other rights (the technical side):** view the **Audit Log** and export it; view the **Role &
   Permissions** screen; edit **company identity** (legal name, GSTIN, PAN, registered-office city, signatory name
   and designation), the **logo**, **message templates** and **field settings** (which fields are required).
4. **Director keeps, and Admin does not get:** every setting that prices or words a quotation -- the 27 other master
   settings (margin gap points, contingencies, GST rate, estimate and quotation validity, schedules, site
   establishment, rate-blind mode, approval SLA, the quotation terms and warranty table); ▲ **the four bank-account
   settings** (account name, number, IFSC, bank name -- a changed account on client-facing quotations is a classic
   fraud route, so a change stays with the Director); and every catalogue that carries a rate or multiplier (sports,
   hubs and regional multipliers, netting grades, vehicle classes, scope items, accessory and cross-sell catalogues,
   lighting standards, flooring guides, package contents, construction sequences, sport margin policies).
   Approvals, releases, waivers, Mark Won/Lost, the calibration override and the report release stay with the Director
   and PM exactly as now.
5. **Settings are gated by key, not just by route:** `POST /settings` admits an Admin only for the six company-identity
   keys; the other 31 keys, bulk update and the spreadsheet import stay Director-only. Refused with a plain reason.
6. ▲ **The Audit Log for an Admin hides values that are cost or margin** (old and new value for pricing-policy
   settings, margin policies, cost-sheet lines, rate items and catalogue rates): the Admin sees who changed what and
   when, not the numbers -- the same K.3 principle as everywhere else. The Director sees everything, as now.
7. **What Admin does not see or do:** clients, leads, projects, cost sheets, estimates, quotations, work orders,
   payments, reports, vendors, rates, pricing calculator -- none of the business screens and none of their routes
   (they answer 403). The all-routes test and the role table are extended to the seventh role.
8. **Every Admin action is audited** (existing audit log, no migration), and **the Director's dashboard "Recent
   activity" shows Admin actions** so nothing an Admin does is hidden from them.
9. **Guardrails, server-side:** there is always at least one active Admin and at least one active Director; neither
   the last Admin nor the last Director can be deactivated or demoted; nobody can deactivate or demote themselves.
10. **The first Admin** is created by the Director once (Team & Access, or the seed script for a fresh install) and
    from then on Admins create Admins. Nothing is created automatically.
11. **Tests**, including: every gated route is checked as all seven roles against the role table (the
    `role_route_check.py` script and the all-routes test pass); a PM's create-user limits (403 for Director, PM,
    Admin); a Director cannot create or touch an Admin; the last-Admin and last-Director guardrails; Admin refused on
    every business route; the settings key gate (company name yes, GST rate no, bank account no); audit-log masking
    for Admin and none for Director; each guard removed once to see a test fail.

**Part B -- Screens**
12. **Sidebar and navigation** (the single role table `navAccess.js`): Admin sees only Team & Access (People and Role &
    Permissions), Audit Log, Master Settings (company details, message templates, field settings), and a small
    Overview of system facts (people, recent activity). Director and PM keep their sidebars; **a PM additionally sees
    the People tab with the create form and the list, and nothing else on Team & Access.**
13. **Team & Access -> People:** the role picker offers each person only the roles they may create; the buttons a role
    may not use are not shown (the server refuses them anyway).
14. **Master Settings:** an Admin sees the company-identity fields, logo, templates and field settings editable and the
    rest read-only or absent; a Director sees no change.
15. **Handbook:** Team & Access, Master Settings, Audit Log and a new "Who does what" entry -- checked by name and by
    wording -- plus the Role & Permissions screen showing seven roles.
16. **Phone layout** at 375, 414 and 768px and a real-Chrome pass per role (all seven): every reachable screen opens
    with zero refused calls; screens a role cannot reach are not offered.

**Sequencing (one Amendment number, two ordered PRs):** PR 1 = Part A (backend, migration, tests); PR 2 = Part B
(frontend). Part A is safe under the old frontend (no existing role or account changes). Each is deployed and
verified from outside before the close-out.

### Explicitly out of scope
- Mobile-number sign-in and mobile-or-email user creation (Amendment 61).
- Limiting Sales to their own records and the personal dashboard (Amendment 60).
- Two-factor sign-in, a "manager" role separate from PM, per-user custom permissions, approval workflows for Admin
  actions.
- Any pricing rule, margin, GST or K.3 gate.

### Acceptance criteria
- An Admin can create, reset, deactivate and change the role of any non-Admin user and create other Admins, edit the
  six company-identity fields, the logo, templates and field settings, and read (but not see the numbers in) the audit
  log; every business route answers them 403 and no business screen is offered.
- A Director can do the user work for non-Admin users, keeps every pricing setting and approval, cannot create or
  change an Admin, and sees Admin actions in Recent activity.
- A PM can create Sales, Procurement, Site Engineer and CA/Tax users and nothing else about users; asking for a
  Director, PM or Admin is refused 403.
- `POST /settings` changing `company_legal_name` works for an Admin; changing `gst_rate_percent` or a bank-account
  setting is refused 403 for an Admin and works for a Director.
- The last Admin and last Director cannot be deactivated or demoted; nobody can deactivate themselves.
- The role table shows seven roles and matches the server on every route (0 mismatches); existing accounts and
  sessions are unaffected; the existing suite passes.

### Open decisions (proposed defaults)
1. **A separate Admin role, distinct from Director.** Proposed: **yes.**
2. **Admin has all administration rights but no business approvals**, and sees no cost or margin. Proposed: **yes.**
3. **A Director may create any role except Admin; only an Admin creates an Admin.** Proposed: **yes.**
4. **A PM may create Sales, Procurement, Site Engineer and CA/Tax users only**, and list users; nothing more.
   Proposed: **yes.**
5. **The Director decides pricing policy** (margin floors, contingencies, GST, validity, rates, catalogues, terms);
   Admin edits only technical settings and company identity. Proposed: **yes.**
6. ▲ **Bank-account settings stay with the Director.** Proposed: **yes.** (Alternative: Admin may edit them, every
   change shown to the Director.)
7. ▲ **Admin sees the audit log with cost and margin values hidden.** Proposed: **yes.**
8. **At least one active Admin and one active Director at all times.** Proposed: **yes.**
9. **Two ordered PRs** (backend, then screens). Proposed: **yes.**

### Approval
☑ Approved — "approve as proposed, all decisions" (26 September 2026). The proposals approved in the conversation
were: the separate Admin role; Admin has all administration but no approvals and no cost or margin; the Director
decides pricing policy; a Director or PM creates users within the limits above; the guardrails; the split into
separate amendments in this order. The items marked ▲ were added while drafting and are flagged for the Director's
attention; everything else follows the approved proposals.
☐ Approved with changes (noted above)
☐ Not approved

**Prepared by:** R. Patni (with AI development assistance)
**Date:** 26 September 2026
