"""Amendment 17 (Section 23): defends against CSV/XLSX formula injection.

A value any app user can enter -- an item name, client name, category,
spec, vendor name, etc. -- that starts with '=', '+', '-', or '@' is
treated as a live formula by Excel/LibreOffice the moment the exported
file is opened outside the app. Prefixing it with a single leading
apostrophe forces "text" display, neutralizing the formula without
touching what's stored in the database or shown anywhere else in the
app -- only the raw exported cell is affected.

Only wrap the row lists passed to ws.append(...)/writer.writerow(...).
Never wrap a live spreadsheet formula this app writes itself (e.g. the
Cost Sheet export's own "=F{row}*G{row}" Amount cells, set via a
separate ws.cell(..., value=f"=...") call) -- those aren't user input
and must keep working as real formulas.
"""

_FORMULA_PREFIXES = ("=", "+", "-", "@")


def sanitize_cell(value):
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def sanitize_row(row):
    return [sanitize_cell(v) for v in row]
