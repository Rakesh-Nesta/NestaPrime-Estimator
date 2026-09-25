# Section 57 — Amendment No. 53 Spec

## Amendment No. 53 — Global Quick Search

### Registered scope
The Director's instruction (25 September 2026): register and spec the global quick search (plan
B.3), the last cross-cutting gap from Amendment 48's audit that is a product feature. Evidence is in
`docs/annexures/Annexure-2.md`, Amendment No. 53. In short: a rep on a call with a client has no fast
way to pull up that client. The only searches are inside four separate screens, each filtering only its
own list; nothing crosses clients, leads, projects and quotations, and the sidebar and phone top bar
have no search at all.

### Governing principles
- **A search must never reveal more than the person could already open.** Each kind of result is
  shown only to the roles that can already read that kind through the existing screens, and never
  carries cost, margin or any amount (K.3) -- results identify a record, they do not describe it.
- **Say what happened.** No query, too short a query, loading, an error, "nothing matches" and "showing
  the first 6 of N" are different states and read differently; a failed search never looks like an empty
  one (the data-honesty rule).
- **Fast for a phone call.** One tap or one key to start, results as you type, one tap to open.
- **Reuse what exists.** Opening a result uses the screens and open-a-project call that already
  work; this amendment adds finding, not a new record view.

### Proposed spec

**Part A -- Backend (small)**
1. **`GET /search?q=` (new),** open to all six roles, returns results grouped by kind, each group holding
   at most 6 rows plus the true total, e.g. `{query, groups: [{kind, total, items: [...]}]}`. A role
   receives **only the kinds it can already read** (from the existing gates, reused as constants, not
   copied): clients and leads -- `sales`/`pm`/`director`/`procurement`; projects -- all six;
   quotations -- `sales`/`pm`/`director`. An empty `groups` list for a role with no readable kinds is not
   an error.
2. **What is searched** (case-insensitive substring; `%` and `_` in the query are matched literally,
   never as wildcards; a query under 2 characters is refused with a clear 422):
   - *Clients:* name, contact name, phone, email, city.
   - *Leads* (Opportunities not yet linked to a client, or any Opportunity by its lead fields): lead name,
     lead phone, lead email.
   - *Projects:* project number, client name, city.
   - *Quotations:* document number, project number, client name.
   A query of 3 or more digits also matches phone numbers on their digits alone, so `98765 43210` finds
   `+91-98765-43210`.
3. **What a result carries:** kind, id, a primary line (name / project number / document number), a
   secondary line (phone, city, client type / stage / status), and what is needed to open it
   (`client_id`, `project_id`, `opportunity_id`). **No cost, margin, price or any amount** -- the response
   models have no such fields, and a test asserts it for every kind.
4. **Ordering:** exact and prefix matches before other matches, then newest first; deterministic for equal
   rows.
5. **The Roles & permissions screen (Amendment 51) lists `GET /search` with an override label** saying
   results are limited to what the role can read, since the route gate alone (all six roles) would
   otherwise read as broader than it is.
6. **Tests:** anonymous 401; each role gets exactly its kinds (and `site_engineer`/`ca_tax` projects
   only); `%`/`_` literal; the 2-character minimum; phone-digit matching; the 6-row cap with a correct
   `total`; ordering; no amount field in any response; a Sales token receives no cost or margin;
   inactive/blacklisted clients are still found (flags are shown, not hidden); an added-then-searched
   record appears.

**Part B -- Frontend**
7. **A search palette opens from the sidebar's "Search" button** (top of the sidebar, under the
   workspace card), from **a magnifier in the phone top bar**, and from the keyboard: `/` when no field is
   focused, and Ctrl/Cmd+K. It is a centred overlay on desktop and full-width on phones.
8. **Live results as you type** (about 250 ms after the last key), grouped and labelled by kind, each row
   showing its primary and secondary lines; arrow keys move through rows, Enter opens the highlighted
   row, Esc closes, and the field is focused on open. Shown states: a short hint under 2 characters,
   "Searching...", the results, **"Nothing matches "xyz""**, a visible error with a retry button, and
   "Showing the first 6 of N clients" per group when there are more.
9. **Opening a result:** a project or quotation opens that project's Documents screen (the existing
   open-a-project call); a client or lead opens **Leads & Clients with the search box pre-filled with the
   record's exact name**, so the record is the first row (there is no per-record view or deep link today;
   building one is out of scope). The palette closes.
