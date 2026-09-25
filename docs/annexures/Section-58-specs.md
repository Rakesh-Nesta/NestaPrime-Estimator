# Section 58 — Amendment No. 54 Spec

## Amendment No. 54 — Quotation Content (plan Section C: cover letter, descriptive scope of work, company details)

### Registered scope
The Director's instruction (25 September 2026): register and spec Section C, the last open item from
Amendment 48's audit that concerns the client-facing document. The plan asked for three things after the
Director shared a real historical quotation (`SEP-85 Quotation for 54 Er Rg Badminton 14.72L.pdf`): a richer
cover letter, a descriptive scope of work with **no per-line pricing** (the total stays one lump sum),
and Director-configurable terms, bank details and notes. Evidence is in `docs/annexures/Annexure-2.md`,
Amendment No. 54. In short: the third piece is already built (Section 14), and the second is a gap of one
missing call -- the earlier Estimate PDF already describes what each package contains, but the binding
Quotation PDF does not.

### Governing principles
- **Lump sum stays lump sum.** No price is ever attached to a descriptive line, and no new figure
  appears anywhere; only words about what is being delivered.
- **The client-facing document says only what is true and configured.** Text comes from what a Director
  authored (package content, terms, company details) or from this quotation's own data. Anything unset is
  left out of the PDF, never printed as "not configured" or a placeholder, and is reported to the
  person preparing the quotation instead.
- **AI drafts, people decide.** The cover letter draft is grounded only in supplied facts, never saved by
  the draft call, and always reviewed and saved by a person (Amendment 13's rule, unchanged).
- **What a client already received does not change under them.** The new sections appear on quotations
  not yet sent; a sent, won or lost quotation renders as it did.

### Proposed spec

**Part A -- Backend**
1. **A "Scope of work" section in the private-client Quotation PDF** (tender-mode BOQ quotations are
   unchanged), placed after the totals and amount in words: for each sport on the quotation, the
   Director-authored package content for that sport and tier -- flooring, structure, lighting, the scope
   lines and the warranty years -- followed by the project's Part I **inclusions** list (the scope
   checklist items marked included, with their notes). No rupee figure appears in it. The two builders
   already exist for the Estimate PDF (`_package_content_flow`, `_inclusions_and_exclusions`); the
   Quotation PDF computes the inclusions today and never prints them.
2. **A sport whose package content is not configured is left out of that section** -- no "Package content
   not yet configured" line on the client's document (the Estimate PDF's placeholder is not carried over).
   If nothing at all can be shown, the section heading is omitted too.
3. **A cover-letter block** printed at the top of the PDF, **only when the quotation has a cover note**
   (so an unused cover note still changes nothing, as Amendment 13 promised): an addressee line, a
   subject line, the note, and a sign-off.
   - *Addressee:* "Kind attention: <name>, <designation>" from the client's first **active** signatory
     (Part O), else "Kind attention: <contact name>", else no addressee line.
   - *Subject:* "Quotation <document no.> -- <sport names> at <site or city>".
   - *Sign-off:* "Yours faithfully," / "For <company legal name, or NestaPrime Sports Infrastructure>" and
     the authorised signatory's name and designation from two new company settings,
     `company_signatory_name` and `company_signatory_designation`. Unset lines are omitted; if both are
     unset only the "Yours faithfully," / company line is printed.
4. **A richer AI draft for the note** (`POST /quotations/{id}/draft-cover-note`, same contract: returns a
   draft, saves nothing, 503 with the reason on an AI failure): two short paragraphs (about 120-160
   words) instead of two or three sentences, written from **only** these supplied facts -- client name,
   addressee, site/city, each sport with its court count and dimensions, the package tier and its
   configured content lines, the estimated timeline in weeks, the warranty years, the validity period and
   the quotation total. Facts that are not set are not mentioned to the model at all. The prompt forbids
   invented claims (past projects, certifications, guarantees, dates, prices per item) and any
   greeting, sign-off or placeholder, since the PDF prints those itself. The draft endpoint's roles
   are unchanged.
5. **`pdf_gaps` on the quotation:** `GET /quotations/{id}` (and the list used by the Documents screen)
   returns a list of plain sentences naming what the PDF will leave out, e.g. "Bank details are not set
   (no 'Payment to' block)", "No authorised signatory is set (no sign-off name)", "No package content is
   set for Badminton (Standard)", "No cover note (no letter block)". It carries no amounts and is empty
   when nothing is missing; it never blocks release or sending.
6. **Gate:** the new sections and the letter block are rendered only when the quotation has not been
   sent (`sent_at` unset); a sent, won or lost quotation's PDF is built as before.
