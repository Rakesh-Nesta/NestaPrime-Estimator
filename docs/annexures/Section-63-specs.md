# Section 63 — Amendment No. 60 Spec

## Amendment No. 60 — Own-Records Visibility and the Personal Dashboard

### Registered scope
The Director's instruction (26 September 2026): **"in a user account, the user should only see his own entries,
not others'; and in the dashboard only his own performance, not the company's performance or revenue."** Evidence
is in `docs/annexures/Annexure-2.md`, Amendment No. 60. In short: today **no role is limited to its own records**
-- every role sees every client, project and quotation -- and every role's dashboard shows **company-wide** counts and
"won this month" revenue. **Clients and projects do not record who owns them**, so "only his own" cannot yet be
enforced; opportunities and documents record their creator.

### Governing principles
- **Only Sales is limited to its own records.** Procurement, Site Engineer and CA/Tax work by function across
  projects; limiting them to "their entries" would stop them doing their jobs. PM and Director see everything.
- **Ownership belongs to the client and the project, not to whoever typed a document.** A rep sees everything under
  a project they own, including an estimate or cost-sheet line a PM prepared -- otherwise their own quotation would
  disappear from their screen when a PM edits it. (Cost and margin stay hidden from Sales, K.3.)
- **Enforced in the server, in one place.** The screen hiding a row is not protection; a guessed id must be refused.
- **Nothing is lost.** Existing records get an owner where one can be recovered; the rest are visible to PM and
  Director and assigned by hand -- never deleted, never silently hidden from the people who run the company.
- **A rep's numbers are theirs to see.** Their own won value and pipeline are their performance, not company revenue.

### Proposed spec

**Part A -- Backend (one migration)**
1. **Owner.** `clients.owner_id` and `projects.owner_id` (a user, nullable) are added. Opportunities already record
   `created_by_id`, which is their owner. Creating a client or project sets its owner to the person creating it;
   converting a Won opportunity gives the client the opportunity's owner; a project created on a client is owned by
   the client's owner unless a PM or Director creates it for someone else.
2. **One rule for "may this person see this?"** A single helper answers it for clients, projects, opportunities and
   everything that hangs off a project (cost sheets, estimates, quotations, work orders, attachments, messages, site
   surveys, payments). **Sales** sees a record only if they own it or its project; every other role is unchanged. It is
   applied to **every** list, the all-quotations and all-estimates lists, follow-ups, quick search (Amendment 53),
   reports and exports, and to **every open-by-id call** -- another rep's record answers **404**, as if it did not
   exist.
3. **Writes are scoped too.** A rep can create a project only on a client they own, and can change only their own
   records. PM and Director may act on any.
4. **Reassign.** PM and Director (and no other role) can change the owner of a client or project, singly or for all of
   one person's records at once; the change is audited. Deactivating a person who owns records offers to reassign
   them first.
5. **Existing data.** A one-time step gives each existing opportunity its `created_by_id`, and each client and project
   the person the audit log shows creating it where the log recorded that; the rest stay **unassigned**. Before the
   deploy, a count of how many rows are recoverable and how many are not is produced and shown to the Director.
   **Unassigned records are visible to PM and Director only**, with a list to assign them; a Sales user sees none of
   them until assigned.
6. **The dashboard.** For **Sales** every number is the rep's own: open projects, pending estimates and quotations,
   follow-ups due, pipeline (new, contacted, qualified), open opportunities, **won this month** (their quotations'
   value), and **recent projects** (theirs). No company total, no company revenue. For **PM and Director** the
   dashboard stays company-wide and gains a **per-salesperson performance table** (open projects, quotations sent,
   won this month, pipeline) so the Director can see who is doing what. Other roles' dashboards are unchanged.
7. **Duplicate clients.** When a rep creates a client that matches one owned by another rep (the app's existing
   duplicate check), they are told "this client already exists under another salesperson -- ask a PM" and shown
   nothing else about it (no name, no phone, no owner). PM and Director see the match as they do today.
