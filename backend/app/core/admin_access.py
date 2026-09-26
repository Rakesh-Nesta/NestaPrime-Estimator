"""Amendment 59 (Section 62): what an Admin may touch, in one place.

An Admin runs the system -- people, access, company identity, templates, field settings -- and does not approve,
price or see cost and margin. These constants are imported by the routers that enforce it (settings, audit log,
users); this module imports nothing so it can be used from anywhere without a cycle."""

# The only Master Settings an Admin may read or change: company identity. The four bank-account settings are
# deliberately absent (a changed account on client-facing quotations is a fraud route, so it stays with the
# Director), as is every setting that prices or words a quotation.
ADMIN_SETTING_KEYS = frozenset(
    {
        "company_legal_name",
        "company_gstin",
        "company_pan",
        "company_registered_office_city",
        "company_signatory_name",
        "company_signatory_designation",
    }
)

# Audit-log entries whose old/new values an Admin may see. Everything else -- quotations, costs, rates, margins,
# clients, work orders -- shows who changed what and when, with the values hidden (K.3). Listing what is visible,
# rather than what is hidden, means a newly audited field is hidden from an Admin until someone decides otherwise.
ADMIN_VISIBLE_AUDIT_DOCUMENT_TYPES = frozenset({"user", "field_setting", "message_template"})

HIDDEN_FOR_ROLE = "(hidden for your role)"


def admin_may_see_audit_values(document_type: str, field: str) -> bool:
    if document_type in ADMIN_VISIBLE_AUDIT_DOCUMENT_TYPES:
        return True
    return document_type == "setting" and field in ADMIN_SETTING_KEYS