7. **Tests:** the scope section lists a configured sport's flooring/structure/lighting/scope/warranty and
   the included scope items, contains no rupee amount, and is absent for a sent quotation and in tender
   mode; a sport with no package content is omitted without any placeholder text anywhere in the PDF;
   the letter block appears only with a cover note and uses signatory, then contact, then nothing;
   sign-off lines follow the two new settings; the draft prompt (with the AI call stubbed) contains the
   supplied facts, omits unset ones and carries the no-invention instructions; an AI failure is still a
   503 with its reason and nothing is saved; `pdf_gaps` names each missing thing and is empty when
   complete; every existing PDF test still passes.

**Part B -- Frontend**
8. **Company details** (Master Settings, Director) gains **Authorised signatory name** and **Authorised
   signatory designation**, saved like the other company details, with the card's blurb saying a blank
   field is omitted from the PDF. PM stays read-only (Amendment 51).
9. **The Quotation row** in Documents shows the `pdf_gaps` sentences as a quiet, non-blocking note by
   the PDF download ("The PDF will leave out: ..."), and the cover-note panel's helper text says what the
   AI draft uses and that it is a draft to be checked. Nothing else on the screen changes.
10. **Help handbook:** the Documents, Master Settings (Company details) and cover-note entries are updated
    for the new sections, settings and note -- searched by name **and** by wording about what the
    quotation contains, as Amendments 51-53 taught.
11. **Phone layout:** the Company details card and the notice fit at 375 and 414px (plus 768px and a
    desktop pass).

**Sequencing (one Amendment number, two ordered PRs):** PR 1 = Part A (backend + tests); PR 2 = Part B
(frontend). Each is deployed and live-verified before the close-out.

### Explicitly out of scope
- **Any per-line price or itemised breakdown** -- never, by the Director's constraint.
- **Tender-mode (BOQ) quotations, the Estimate PDF, and every other PDF.**
- **Rewriting the terms and conditions, warranty table or notes.** They are already Director-editable
  (Section 14); the reference PDF is not in the repository, so its 13 clauses cannot be compared here.
  The Director reviews the clause list in Master Settings and edits what differs (decision 9).
- Letterhead, logo or layout redesign; other languages; e-signatures; the client-message (WhatsApp/email)
  text; authoring UI for package content (it exists in Sports & Scope); changing who may draft or edit a
  cover note.

### Acceptance criteria
- A released, unsent private-client quotation for a sport with configured package content prints a
  "Scope of work" section (flooring, structure, lighting, scope lines, warranty years, then the included
  scope items) containing **no rupee amount**, and the total is still one lump-sum figure.
- A sport with no package content is absent from that section, and **no PDF anywhere contains the words
  "not yet configured"**; `pdf_gaps` names the missing content.
- With a cover note the PDF opens with the addressee, subject, note and sign-off; without one, the top of
  the PDF is what it was before this amendment.
- A sent quotation's PDF, and every tender-mode PDF, has none of the new sections.
- The AI draft is two short paragraphs from the supplied facts only; with the AI stubbed, the prompt
  contains those facts and none that are unset; a failure still returns 503 and saves nothing.
- The Director can set and clear the two signatory settings; a blank one is omitted, and PM cannot edit.
- The notice lists exactly what is missing and disappears when it is all set.
- As each of the six roles, opening every visible item causes zero refused (4xx) calls; the existing PDF,
  cover-note and settings tests still pass.
- At 375px and 414px the Company details card and the notice need no more width than the phone has.

### Open decisions (proposed defaults)
1. **Add a "Scope of work" section to the private-client Quotation PDF** from package content plus the
   included scope items, no prices. Proposed: **yes.** (Alternative: keep the Quotation PDF as it is and
   attach the Estimate's package description another way.)
2. **A sport with no package content is omitted from the PDF and reported in-app,** not printed as "not
   configured". Proposed: **yes.**
3. **The letter block prints only when a cover note exists.** Proposed: **yes.** (Alternative: always
   print the addressee and subject.)
4. **Addressee = first active client signatory, else the client's contact name, else none.** Proposed:
   **yes.**
5. **Two new company settings for the authorised signatory's name and designation,** edited in the Company
   details card. Proposed: **yes.** (Alternative: use the signed-in user's own name and role.)
6. **The AI draft becomes two short paragraphs from real facts only** (no invented claims), still a
   reviewed draft. Proposed: **yes.**
7. **Show the "PDF will leave out ..." notice** on the Quotation row (`pdf_gaps`). Proposed: **yes.**
8. **The new sections appear only on quotations not yet sent;** sent, won and lost quotations render as
   before. Proposed: **yes.** (Alternative: apply to every PDF built after the deploy, as terms changes
   already do.)
9. **No code change to terms, warranty or notes; the Director reviews them against the reference PDF** in
   Master Settings. Proposed: **yes.**
10. **Tender-mode quotations are unchanged.** Proposed: **yes.**
11. **Two ordered PRs** (backend, then frontend). Proposed: **yes.**

### Approval
☐ Approved — "approve as proposed, all decisions"
☐ Approved with changes (noted above)
☐ Not approved

**Prepared by:** R. Patni (with AI development assistance)
**Date:** 25 September 2026
