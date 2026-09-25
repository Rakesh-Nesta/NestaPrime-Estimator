# Section 55 — Amendment No. 51 Spec

## Amendment No. 51 — Team & Access and Role-Accurate Navigation

### Registered scope
The Director's instruction (25 September 2026): register and spec Team & Access, from Amendment 48's
audit. Evidence is in `docs/annexures/Annexure-2.md`, Amendment No. 51. In short: "Team & Access"
opens the Master Settings screen instead of team and access; that item, and most of the "More"
menu, is shown to roles the API refuses (refused calls, permission-error text, and a false
"Current settings (0)"); PM is shown write forms every one of whose endpoints refuses it; and the
Director-only Role & Permissions tab is a hand-kept mirror that has drifted from the code.

### Governing principles
- **Show a link only to a role that can use it.** Amendment 46's rule, applied to every remaining
  item. The API stays the authority; the navigation follows it, never the other way round.
- **A permissions screen must not be able to lie.** It is generated from the same role checks the
  API enforces, so a new or changed gate shows up without anyone remembering to edit a file.
- **No backend role gate changes.** This amendment aligns the interface with the existing gates; it
  does not widen or narrow anyone's access.

### Proposed spec

**Part A -- Backend (small)**
1. **`require_roles` tags its dependency with the role list it enforces** (`dependency.allowed_roles`),
   one added attribute; behaviour is unchanged.
2. **`GET /role-permissions`, Director-only,** walks the live route table and returns every route that
   carries such a gate, grouped by area (the route's first tag), then by identical role set, each item
   being method, path and a readable label (the route function's name, humanised, with an optional
   curated override map for the awkward ones). Routes with no role gate (login, `/auth/me`, password
   change, health) are listed separately as "any signed-in user" / "no sign-in".
3. **Tests:** Director-only (every other role 403); every gated route appears exactly once; spot checks
   against known gates (e.g. `GET /payments` includes `ca_tax`; `POST /settings` is `director` only;
   `POST /users` is `director` only; `GET /quotations` is `sales`/`pm`/`director`); a route added in
   the test with a new gate shows up without any other edit.

**Part B -- Frontend**
4. **"Team & Access" becomes a real screen, shown to the Director only** (the only role that can call
   `/users`): two tabs, **People** (the existing user management, unchanged) and **Roles & permissions**
   (see 8), opening on People. It is no longer wired to Master Settings, and its App route refuses any
   other role.
5. **Master Settings has one entry point, "Admin > Master Settings",** visible to `pm` and `director`
   only (the roles `GET /settings` admits).
6. **PM sees Master Settings read-only:** every write control (Add a new setting, Bulk update, logo,
   company details, templates, field settings, Excel import, edit/remove buttons) is not rendered for
   PM, and the blurb says so. The Director's screen is unchanged.
7. **Every "More" item is shown only to the roles its screen actually works for** -- one table in one
   frontend file, each row noting the endpoints it depends on:

   | Item | Shown to |
   |---|---|
   | Vendor Master | pm, director, procurement (unchanged) |
   | Price Calculator | pm, director |
   | Rate Sheet | pm, director, procurement, site_engineer |
   | One Simple Calculator | everyone (unchanged) |
   | Price Requests | pm, director, procurement |
   | All Types of Reports | sales, pm, director |
   | Sports & Scope | pm, director |
   | Master Settings | pm, director |
   | Cross-Sell Add-ons, Audit Log, All Quotations | director (unchanged) |
   | Help, Education | everyone (unchanged) |

   A group with no visible items is not shown at all. **Rate Sheet stays available to `site_engineer`**
   (the plan names them as a Rate Sheet user; `rate-items` works for them) and the screen tolerates its
   `/vendors` refusal quietly -- no error text, the vendor field simply omitted.
8. **The Roles & permissions tab renders `GET /role-permissions`** instead of `rolePermissionsData.js`,
   which is removed. The three "safety-critical rules" (K.3 cost/margin hidden from Sales, the
   Director-only quotation lifecycle gates, the Director-count guardrail) stay as static text, since
   they are prose about behaviour, not a role list. The stale "CA/Tax has Dashboard-only access" note is
   removed (the tab now shows what CA/Tax can actually do).
9. **Phone layout:** the new screen and tabs fit at 375 and 414px (plus 768px and a desktop pass),
   verified as in Amendments 47 and 49.

**Sequencing (one Amendment number, two ordered PRs):** PR 1 = Part A (backend + tests); PR 2 = Part B
(frontend, depends on PR 1). Each is deployed and live-verified before the next header work starts.

### Explicitly out of scope
- **Where each "More" item should live** (Amendment 48's placement decisions -- e.g. moving Help out of
  Admin, or giving Vendor/Tools/Reports their own headers). This amendment only makes each item
  role-accurate where it is.
- Changing any backend role gate, opening any report or screen to another role (for example a CA/Tax
  report), or an editable permissions engine.
- Editing a user's name or email (out of scope by design in `users.py`), bulk import, a login-history view.
- The Sales role's navigation (already correct).

### Acceptance criteria
- As each of the six roles, opening **every visible item** in the sidebar and the "More" menu causes
  **zero refused (4xx) API calls** and no permission-error text (checked with the same real-Chrome
  audit used to find this).
- A Director opening "Team & Access" sees People first, then Roles & permissions; no other role has the
  item, and a non-Director cannot reach the screen.
- "Admin > Master Settings" is the only way to Master Settings and is hidden from procurement,
  site_engineer, ca_tax and sales; for PM it shows the settings and their history with **no write
  controls**; the Director's screen is unchanged.
- Site Engineer opens Rate Sheet with no error text.
- The Roles & permissions tab lists CA/Tax's Payments read access, milestones and the other
  since-added areas (Opportunities, Follow-ups, the Quotations list, the Overview payments block);
  adding a gated route in a test makes it appear with no other change; `rolePermissionsData.js` is gone.
- `GET /role-permissions` is refused to every role but Director; existing tests still pass.
- At 375px and 414px the new screen needs no more width than the phone has.

### Open decisions (proposed defaults)
1. **Team & Access is Director-only.** Proposed: **yes.** (Alternative: also show PM a read-only
   Roles & permissions view -- it would need a second, wider gate on `GET /role-permissions`.)
2. **PM keeps read-only access to Master Settings** rather than losing the item. Proposed: **yes** --
   `GET /settings` already admits PM and its own blurb says "PM is read-only".
3. **Generate the permissions tab from the live route table** (drift-proof) rather than hand-refreshing
   the static file once more. Proposed: **generate.** (Alternative: refresh the file by hand now and
   accept it will drift again.)
4. **Rate Sheet stays visible to `site_engineer`,** degrading quietly on `/vendors`. Proposed: **yes.**
   (Alternative: hide it from them, as the API refuses part of what the screen loads.)
5. **Reports stays hidden from `procurement`, `site_engineer` and `ca_tax`** (the API refuses them).
   Proposed: **yes** -- opening a report type to the CA is a separate, deliberate decision.
6. **Master Settings has a single entry point (Admin > Master Settings),** the "Team & Access" route
   no longer reaches it. Proposed: **yes.**
7. **Two ordered PRs** (backend, then frontend). Proposed: **yes.**

### Approval
☑ Approved — "approve as proposed, all decisions" (25 September 2026)
☐ Approved with changes (noted above)
☐ Not approved

**Prepared by:** R. Patni (with AI development assistance)
**Date:** 25 September 2026
