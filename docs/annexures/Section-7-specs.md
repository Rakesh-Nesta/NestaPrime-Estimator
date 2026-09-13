# Section 7 — Draft Specification for Director Approval

**Date: 13 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

---

## Amendment No. 3 — "Complete Your Facility" Cross-Sell at Estimate Step

**Registered scope (Annexure 2, §2):** "At the Estimate step, suggest 4–5 sport-matched
add-ons (lighting, fencing, seating, AMC) with prices and own margins; one-tap add;
never forced."

### Current state
Nothing like this exists yet (confirmed by a full repo search). The closest neighbours
are all different concepts: `PackageContent` is Director-authored descriptive text for
what a package tier already includes (no price, no margin, not an add-on); the
Accessories Cost Sheet tab is an internal, cost-side take-off tool with no client
visibility and no margin of its own; `EstimateOption` carries exactly one aggregate
`cost_for_option` number with no child items — there is nowhere today an "extra item"
could attach to an Estimate. AMC exists only as an unpriced checkbox in the Additional
Scope Checklist (Part I), not a real product.

### Proposed spec

**1. Add-on catalog** — a new `CrossSellAddon` table (Director-managed, mirroring the
existing Rate Sheet/Vendor Product pattern): name, category (Lighting / Fencing /
Seating / AMC / other), description, cost (internal), margin % (its own, Director-set —
not the project's client-type margin policy), sport-scoping (a many-to-many link to
Sport, since e.g. Fencing suits outdoor court sports generally while AMC suits
everything), is_active. Selling price is computed from cost + margin the same way K.2
already computes every other selling price — never a flat typed-in client price, so a
margin change stays auditable the same way rate/margin changes are everywhere else in
this app.

**2. Suggested at the Estimate step** — when viewing/creating an Estimate, the screen
shows up to 5 active add-ons matched to the project's selected sport(s) (an add-on
matches if it's tagged to at least one of the project's sports, or tagged "all sports"
for something like AMC). Each shows its selling price only — K.3's cost/margin
visibility split applies here exactly as everywhere else (Sales sees the price, never
the cost or margin behind it).

**3. One-tap add, never forced** — a new `EstimateOptionAddon` child row (one per
option × add-on), created with a single click; each carries a frozen snapshot of the
add-on's price/cost/margin at the moment it was added (the same freezing principle used
throughout this app — M.2's rule that a document's figures don't silently drift when
the underlying master data changes later). Shown as a separate "Optional add-ons"
subtotal alongside the base option's price range, not folded into it — so a client sees
exactly what the base facility costs and exactly what each optional extra would add,
never a blended number they can't unpick. Removable with the same one-tap simplicity
before the Estimate is sent.

### Two open decisions — need Director input before implementation

**Decision A — does an added add-on carry through to the real Quotation?** The
registered scope names only "the Estimate step." Two honest options:
- **Estimate-only (smaller, matches the literal registered scope):** add-ons are a
  persuasive tool at the Estimate stage — visible to the client on the Estimate, but
  the actual Quotation (the document that becomes a binding, invoiced commitment) is
  built from the Cost Sheet exactly as it is today, unaffected by which add-ons were
  shown or added at Estimate time. A Sales/PM would need to fold an accepted add-on's
  scope into the Cost Sheet manually (e.g. a Manual Line) before quoting it for real.
- **Full flow-through (larger):** an add-on the client keeps through to Quotation time
  becomes a real Quotation line item automatically, actually contributing to the
  invoiced total — closer to what "Complete Your Facility" implies as a sales tool, but
  a materially bigger build (touching Quotation creation/pricing, not just the Estimate
  screen).

**Decision B — starter catalog pricing.** I don't have defensible real-world pricing for
all four named categories. Fencing has real reference data from Note R1's historical
review (chain-link ₹120/sqft, SS railing ₹440/rft); Lighting's historical data was
explicitly flagged there as not cleanly extractable (every historical quote bundles
fixtures/poles/wiring together); Seating and AMC have no reference data anywhere in the
23 quotations reviewed. Proposing the same discipline as Note R1's rate card: seed only
Fencing with a real starter price, and add Lighting/Seating/AMC as real catalog rows
with `cost = null` — present in the system, sport-tagged, ready to use, but inactive
(hidden from the Estimate screen) until a PM/Director enters a real cost, rather than
fabricate plausible-sounding prices for a client-facing document.

**Acceptance criteria:** an Estimate for a project with e.g. Badminton shows up to 5
active, sport-matched add-ons with selling price only; one click adds one to that
option's Estimate view as a separate line, another click removes it before sending;
Sales never sees an add-on's cost or margin, only its price; an inactive (no-cost)
add-on never appears as a suggestion.

---

## Approval

Amendment 3: ☐ Approved ☐ Changes ☐ Later
Decision A (add-on flow-through): ☐ Estimate-only ☐ Full flow-through
Decision B (starter pricing): ☐ Approved as scoped ☐ I'll supply real prices for
Lighting/Seating/AMC too

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 13 September 2026
