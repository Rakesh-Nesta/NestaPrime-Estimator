# Section 8 — Draft Specification for Director Approval

**Date: 13 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

---

## Amendment No. 8 — Communication & Integrations (WhatsApp, Email, Telegram)

**Registered scope (Annexure 2, §2):** "Document sharing and messaging from the app with
delivery status. Opportunity: investigate the company's existing wa-gateway server before
any paid BSP. Telegram easiest to start. Largest build; after Amendments 1–7."

### Current state

**In this app:** a `Message`/`MessageTemplate` system already exists, but it is a log
only — confirmed by reading the code, and the frontend panel says so directly to the
user ("This app has no email/WhatsApp provider wired up... it does not actually send
anything"). What's already built and working: channel enum (`email`/`whatsapp` — no
Telegram yet), a `status` field that only ever reaches `RECORDED` (`SENT`/`DELIVERED`/
`FAILED` exist as placeholders nothing populates), client consent gating
(`whatsapp_opt_in`/`email_opt_in` on `Client`, already enforced before a message record
can be created), an internal-document rule (Cost Sheet messages are email-only, internal
domains only — never WhatsApp), a Director-managed template library with a WhatsApp
Meta-approval-style workflow (`draft/submitted/approved/rejected`), and a
document-attachment link. All of this governance is real and already enforced — nothing
here needs to be rebuilt, only wired up to something that actually sends.

**wa-gateway:** the company's self-hosted WhatsApp backend (C:\wa-gateway on this
machine) — Node/Express + Baileys (the unofficial WhatsApp Web protocol), Docker-first,
no per-message fees, no paid BSP. Investigated directly: it is running right now
(`/health` → ok) and already paired to a real business number (+91 94066 60012, instance
status `open`). It exposes `POST /sendText` (to, text) and `POST /sendMedia` (to, type,
url-or-**base64**, caption, fileName) — the base64 path means NestaPrime can send a
generated PDF straight from memory without needing to host it anywhere first, and
without opening any new public endpoint on our own server. It pushes `message.sent`
(with WhatsApp's own message id) to a webhook once Baileys confirms the message left our
session, and `message.received`/`connection.update`/`qr.updated` for the rest. **One
real limit found in the source:** wa-gateway only ever reports "sent" — Baileys' delivery
and read receipts are not wired up in it, so a true "Delivered"/"Read" tick is not
available from this integration. "Delivery status" here can honestly mean
Recorded → Sent → Failed, not Recorded → Sent → Delivered → Read.

Telegram and real email (SMTP) have no existing infrastructure at all — a Telegram bot
would need to be created from scratch (BotFather), and no SMTP credentials or provider
exist today.

### Proposed spec

**1. Wire WhatsApp sending into the existing `Message` flow.** `POST /messages` keeps
every governance check it already has (consent, internal-doc gating, template
approval) and, for `channel=whatsapp`, additionally calls wa-gateway's `sendText` (for a
note-only message) or `sendMedia` with the relevant document's PDF base64-encoded in
memory (for Estimate/Quotation — Cost Sheet stays excluded, unchanged from today's
internal-only rule). The response's WhatsApp message id is stored on a new
`provider_message_id` column; status becomes `SENT` on a successful call, `FAILED` on
error (e.g. instance not connected, 409).

**2. Delivery-status webhook.** A new `POST /integrations/wa-gateway/webhook` endpoint,
verified against wa-gateway's `X-Webhook-Secret` header, matches an inbound
`message.sent` event to a `Message` row by `provider_message_id` — mostly a
confirmation/reconciliation step, since the send call above already marks `SENT`
synchronously. `DELIVERED` is dropped from active use (see the real limit above); the
enum value stays defined for a future BSP swap but nothing sets it.

**3. Frontend.** `MessagesPanel.jsx` drops its "this doesn't send anything" banner for
WhatsApp, replaces "Log sent message" with "Send" for that channel, and shows the real
status (Recorded/Sent/Failed) instead of always Recorded. Email and Telegram keep
today's log-only behaviour and banner, unchanged.

**4. New config.** wa-gateway base URL, API key, and webhook secret as backend env vars
(none exist today) — same secrets-in-env-not-code pattern as everything else in this
app.

### Three open decisions — need Director input before implementation

**Decision A — channel scope for this build.** The register itself points two directions
at once: "investigate wa-gateway before any paid BSP" (WhatsApp) vs. "Telegram easiest to
start." Now that wa-gateway is confirmed already running and already paired to a real
number, WhatsApp is the smaller build of the two (Telegram needs a bot built from
scratch, with no existing infra to lean on) —
- **WhatsApp only this wave (Recommended):** ships the real send + delivery-status wiring
  above for WhatsApp; Email and Telegram stay exactly as they are today (log-only,
  unchanged banner) and move to a later wave.
- **WhatsApp + Telegram both this wave:** doubles the build — a new Telegram bot,
  `MessageChannel.TELEGRAM`, a second provider integration and webhook — before either
  ships.

**Decision B — where wa-gateway runs in production.** It only runs on this development
machine today (`localhost:8080`), not on the production server
(`65.1.234.78`) that hosts NestaPrime Estimator — for real sends from production, it
needs to be reachable from there.
- **Deploy wa-gateway onto the production server (Recommended):** a new set of Docker
  services (already Docker-first) alongside the existing NestaPrime containers; I hand
  off deploy commands the same way as every other change this session (no SSH access).
  Same paired number (+91 94066 60012) carries over — WhatsApp session state lives in a
  Docker volume that can be copied across.
- **Keep wa-gateway on a separate host:** Director supplies the URL/API key for wherever
  it should actually run, and NestaPrime's production backend just points at that
  instead.

**Decision C — keep the template-approval gate for WhatsApp sends?** wa-gateway is not a
Meta-approved Business Solution Provider, so WhatsApp itself imposes no template-approval
requirement on what it sends — the existing `whatsapp_template_status` workflow
(draft/submitted/approved/rejected) was built anticipating a real BSP, not this path.
- **Keep requiring Director-approved templates anyway (Recommended):** an internal
  content-quality control independent of what WhatsApp itself requires — Sales still
  can't send a template that hasn't been reviewed. Free-text (no template selected)
  stays allowed exactly as today.
- **Drop the approval gate for WhatsApp sends:** any active template can be used
  immediately once created; nothing stops an unreviewed message from going out.

**Acceptance criteria:** from an Estimate or Quotation's Messages panel, sending via
WhatsApp to a client with `whatsapp_opt_in=true` actually delivers a real WhatsApp
message (text or the document as a PDF attachment) through the paired number, and the
Message row's status reflects Sent or Failed truthfully — never a status the system can't
actually verify. A client without `whatsapp_opt_in` (or a Cost Sheet, an internal-only
document) cannot be WhatsApp-messaged, exactly as today's consent/internal-doc rules
already enforce. Email and Telegram remain log-only, with their existing "this doesn't
send anything" banner intact, until a later wave.

---

## Approval

Amendment 8: ☐ Approved ☐ Changes ☐ Later
Decision A (channel scope): ☐ WhatsApp only this wave ☐ WhatsApp + Telegram both
Decision B (wa-gateway production hosting): ☐ Deploy to production server ☐ Separate host (details to follow)
Decision C (template-approval gate): ☐ Keep requiring approval ☐ Drop the gate for WhatsApp

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 13 September 2026
