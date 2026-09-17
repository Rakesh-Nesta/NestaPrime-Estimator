# Section 14 — Draft Specifications for Director Approval

**Date: 17 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: this is the broader ask behind the question that led to PR #75/#76 (Quotation
PDFs now embed reference images). This spec covers what's left of that original question
— letting the Director change the Quotation PDF's company details and legal/boilerplate
wording without a developer.

---

## Amendment No. 14 — Customizable Document Templates

**Registered scope (Annexure 2, §2):** letting the Director edit the Quotation/Estimate/
Reports PDFs' company details and boilerplate legal text from a settings screen, based on
three real quotation samples the Director shared showing a much richer document than the
app currently produces.

### Current state (checked against the actual code, not assumed)

**Company details are already settings-driven — just not discoverable.** Seven fields
(`company_legal_name`, `company_pan`, `company_gstin`, `company_bank_name`,
`company_bank_account_name`, `company_bank_account_number`, `company_bank_ifsc`) plus
`company_registered_office_city` and `warranty_years_<client_type>` already flow live
into the Quotation PDF (`_company_details_lines()`, `_starter_terms()`,
`_warranty_years()` in `pdf_documents.py`) the moment a Director sets them. The problem
is entirely UX: Master Settings only offers a generic "Add a new setting" key/value form
(any key, unlabeled) — a Director would have to already know the exact key name
`company_bank_ifsc` to use it. **No backend work needed for this tier**, only a friendly
form.

**Legal/boilerplate text is fully hardcoded, not settings-driven at all.** The 8
Quotation T&C clauses (`_STARTER_TERMS_FIXED` — validity, payment, delivery, warranty
basis, site access, variations, force majeure, taxes) and the 5-row warranty table
(`WARRANTY_TABLE` — which items are manufacturer-backed vs. NestaPrime-workmanship) are
literal Python strings in `pdf_documents.py`. Changing a single word today means a code
change, a PR, and a deploy. This is the real gap.

**Scope is narrower than "Quotation/Estimate/Reports" equally** — checked where these
clauses/tables/company-detail blocks are actually used: `_starter_terms()`,
`WARRANTY_TABLE`, and the bank-details block only ever render inside
`build_quotation_pdf`. The Estimate PDF, Cost Sheet PDF, and Report exports carry no T&C,
warranty, or bank-details section today, so this customization only meaningfully applies
to the **Quotation PDF**. (The company logo and Cover Note already work the same way
across documents that use them; this spec doesn't change that.)

**Full layout control (colors, fonts, section order, custom blocks) is not proposed for
this wave** — see the earlier scoping discussion: that tier is the biggest engineering
lift and the most that can visibly go wrong on a client-facing legal document, for a
request that, on the Director's own follow-up ("forget about content"), turned out not to
be what was actually needed. Flagged as a possible future wave only if the Director wants
it after using this simpler version.

### Proposed spec

1. **A "Company & Quotation Details" panel in Master Settings** (Director-only, same
   gate as the rest of Master Settings) with labeled fields for the 9 keys above,
   replacing the need to know raw key names — writes through the exact same
   `POST /settings` endpoint and versioning every other Setting already uses (a new value
   is a new version effective from today; it never rewrites a Quotation PDF someone
   already generated).

2. **Two new editable text blocks**, stored as Settings (new keys
   `quotation_terms_and_conditions` — the 8 T&C clauses, one per line — and
   `quotation_warranty_table` — item/basis pairs, structured the same way), each seeded
   with **today's exact wording as the default value**, so nothing on the PDF changes for
   anyone until a Director deliberately edits it. `pdf_documents.py` reads from the
   Setting when present, falling back to the current hardcoded list when it isn't —
   same additive-only discipline as the Cover Note and Reference Images features.

3. **A live preview before saving.** Given this touches a legal, client-facing document,
   editing either text block shows a rendered sample Quotation PDF (using a real recent
   Quotation as sample data, clearly marked as a preview) before the change is confirmed
   — so a formatting mistake is caught before it's live on every future Quotation, not
   discovered on the next one a Sales rep happens to generate.

4. **Audit trail**: reuses the existing Setting → Audit Log wiring already in place for
   every other Master Setting — no new work needed here, just confirming it applies.

**Acceptance criteria:** a Director can find and edit all 9 company-detail fields from a
labeled form, not a raw key/value box; editing the T&C or warranty table text updates the
next-generated Quotation PDF and shows a preview first; a Quotation generated before an
edit is unaffected (each PDF is built live from whatever the Setting says at download
time, so this is a going-forward change, not a retroactive rewrite); no other document
type (Estimate, Cost Sheet, Reports) changes behavior, since none of them use these
fields today.

### Open decisions — need Director input before implementation

1. **Confirm scope.** This spec proposes Quotation PDF only, since that's the only
   document that actually uses company details/T&C/warranty today. If the Director wants
   Estimate/Reports to gain their own equivalent sections (they don't have any today),
   that's new scope beyond "customizable" — it would mean designing what those documents
   should say first, which is a different, larger spec.
2. **Confirm depth.** Proposed: company-details panel + editable T&C/warranty text
   (Tiers 1–2 above). Full layout/color/font control (Tier 3) is proposed as explicitly
   out of scope for this wave — confirm, or ask for it to be scoped instead.
3. **Live preview** — confirm this is wanted before every text-block save, or whether
   save-immediately (faster, less safe) is preferred instead.

---

## Approval

Amendment 14 (customizable Quotation company details + T&C/warranty text, Tiers 1–2):
☐ Approved ☐ Changes ☐ Later

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 17 September 2026
