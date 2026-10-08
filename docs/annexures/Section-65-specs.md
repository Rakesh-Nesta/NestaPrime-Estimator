# Section 65 — Amendment No. 62 Spec

## Amendment No. 62 — Professional Document Templates & Final Output Management

**Status: requirements approved; preview-first sequence approved; NOT implemented, NOT deployed.** Approved by the
Director on 4 October 2026 at 23:53 IST (source: the approved document-template amendment in the reconciliation
hand-off, `Approved-Document-Template-Amendment.html`); clarified by the Director on 5 October 2026 (Section 3 and 5
below). The number 62 was checked against this register (Amendments 1-61 only; no `Section-65` file existed; no branch,
PR or commit referred to Amendment 62 or later) and is the next unused number.

**Relationship to existing amendments (original history is preserved, not edited):**
- **Amendment No. 14 -- Customizable Document Templates.** A14 delivered Tiers 1-2 for the **Quotation only** (a Master
  Settings "Company details" panel and a Director-editable "Quotation terms & warranty" editor with a live preview) and
  explicitly left "full layout/color/font control (Tier 3)" out of scope. **This amendment extends A14; it does not
  replace it.** A14's entry and spec stay as written.
- **Amendment No. 59 -- The Admin role.** Its permissions are **preserved**: an Admin may read and change only the
  company-identity settings; the four bank-account settings and every setting that prices or words a quotation stay
  **Director-only**. See Section 3.
- **Must be preserved by every template:** Amendment 54 (added Quotation content prints only on quotations not yet
  sent), Amendment 57 (one row per sport), Amendment 24 (the GST label back-derived from the document's own frozen
  amounts) and the nearest-Rs-10 rounding policy with its rounding row (#283); the existing export controls (a selected
  image is never dropped silently).

### 1. Objective and scope
Provide consistent, professional templates for CRM documents intended for final download, printing or sending. Replace
the current quotation presentation with reviewed alternatives. Inventory quotations, proposals, estimates, invoices,
receipts, purchase orders, work orders, agreements, completion/handover documents and reports. Apply to **existing
outputs first**; future outputs follow their own module implementation. An invoice template does not independently
authorize invoice issuance or alter accounting authority.

### 2. Choices and design
At least five professional templates for each supported document category, sharing components where appropriate:
**Corporate Classic, Modern Minimal, Detailed Technical, Tender / Institutional, Branded Presentation**; each adapted to
the actual document. Start by presenting **five quotation previews**, prioritizing Corporate Classic and Detailed
Technical for Nesta Prime. Use the original company logo. Support client/project details, document numbers and
revisions, readable tables, page numbering, headers/footers, long descriptions, multipage content, photographs, terms
and signatures without overlap or clipping.

### 3. Admin authority (as clarified 5 October 2026)
**Admin manages layouts and template availability:** add, duplicate and edit templates through controlled layout
settings; preview, publish, activate and set defaults by document category; retire templates from future selection;
delete unused drafts; archive templates used by issued documents; inspect versions and audit history.
**Unchanged (Amendment 59 and Amendment 14):** bank-account details and commercial wording (terms and conditions,
warranty text, anything that prices or words a quotation) remain **Director-only**. Template management does not grant
access to restricted report data, approval authority over business transactions, or permission to change financial
calculations.

### 4. User workflow
Select a published template, preview the complete document, complete the existing approval/issuance steps, then
download, print or send. Existing user permissions apply. Previewing never automatically issues, approves or sends.
An invalid or unavailable template produces a clear error rather than silently switching formats.

### 5. Integrity and history (as clarified 5 October 2026)
Use the same authoritative CRM data and calculations across templates. Preserve amounts, taxes, discounts, rounding,
payment status, numbering, mandatory information and approval rules. **Preserve the exact issued file alongside the
document revision and the template version used.** Later layout changes must not alter historical documents.
Corrections use the existing revision/reissue process.
*(Current state, for the implementer: PDFs are generated live on each request and never stored; a sent message keeps
only a hash of the bytes sent. Storing the issued file therefore needs its own design inside the implementation step.)*

### 6. Acceptance
The Director accepts the quotation designs before editor implementation. Verify identical business values across
layouts, long and short documents, page breaks, rupee amounts, supported languages, photographs and print quality.
Verify Admin controls, user permissions and audit records. Retired templates cannot be selected for new documents;
historical issued files remain unchanged.

### 7. Delivery order (approved)
1. Complete the pending-work reconciliation (done: `pending-work-register-2026-10-05-r3.md` accepted as the baseline).
2. **Inventory the existing outputs and prepare five quotation previews.**
3. **Director design acceptance of the quotation previews** -- a hard gate; nothing below starts before it.
4. Implement template management and quotation integration, including preservation of the exact issued file with the
   document and template versions.
5. Extend to existing reports and outputs.
6. Future finance and lifecycle documents, each with its own module.

### Explicitly out of scope of this amendment
Changing any calculation, tax, discount or rounding rule; changing who may approve, issue or send a document; issuing
invoices or changing accounting authority; message templates (WhatsApp/email wording), which are a separate feature.
