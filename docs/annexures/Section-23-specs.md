# Section 23 — Draft Specifications for Director Approval

**Date: 19 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: self-identified during a Director-requested proactive audit of the codebase
for gaps not yet in the register (see chat log 19 September) — a real security gap, not
a design choice, spot-verified against the live code before being registered as
Amendment No. 17.

---

## Amendment No. 17 — Export Output Sanitization (CSV/XLSX Formula Injection)

**Registered scope (Annexure 2, §Amendment 17):** exported Excel/CSV files write
free-text fields controlled by ordinary app users straight into cells with no escaping,
so a value deliberately crafted to look like a spreadsheet formula executes when the
file is later opened in Excel by whoever receives it — a Director, an accountant, a
client.

### Current state (verified against the actual code)

Every `openpyxl`/`csv` write site in the backend was enumerated directly (`grep -rn
"Workbook()\|csv.writer" backend/app/api/*.py`) rather than guessed:

| File | Line | Sheet/export |
|---|---|---|
| `backend/app/api/exports.py` | 72 | Cost Sheet |
| `backend/app/api/exports.py` | 128 | (second export in the same file) |
| `backend/app/api/exports.py` | 192 | (third) |
| `backend/app/api/exports.py` | 224 | (fourth) |
| `backend/app/api/exports.py` | 268 | (fifth) |
| `backend/app/api/quotations_admin.py` | 161 | Quotation CSV |
| `backend/app/api/rate_items.py` | 625 | Rate Sheet |
| `backend/app/api/reports.py` | 488 | Reports export |
| `backend/app/api/settings.py` | 251 | (a Master Settings export) |
| `backend/app/api/audit_log.py` | 108 | Audit log CSV |

Confirmed directly: `exports.py:79-90` appends `line.item_name`, `line.category`,
`line.spec` (all free text on `CostSheetLine`, settable by Sales/PM/Site Engineer roles
per `backend/app/api/documents.py`) as raw cell values with no escaping, e.g.:

```python
ws.append([
    line.work_package.value,
    line.category,      # free text, unescaped
    line.item_name,      # free text, unescaped
    line.spec,           # free text, unescaped
    ...
])
```

A value like `=HYPERLINK("http://evil.example","click")` or `=1+1+cmd|'/c calc'!A1`
entered as an item name, category, spec, or client name survives untouched into the
exported file. Excel (and most spreadsheet software) treats any cell whose value starts
with `=`, `+`, `-`, or `@` as a formula by default. This is CWE-1236 / OWASP's
CSV-injection class — a real trust boundary (user input → a file consumed by a human
outside the app, often with fewer protections than a browser) that this app currently
has no defense against anywhere.

### Proposed spec

1. **One shared sanitizer**, e.g. `app/core/export_safety.py::sanitize_cell(value)`:
   if a string value starts with `=`, `+`, `-`, or `@`, prefix it with a single leading
   apostrophe (`'`) — the standard, minimal-disruption mitigation (Excel/LibreOffice both
   render a leading apostrophe as "force text," stripping it from display but neutralizing
   formula evaluation). Non-string values (numbers, dates, `None`) pass through unchanged.
2. **Apply it at every write site above** — both the `openpyxl` `ws.append([...])` /
   `ws.cell(..., value=...)` calls and the `csv.writer` rows — to every column that can
   ever hold user-entered free text. System-generated/numeric/enum columns (amounts,
   dates, `.value` on an enum) don't need it, but the sanitizer is cheap enough to apply
   to every string cell uniformly rather than auditing each column's provenance one by
   one and risking a miss.
3. **No change to what's stored** — sanitization happens only at export time, on the
   value written into the cell, never touching the database. A client or item name
   remains exactly as entered everywhere else in the app (Cost Sheet screen, Quotation
   PDF, etc.) — only the raw spreadsheet export gets the defensive prefix.
4. **No frontend change** — this is entirely a backend export-time fix.

**Acceptance criteria:** a `CostSheetLine.item_name` (or any other exported free-text
field) set to `=1+1` (or any string starting with `=`/`+`/`-`/`@`) appears in every
export above as `'=1+1` (or the app's chosen equivalent), not as a live formula; a normal
item name with no leading special character is byte-for-byte unchanged in the export;
existing export tests continue to pass; a new test confirms the sanitizer is applied at
each of the ten write sites listed above (or documents why a specific site is exempt,
e.g. it never writes user-controlled text).

### Open decisions — need Director input before implementation

1. **Sanitization method** — proposed: leading-apostrophe prefix (industry-standard,
   reversible, minimal display disruption). An alternative is stripping the leading
   character entirely, which is more aggressive and would silently alter a legitimately
   named item (e.g. a spec starting with `-` for "minus tolerance"). Confirm the
   apostrophe-prefix approach, or specify a preference.
2. **Scope of write sites** — proposed: all ten sites listed above get the sanitizer
   applied uniformly. Confirm, or flag any of the ten that should be excluded (e.g. if a
   site is confirmed to write only system-generated values, not user-entered text).

---

## Approval

Amendment 17 (export output sanitization): ☑ Approved — "approve as proposed, all
decisions" (19 September 2026)

Decision 1 (sanitization method, leading-apostrophe prefix): ☑ Resolved as proposed.
Decision 2 (scope of write sites, all ten sites uniformly): ☑ Resolved as proposed.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 19 September 2026
