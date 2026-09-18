# Section 17 — Draft Specifications for Director Approval

**Date: 18 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: closes the one gap left in Amendment 8 (Communication & Integrations) —
WhatsApp and Telegram are real, provider-verified sends today; Email has never actually
sent anything, it only logs a manual record.

---

## Amendment No. 8 (continued) — Real Email Sending

**Registered scope (Annexure 2, §2):** *"Amendment 8, add real email sending."*

### Current state

Checked against the actual code: `app/services/` has `wa_gateway.py` and `telegram.py`,
each a small, thin client (one `httpx.post` call, a `_require_configured()` fail-fast
guard, a dedicated exception class) — no `email_gateway.py` or equivalent exists.
`app/config.py` carries zero SMTP/email-provider settings. In
`app/api/messages.py`'s `_dispatch_send()`, the WhatsApp/Telegram branches make a real
provider call and set `Message.status` to `SENT`/`FAILED`; the email branch is a single
`return` with the comment *"email: no provider wired up, stays RECORDED as before this
amendment."*

**What already works and needs no changes** — both real safety gates in
`messages.py` are channel-agnostic and already check email specifically, so real
sending inherits them for free: `_enforce_client_consent()` already blocks a
client-facing email unless `Client.email_opt_in` is set; `_enforce_internal_document_channel()`
already restricts internal documents (Cost Sheet) to the Director-configured
`internal_email_domains` allowlist. Real sending doesn't touch either — it only replaces
what happens after those checks already pass.

### Proposed spec

1. **New `app/services/email_gateway.py`**, following the exact same shape as
   `wa_gateway.py`/`telegram.py`: a `send_email(to, subject, body, attachment_bytes=None,
   attachment_filename=None)` function, an `EmailGatewayError` exception, a
   `_require_configured()` fail-fast guard, no retry/queueing (a failure is
   `Message.status = FAILED` immediately, same as the other two channels).
2. **SMTP, not a vendor API** — proposed as the provider mechanism, since it works with
   any real mailbox the company already has (a Google Workspace or Microsoft 365
   account, or a dedicated transactional-relay account) without picking a new vendor or
   writing a vendor-specific client. Uses Python's own standard library
   (`smtplib`/`email.mime`) — no new dependency, matching this module family's own
   "thin client" discipline. A dedicated transactional API (SendGrid, AWS SES, etc.)
   would need real vendor onboarding and its own client module — a bigger, separate
   decision, not proposed here.
3. **New config keys** (`app/config.py`, same pattern as `anthropic_api_key`/
   `wa_gateway_base_url`): `smtp_host`, `smtp_port` (default 587), `smtp_username`,
   `smtp_password`, `smtp_from_address`, `smtp_use_tls` (default true). Blank
   `smtp_host`/`smtp_username`/`smtp_password` means "not configured" — same fail-fast
   503-equivalent (here, `Message.status = FAILED` with a clear reason) as every other
   AI/provider integration in this app, never a hang.
4. **`messages.py`'s email branch** calls `email_gateway.send_email()` instead of
   returning early — plain text body (matching WhatsApp/Telegram's own plain-text
   sends, not HTML email, to keep this a small, consistent change), the document PDF
   attached the same way WhatsApp/Telegram already attach one when `include_document`
   or a stored attachment is present. `EmailGatewayError` is caught alongside
   `WaGatewayError`/`TelegramError` in the existing `except` clause — no new error-
   handling path, same status-flips-to-FAILED behavior.
5. **`DELIVERED` stays unused for email too** — matching the existing, already-recorded
   rationale for WhatsApp/Telegram (neither provider's API exposes a delivery receipt to
   this app); a successful SMTP send means "accepted for relay by the mail server," not
   "the recipient received it," and this app doesn't claim more than it can verify.

**Acceptance criteria:** with real SMTP credentials configured, sending an email through
the existing Messages panel actually delivers it and the Message row shows `SENT`; with
credentials unset, it fails fast to `FAILED` with a clear reason, never a hang; the
existing consent and internal-domain gates still block exactly what they block today;
WhatsApp/Telegram behavior is completely unchanged.

### Open decisions — need Director input before implementation

1. **Which mailbox/account.** This can't be decided in code — the Director needs to
   supply real SMTP details (host, port, a sending account's username/password or app
   password) for whichever account should be the "from" address, the same way the
   Anthropic API key was supplied for Amendment 13. Proposed default port 587 (STARTTLS)
   unless the chosen provider needs something else.
2. **Confirm SMTP over a dedicated transactional-email vendor.** Proposed as the
   simpler, faster, zero-new-dependency option for this wave. If email volume or
   deliverability becomes a real concern later, a dedicated provider is a legitimate
   follow-on, not attempted here.
3. **Confirm plain-text email** (matching WhatsApp/Telegram) rather than HTML/rich
   formatting for this wave — simpler and more consistent, but a real scope choice worth
   confirming rather than assuming.

---

## Approval

Amendment 8 continuation (real email sending via SMTP): ☐ Approved ☐ Changes ☐ Later

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 18 September 2026
