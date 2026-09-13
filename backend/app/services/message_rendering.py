"""Amendment 8 (Section 8): renders a MessageTemplate's {placeholder}
text against the real document being sent. Only used for the outbound
text actually handed to a provider (WhatsApp/Telegram) -- Message.body_note
and MessageTemplate.body themselves keep storing the literal template
text, unchanged, same as before this amendment.

Unknown placeholders are left literal rather than raising, so a typo or
a not-yet-supported token doesn't block a send -- the same "never
fabricate, never crash on the unexpected" discipline used elsewhere in
this app (e.g. Section 7's Fencing unit handling).
"""

from app.models.setting import DocumentType
from app.pdf_utils import format_inr


class _LiteralOnMissing(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def render_placeholders(text: str, doc_type: DocumentType, document, client) -> str:
    context: dict[str, str] = {}
    if client is not None:
        context["client_name"] = client.name

    document_no = getattr(document, "document_no", None)
    if document_no:
        context["document_number"] = document_no
        context["estimate_number"] = document_no
        context["quotation_number"] = document_no

    if doc_type == DocumentType.QUOTATION and getattr(document, "quotation_total", None) is not None:
        context["amount"] = format_inr(float(document.quotation_total))

    expires_at = getattr(document, "expires_at", None)
    if expires_at is not None:
        context["validity"] = expires_at.date().isoformat()

    return text.format_map(_LiteralOnMissing(context))
