# Section 56 — Amendment No. 52 Spec

## Amendment No. 52 — Placement of the "More" Group (Vendor, Tools, Reports, Admin, Education, Help)

### Registered scope
The Director's instruction (25 September 2026): register and spec the More-group placement decisions
that Amendment 48's audit left open and Amendment 51 deliberately did not touch. Evidence is in
`docs/annexures/Annexure-2.md`, Amendment No. 52. In short: eight real headers are done, but the
screens that do not have one -- Vendor, Tools, Reports, Admin, Education, and Help -- still sit in a
temporary "More" accordion (Amendment 36) that no one ever signed off: **Help is filed under
"Admin"**, the menu people of every role have no reason to open; four of the five groups hold one or
two items; a Sales rep must open More, open a group and pick an item to reach a calculator or Reports;
**"All Quotations" in Admin is now a duplicate** of the Quotations header (Amendment 49 made that
header open the same screen for the same Director); and Reports does not say that Sales can generate
only one of its three report types.

### Governing principles
- **Nothing is removed, only moved.** Every screen reachable today stays reachable, by the same roles
  (Amendment 51's `navAccess.js` table is unchanged), except one exact duplicate (decision 2).
- **Where you look for it is where it is.** Help and training are for everyone, so they are not
  under an admin label; things a role cannot use are not shown to it (Amendment 46/51's rule).
- **No new primary headers.** The eight sidebar headers stay as they are; this amendment only
  reorganises what sits below them.
- **Wording that names a location is part of the change.** Amendment 51 shipped with the Help
  handbook still naming a screen's old home; this spec lists that text as work, not an afterthought.

### Proposed spec

**Part A -- Frontend only (no backend change, no role-gate change)**
1. **Help and Education become two links at the bottom of the sidebar, shown to every role,** above
   the user/log-out block and outside "More": one click from anywhere, on phones too (the same menu
   overlay). They open the existing Help and Education screens unchanged. Education stops being a
   one-item group; Help leaves Admin.
2. **"All Quotations" is removed from Admin.** It opens the identical screen with the identical
   (empty) preset as the "Quotations" header, which every role that can see quotations already has.
3. **"More" is reorganised into two always-open sections instead of five accordion groups:**

   | Section | Items (in this order) |
   |---|---|
   | **Tools & reports** | Reports, Rate Sheet, Price Calculator, Price Requests, Vendor Master, One Simple Calculator |
   | **Admin** | Sports & Scope, Master Settings, Cross-Sell Add-ons, Audit Log |

   Vendor Master joins the tools (procurement, PM and Director use it with Rate Sheet and Price
   Requests); Reports becomes a plain item rather than a one-item group. Each item is shown to
   exactly the roles it is today (`navAccess.js`, unchanged); a section with nothing left to show is
   not shown. "More" stays the label. Items are listed directly when More is open -- no second click
   to open a group.
4. **What each role sees under More** (checked against the API, unchanged from Amendment 51):

   | Role | Tools & reports | Admin |
   |---|---|---|
   | director | Reports, Rate Sheet, Price Calculator, Price Requests, Vendor Master, One Simple Calculator | Sports & Scope, Master Settings, Cross-Sell Add-ons, Audit Log |
   | pm | the same six | Sports & Scope, Master Settings |
   | procurement | Rate Sheet, Price Requests, Vendor Master, One Simple Calculator | *(not shown)* |
   | site_engineer | Rate Sheet, One Simple Calculator | *(not shown)* |
   | ca_tax | One Simple Calculator | *(not shown)* |
   | sales | Reports, One Simple Calculator | *(not shown)* |

5. **Reports tells Sales what it can generate.** For a role that cannot generate every type, one line
   under the Type selector: "You can generate the Quotation Pipeline report. Margin Performance and
   Override Summary are for PM and Director." (Only the Pipeline type is available to Sales; the note
   is for Sales, and for PM the equivalent line names Override Summary as Director-only.) No report
   type is opened to any new role.
6. **The Help handbook and every other on-screen line that names a location is brought in line,**
   found by searching the frontend for the old names (Admin, More, Master Settings, All Quotations,
   Vendor, Tools, Education) -- including the handbook's "All Quotations" entry, which still describes
   a Director-only screen although Amendment 49 opened the Quotations list to Sales and PM.
7. **Phone layout:** the new footer links and the More sections fit at 375 and 414px (plus 768px and
   a desktop pass), verified as in Amendments 47, 49 and 51.

**Sequencing:** one PR (frontend only), then a frontend rebuild and copy; verified from what production
serves, then a docs-only close-out.

### Explicitly out of scope
- New primary headers (for example a "Reports" or "Vendors" header), renaming any screen, or
  changing the eight headers' order.
- Any backend or role-gate change, or opening a screen or report type to a role that cannot use it now.
- Moving Audit Log, Sports & Scope or Cross-Sell Add-ons into Team & Access (decision 6).
- Global quick search, Section C quotation content, HTTPS, and Help content beyond the lines that
  name a location.

### Acceptance criteria
- As each of the six roles, Help and Education are one click away from the sidebar with **no menu
  opened first** (on desktop and in the phone overlay).
- Opening More as each role shows exactly the table in item 4, in that order, with no empty section
  and no second click to reach an item; "All Quotations" no longer appears; nothing else that was
  reachable before is missing.
- Opening every visible item as each role causes **zero refused (4xx) API calls** and no
  permission-error text (the Amendment 51 audit, re-run).
- Sales sees the Reports note; PM sees the shorter line; the Director sees no note.
- A search of the frontend finds no on-screen text naming Help under Admin, Education under More or
  All Quotations under Admin; the handbook's "All Quotations" entry matches what the screen does.
- At 375px and 414px the sidebar overlay needs no more width than the phone has and the footer links
  are reachable by scrolling.

### Open decisions (proposed defaults)
1. **Help and Education move to the sidebar footer for every role.** Proposed: **yes.** (Alternative:
   one "Help & training" link, merging the two screens' entry points.)
2. **Remove "All Quotations" from Admin** (exact duplicate of the Quotations header). Proposed: **yes.**
3. **Merge Vendor into Tools** as "Vendor Master" beside Rate Sheet and Price Requests. Proposed:
   **yes.** (Alternative: keep Vendor as its own section, or make it a header for procurement/PM/Director.)
4. **Reports stays under More as a plain item, not a ninth header;** the Overview's existing Reports
   link stays. Proposed: **yes.** (Alternative: a "Reports" sidebar header for Sales/PM/Director.)
5. **Two always-open sections instead of accordion groups.** Proposed: **yes** -- fewer taps,
   especially on a phone. (Alternative: keep the accordion.)
6. **Audit Log, Sports & Scope and Cross-Sell Add-ons stay in Admin;** Team & Access stays people and
   roles only. Proposed: **yes.** (Alternative: move Audit Log under Team & Access.)
7. **Keep the "More" label.** Proposed: **yes.** (Alternative: "Tools & Admin".)
8. **Add the Reports note for Sales/PM** (Amendment 48 mismatch #4). Proposed: **yes.**
9. **Review and correct the handbook lines that name a location, including the stale "All Quotations"
   entry,** as part of this amendment. Proposed: **yes.**
10. **One frontend PR** rather than one per part (nothing here depends on the backend). Proposed: **yes.**

### Approval
☑ Approved — "approve as proposed, all decisions" (25 September 2026)
☐ Approved with changes (noted above)
☐ Not approved

**Prepared by:** R. Patni (with AI development assistance)
**Date:** 25 September 2026
