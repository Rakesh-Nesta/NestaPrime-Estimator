# Section 54 — Amendment No. 50 Spec

## Amendment No. 50 — Payments Header (Header Index Step 9)

### Registered scope
The Director's instruction (24 September 2026): register and spec Payments. Evidence is in
`docs/annexures/Annexure-2.md`, Amendment No. 50; this is Gap 3 of Amendment 48's audit. In
short: the header is a "Coming soon" placeholder; the app records only money *already received*
(no expected amounts, no due dates, so nothing can be overdue); entries cannot be corrected;
there is no cross-project view; and the reference's "Payments overdue" tile and "Orders &
collections" chart have no data behind them.

### Governing principles (from the blueprint and the register)
- **Reconciliation, not accounting.** Part O's BILLING note allows "a simple reconciliation
  entry, not a system computing tax." This spec adds expected-payment milestones and derives
  totals from figures people enter; it **does not** compute GST, TDS, invoices or RA bills.
- **Data honesty.** Nothing is invented: no schedule is inferred from the client's free-text
  payment terms, and "overdue" exists only where a person entered a due date. A number that
  isn't backed by data shows "--", never 0.

### Proposed spec

**Part A -- Backend**
1. **New table `work_order_payment_milestones`** (hand-written migration): `work_order_id`,
   `name`, `amount_due` (> 0), `due_date`, `notes`, `created_by_id`, `created_at`. A milestone
   is a *promise to be paid*; a receipt is a *fact*. Both stay separate.
2. **`work_order_payment_entries.milestone_id`** -- a nullable FK. A receipt may be recorded
   against a milestone; an unlinked receipt still counts toward the Work Order's totals.
   The link must be to a milestone of the same Work Order.
3. **Endpoints** (all `pm`/`director` to write): `POST` / `GET
   /work-orders/{id}/payment-milestones`, `PATCH` / `DELETE /payment-milestones/{id}`, and
   `PATCH /payment-entries/{id}` (edit amount, date, TDS, notes, milestone link). The existing
   `POST .../payment-entries` gains the optional `milestone_id`. Receipts stay **non-deletable**
   (a wrong one is corrected by editing it); milestones may be deleted.
4. **Validation:** the milestones of a Work Order may not total more than its order value (the
   Won Quotation's `quotation_total`, GST-inclusive, frozen -- there is no separate editable
   contract value). Receipts may exceed order value (advances, extra work) and are shown as
   "over-received", not refused.
5. **Derived, never stored:** per milestone -- `received_amount`, `tds_amount`,
   `settled_amount` (= received + TDS withheld), `outstanding_amount`, `status`
   (`pending` / `part_paid` / `paid`), and `overdue` (`due_date` earlier than today and not
   `paid`). Per Work Order -- order value, total received, total TDS withheld, outstanding
   (= order value - received - TDS), next due date, overdue amount.
6. **`GET /payments`** -- one row per Work Order (project no., client, order value, received,
   TDS, outstanding, milestone count, next due date, overdue amount), filterable by overdue and
   searchable. **Read: `pm`, `director`, `ca_tax`** (the last read-only, for TDS reconciliation).
7. **Audit log:** every create, edit and delete of a milestone, and every create and edit of a
   receipt, is audit-logged with old and new values (these are money figures; the existing
   receipt-create is brought under the same rule).
8. **Overview data:** `GET /dashboard` gains `payments_overdue_amount`,
   `payments_overdue_count`, `payments_tracked_milestones_count`, and a six-month series of
   *awarded Work Order value* (by `WorkOrder.awarded_at`) against *cash received* (by
   `received_date`), returned only for `pm`/`director`/`ca_tax` (null for other roles).
9. **Tests:** validation (amounts, milestone total cap, cross-Work-Order link refused), derived
   statuses and overdue at the boundaries, TDS counted as settled, edit-audit entries, role gates
   (write pm/director; read also ca_tax; sales/procurement/site_engineer refused), the org list
   and its filters, and the Overview figures agreeing with the list.

**Part B -- Payments screen and Work Order panel (frontend)**
10. **The Payments header becomes a real screen** (restyled to the newer header pattern):
    summary cards (Order value, Received, TDS withheld, Outstanding, Overdue) computed from the
    list, tabs **All / Overdue**, a search box, and one row per Work Order that expands to its
    milestones and receipts. `pm`/`director` can add and edit milestones, record and edit
    receipts (choosing which milestone a receipt is against), and delete milestones;
    `ca_tax` sees everything read-only. The client's payment terms are shown as a *reminder*
    beside "Add milestone" -- not parsed into a suggested schedule.
