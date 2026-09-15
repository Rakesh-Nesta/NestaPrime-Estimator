# Section 12 — Draft Specification for Director Approval

**Date: 15 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

---

## Amendment No. 13 — AI-Assisted Content (Quotation Narrative, Client Messages, Report Summaries)

**Registered scope (Annexure 2, §2):** *"after that we will work on result meaning
quotation format, and content, messages, reports etc. idea is maximum utilization of AI
in content side."* Director confirmed (15 September 2026): all three areas, and every
AI-drafted piece of content must be human-reviewed before it's sent or saved as
final — no auto-send anywhere.

### Part A — What exists today (checked against the actual code, not assumed)

| Area | Current state |
|---|---|
| **Quotation/Estimate content** | Zero prose anywhere. `Quotation`/`Estimate`/`EstimateOption` (`backend/app/models/document.py`) are 100% structured data — cost, rates, margins, line items. The PDF (`backend/app/api/pdf_documents.py`, reportlab) is fixed boilerplate + structured tables: same heading text, same inclusions/exclusions pulled from the scope-item catalog, same validity/signature paragraphs on every document. Nobody writes a sentence of custom copy today — this is genuinely new territory, not an upgrade to an existing field. |
| **Client messages** | Partway there already. `Message.body_note` (free text, 500-char cap) can already be hand-typed instead of using a `MessageTemplate`, and `MessagesPanel.jsx` sends on submit with **no review/preview step** — clicking Send fires immediately. Consent gating (M.7.2 rule 5: WhatsApp/Telegram/email opt-in per client) and the internal-document channel restriction (M.7.2 rule 7) already exist and are untouched by this amendment. |
| **Reports** | Pipeline / Margin / Override Summary (`backend/app/api/reports.py`) are pure dicts of counts and totals — no narrative field exists on `Report` at all. Role-gating is per-report-type (`VISIBLE_ROLES`): Pipeline is Sales/PM/Director, Margin and Override Summary are PM/Director and Director-only respectively (K.3's cost/margin restriction). An AI summary must inherit whichever gate its source report already has — there's no single blanket rule to reuse. |
| **AI/LLM integration** | None anywhere in the codebase today. Greenfield — no existing service, no existing API key convention to extend, just the general external-integration pattern (see Part C) to follow. |

### Part B — What's new, per area

**B.1 Quotation content — a Cover Note.**
One new optional field, `Quotation.cover_note` (Text, nullable) — a short personalized
introduction paragraph, drafted by AI from that quotation's own data (client name,
sport(s), package, total), shown as an editable textarea on the quotation-release screen
before release. If present, it renders as a new paragraph in the PDF immediately after
the header, before the line-item tables — additive to the existing rigid structure, not
a rewrite of it. Leaving it blank (as today) produces exactly today's PDF, unchanged.

**B.2 Client messages — a draft button, not a new send path.**
A "Draft with AI" action next to the existing note field in `MessagesPanel.jsx`. It
calls the AI service with the project/client/document context already on screen and
fills the *existing* free-text `body_note` field with a suggested message — the person
still reviews/edits it and clicks the *existing* Send button themselves. No backend send
path changes; the review step is simply "AI pre-fills a field a human already had to
approve by clicking Send." Consent/channel gating (M.7.2) applies exactly as it does
today, before and after this change.

**B.3 Reports — an on-demand summary, not a stored field.**
A "Generate summary" button on each report screen. It sends that report's own
already-computed structured data (the same dict the tables render from) to the AI
service and displays the returned paragraph in the UI — copyable, regenerable, **never
persisted**. No new field on `Report`, no change to what's stored or exported; this is
a read-only convenience layer on top of data that's already correct and already
gated by that report's own `VISIBLE_ROLES` entry.

### Part C — Shared infrastructure

**New backend service**, `backend/app/services/ai_content.py`, calling the Anthropic
API (Claude), following this project's own established pattern for optional external
integrations exactly (`wa_gateway.py` / `telegram.py`):
- New setting `anthropic_api_key: str = ""` in `backend/app/config.py`, blank by
  default.
- `_require_configured()` raises `AiContentError` immediately if the key is unset —
  same "blank = not configured, fail fast" discipline, no hung requests.
- Three thin endpoints, one per area (`POST /quotations/{id}/draft-cover-note`,
  `POST /messages/draft`, `POST /reports/{type}/summarize`), each server-side inheriting
  the exact role gate its underlying resource already has (M.2/M.7.2/K.3 respectively) —
  no new gate invented, no broadening of who can see what.
- A disabled/unconfigured key means the three buttons above show "AI drafting isn't
  configured" rather than erroring — same graceful-degradation the WhatsApp/Telegram
  buttons already give when *those* keys are unset.

**Review gate, restated precisely:** every one of the three surfaces above puts AI
output into an already-editable field or an on-screen display, and every path to
"real" — release a quotation, send a message, — already required (and still requires)
an explicit human action after the AI text appears. Nothing added by this amendment
sends, saves, or releases anything by itself.

### Open decisions for Director

**Decision A — Anthropic API key.** This is the one genuinely new operating cost this
amendment introduces (metered per Anthropic's API pricing, unlike everything else in
this app). Needs a Director-obtained `ANTHROPIC_API_KEY` before any of this can go live
in any environment — nothing here works, even in dev, without it. Confirm before
implementation starts.

**Decision B — build order.** Recommend building in the order listed (C: shared
service → B.1: Cover Note → B.2: message drafts → B.3: report summaries) as three or
four separate PRs rather than one large one, matching how every prior Amendment this
project has shipped. Confirm, or reorder by priority.

**Acceptance criteria:** an `ANTHROPIC_API_KEY`-less environment behaves exactly as
today (no broken buttons, no hangs — same graceful-degradation as WA/Telegram); a
configured environment can draft a quotation cover note, a client message, and a report
summary, and in every case a human sees and can edit the AI text before any existing
send/save/release action is taken; no existing document, message, or report gains new
required fields or changes its output when AI content isn't used.

---

## Approval

Amendment 13 overall: ☑ Approved -- "approved, use squash merges as listed" (15 September 2026)
Decision A (Anthropic API key): ☐ Confirmed ☐ Not yet -- key not yet supplied; building
proceeds with the fail-fast pattern (graceful no-op until a key is set), so this isn't a
build blocker, only an end-to-end-testing blocker
Decision B (build order): ☑ Confirmed as listed -- shared service → Cover Note → message
drafts → report summaries, each its own PR, squash-merged

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 15 September 2026