8. **Tests**, including: two Sales accounts A and B -- B cannot list, open by id, search, export, attach to, message
   or create a project on A's client (404 or 403), across **every route that takes an id or returns a list** (a
   generated walk, in the spirit of the all-routes test); A sees a PM's estimate on A's project; PM and Director see
   both; unassigned records are invisible to Sales and visible to PM; reassigning moves the visibility; the
   dashboard numbers for A equal a direct count of A's records and contain nothing of B's; the duplicate message
   leaks nothing; each guard removed once to see a test fail. A local, purpose-written check replaces the
   authenticated scan's blind spot: the scan cannot tell whether one person can read another's record.

**Part B -- Screens**
9. **Dashboard** shows a Sales user only their own tiles and lists, labelled as theirs ("My open projects"); PM and
   Director get the company tiles and the per-salesperson table.
10. **Records:** a rep's lists, search and quotations screens simply contain their own; the create-client screen shows
    the duplicate message; PM and Director get an **Owner** column and a reassign control on clients and projects, and
    an **Unassigned** list.
11. **Handbook:** Overview, Clients, Projects, Quotations, and "Who sees what" -- checked by name and by wording.
12. **Phone layout** at 375, 414 and 768px, and a real-Chrome pass as two Sales accounts, a PM and a Director: zero
    refused calls on the rep's own screens; nothing of the other rep's visible anywhere.

**Sequencing (one Amendment number, two ordered PRs):** PR 1 = Part A (backend, migration, backfill, tests); PR 2 =
Part B (frontend). Part A is deployed first; because it changes what a Sales user sees, the unassigned count is
reviewed with the Director **before** it is switched on. Each is verified from outside before the close-out.

### Explicitly out of scope
- Limiting Procurement, Site Engineer or CA/Tax to assigned projects (they keep working by function).
- Team leads, sharing a client between two reps, or hiding a client from PM or Director.
- Commission, targets or ranking beyond the per-salesperson table.
- Any pricing rule or K.3 gate; the Admin role (Amendment 59) and mobile sign-in (Amendment 61).

### Acceptance criteria
- As Sales A: every list, the quotations and estimates screens, follow-ups, search, exports and the dashboard contain
  only A's records; opening B's project or client by id answers 404; A sees the estimate a PM prepared on A's project.
- The Sales dashboard shows no company total or company revenue; the PM's shows company numbers and a table with a
  row per salesperson whose numbers equal a direct count.
- Creating a client that another rep owns gives the plain "ask a PM" message and reveals nothing else.
- PM and Director can see, filter by owner, reassign and bulk-reassign; unassigned records appear in a list for them
  only; deactivating an owner prompts to reassign.
- The Director has seen the recoverable-versus-unassigned counts before Sales scoping is switched on.
- The two-Sales walk over every id-taking and list route passes; the all-routes test, the role-table check and the
  existing suite pass.

### Open decisions (proposed defaults)
1. **Only Sales is limited to own records.** Proposed: **yes.**
2. **A rep sees documents on their own projects that a PM prepared.** Proposed: **yes.**
3. **A per-salesperson performance table for Director and PM.** Proposed: **yes.**
4. **Existing records are backfilled from the audit log where it recorded the creator; the rest are assigned by
   hand.** Proposed: **yes.**
5. **The duplicate-client message shows nothing about the other rep's client.** Proposed: **yes.**
6. **Another rep's record answers 404, not 403** (it looks as if it does not exist). Proposed: **yes.**
7. **Two ordered PRs, with the unassigned review before the switch-on.** Proposed: **yes.**

### Approval
☑ Approved — "approve as proposed, all decisions" (26 September 2026). The five proposals approved in the
conversation were: only Sales limited to own records; a rep sees documents on their own projects even when a PM
prepared them; a per-salesperson performance table for Director and PM; backfill from the audit log with the rest
assigned by hand; the duplicate-client message that reveals nothing; and the order Admin role, then this, then
mobile/email sign-in. Decisions 6 and 7 were added while drafting.
☐ Approved with changes (noted above)
☐ Not approved

**Prepared by:** R. Patni (with AI development assistance)
**Date:** 26 September 2026