11. **The Work Order panel on Documents** shows the same milestones, lets the receipt form pick
    a milestone, and links to the Payments screen.
12. **Nav:** "Payments" loses its muted "Soon" badge and is shown only to `pm`, `director`,
    `ca_tax`; hidden for the others, as Amendment 46 did for Leads & Clients.
13. **Phone layout:** rows as stacked cards, no sideways page scroll, verified at 375px and 414px
    (plus 768px and a desktop pass) with the same real-Chrome method as Amendment 47.

**Part C -- Overview wiring (frontend)**
14. **"Payments overdue" tile** shows the overdue rupee total with the count, linking to the
    Payments screen filtered to Overdue; **"Orders & collections" panel** shows totals and the
    six-month awarded-value vs cash-received bars. If no milestones exist anywhere, the tile
    shows "--" with "No due dates set" -- never 0. Roles without access do not see the tile or
    the panel.

**Sequencing (one Amendment number, three ordered PRs, as Amendment 44 was):** PR 1 = Part A
(model, migration, API, tests); PR 2 = Part B (screen and Work Order panel); PR 3 = Part C
(Overview). Each is deployed and live-verified before the next.

### Explicitly out of scope
- Inferring or parsing a milestone schedule from `Client.payment_terms`.
- Invoices, RA bills, GST or TDS *computation*, credit notes, refunds, payment gateways or
  client-facing payment links.
- Reminders or notifications (email, WhatsApp, Telegram) -- overdue is shown, not pushed.
- Ageing reports and CSV export; Sales/Procurement/Site-Engineer access.
- Any change to Work Order creation, status, or the Quotation lifecycle.

### Acceptance criteria
- A PM can add a milestone with an amount and due date to a Work Order, record a receipt against
  it, and see it move pending -> part paid -> paid; a milestone past its due date and not paid
  shows as overdue.
- A milestone total above the order value, and a receipt linked to another Work Order's
  milestone, are refused with a clear message.
- A mistyped receipt can be edited, and the edit appears in the audit log with old and new
  values; a receipt cannot be deleted.
- The Payments screen's totals equal the sum of its rows; the Overview tile's overdue total and
  count equal the Overdue tab's; both equal the API's own figures.
- With no milestones anywhere the Overview shows "--" / "No due dates set", not 0.
- `ca_tax` can read Payments but not change anything; Sales, Procurement and Site Engineer have no
  Payments item and are refused by the API.
- At 375px and 414px the screen needs no more width than the phone has.
- No existing test regresses; new tests cover everything listed in Part A item 9.

### Open decisions (proposed defaults)
1. **Who sees Payments.** Proposed: **`pm` + `director` write, `ca_tax` read-only**, hidden
   from `sales`, `procurement`, `site_engineer`. (Today's Work Order payment data is PM/Director
   only; a CA reconciling TDS is the natural reader.)
2. **Milestones may not total more than the order value.** Proposed: **refuse.** (Alternative:
   warn only.)
3. **TDS withheld counts as settled** (outstanding = order value - received - TDS), shown as its
   own line. Proposed: **yes** -- the payer has paid that part to the government on the
   vendor's behalf. **This is an accounting judgment: please confirm it with the CA.**
4. **Receipts become editable (audit-logged) but stay non-deletable; milestones may be
   deleted.** Proposed: **yes.**
5. **Order value = the Won Quotation's frozen `quotation_total`** (GST-inclusive); no separate
   editable contract value. Proposed: **yes.**
6. **Milestone status is derived, never stored.** Proposed: **yes** (so it can never disagree
   with the receipts).
7. **The Overview shows "--" / "No due dates set" when nothing is tracked, and hides the tile and
   panel from roles without access.** Proposed: **yes.**
8. **"Orders & collections" uses Work Order award date, not a won date** (Quotation has no
   `won_at`). Proposed: **yes** -- labelled "awarded Work Orders", and Won Quotations that have
   no Work Order yet are not counted.
9. **Three ordered PRs** (API, screen, Overview). Proposed: **yes.**

### Approval
☑ Approved — "approve as proposed, all decisions" (24 September 2026)
☐ Approved with changes (noted above)
☐ Not approved

**Prepared by:** R. Patni (with AI development assistance)
**Date:** 24 September 2026