10. **Phone layout:** the palette, its rows and the top-bar magnifier fit at 375 and 414px (plus 768px
    and a desktop pass), verified as in Amendments 47, 49, 51 and 52.
11. **Help:** the handbook gets a short "Quick search" entry (how to open it, what it finds, that it shows
    only what your role can open), and every line naming where to search is checked -- the check is by
    name **and** by wording about gates, as Amendments 51 and 52 taught.

**Sequencing (one Amendment number, two ordered PRs):** PR 1 = Part A (backend + tests); PR 2 = Part B
(frontend, depends on PR 1). Each is deployed and live-verified before the close-out.

### Explicitly out of scope
- Searching inside documents, notes, messages, cost sheets, rate items, vendors, price requests or the
  audit log (each has, or does not need, its own screen), fuzzy or typo-tolerant matching, saved or recent
  searches, and search analytics.
- A per-client or per-lead record view or a deep link into a row (an existing gap noted in Amendment 48);
  here a client or lead result lands on Leads & Clients with the search pre-filled.
- Changing any existing role gate, opening a screen to a new role, or adding pagination to any list.
- Fixing `GET /projects`'s unescaped `%`/`_` in its own `search` parameter (noted in the register; the
  new endpoint does not depend on it).

### Acceptance criteria
- As each of the six roles, opening the palette and searching causes **zero refused (4xx) API calls**;
  the role sees only its kinds; a Sales session's responses contain no cost, margin or amount.
- Searching a client by name, phone (including with different spacing), email, city or contact name finds
  it; a lead by its lead fields; a project by number, client or city; a quotation by document number.
- `%` and `_` typed as the whole query match only records containing those characters.
- A one-character query does no search and says so; a query with no matches says "Nothing matches"; a
  stopped backend shows an error, not "Nothing matches".
- With more than 6 matches a group shows 6 and the true total.
- From the palette, a project opens its Documents screen and a client or lead opens Leads & Clients showing
  that record first; Esc and a tap outside close it; the palette opens by `/`, Ctrl/Cmd+K, the sidebar
  button and (on phones) the top-bar magnifier.
- At 375px and 414px the palette and the top bar need no more width than the phone has, and the results
  can be reached by scrolling.
- `GET /search` appears on the Director's Roles & permissions screen with the limited-results label;
  existing tests still pass.

### Open decisions (proposed defaults)
1. **One new backend endpoint (`GET /search`)** rather than the browser calling the existing list
   endpoints and filtering them itself. Proposed: **new endpoint** -- less data over the wire, one
   place that enforces per-kind visibility, and correct wildcard handling. (Alternative: no backend
   change, fetch and filter the existing lists in the browser as Leads & Clients does.)
2. **Kinds searched: clients, leads, projects and quotations (by document number, no amounts).**
   Proposed: **yes.** (Alternative: clients and projects only, as the plan first wrote it -- "not quotation
   financials"; quotations are included here by number and status only.)
3. **Each role sees only the kinds it can already read,** using the existing gates as the single source.
   Proposed: **yes.**
4. **A palette overlay** (sidebar button, top-bar magnifier, `/` and Ctrl/Cmd+K) rather than a dedicated
   Search screen. Proposed: **yes.** (Alternative: a Search screen in the sidebar.)
5. **Matching rules:** case-insensitive substring, literal `%`/`_`, minimum 2 characters, phone matched
   on digits from 3 digits, 6 results per kind with the true total shown. Proposed: **yes.**
6. **A client or lead result opens Leads & Clients with the name pre-filled** rather than building a
   record view. Proposed: **yes.** (Alternative: build a per-record deep link first, as its own amendment.)
7. **No recent or saved searches.** Proposed: **yes.**
8. **`GET /search` gets an override label on the Roles & permissions screen.** Proposed: **yes.**
9. **Add a short "Quick search" entry to the Help handbook** and check the handbook by name and by gate
   wording. Proposed: **yes.**
10. **Two ordered PRs** (backend, then frontend). Proposed: **yes.**

### Approval
☐ Approved — "approve as proposed, all decisions"
☐ Approved with changes (noted above)
☐ Not approved

**Prepared by:** R. Patni (with AI development assistance)
**Date:** 25 September 2026
