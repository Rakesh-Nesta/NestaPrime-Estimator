# Section 15 — Draft Specifications for Director Approval

**Date: 18 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: closes the Education nav slot Amendment 12 reserved but never filled, using
the AI integration Amendment 13 already built rather than a new ChatGPT/OpenAI
connection (Director instruction, confirmed).

---

## Amendment No. 15 — Education Tab AI Assistant

**Registered scope (Annexure 2, §2):** an AI assistant in the Education tab, answering
questions about how to use the app, built on the existing Anthropic integration.

### Current state

`frontend/src/Education.jsx` is a placeholder ("Coming soon"), reachable from the nav
with no role restriction — every role sees it. `app/services/ai_content.py` is the
existing Anthropic client, but it's single-turn only: `generate_text(prompt,
max_tokens)` hardcodes one user message with no `system` field and no message history —
it was built for one-shot drafting (Cover Note, message text, report summary), not a
back-and-forth conversation. The handbook (`frontend/src/handbookData.js`, Section 13)
already carries accurate, verified, role-aware content about every screen in the app —
built for a human to read, but exactly the reference material an assistant needs to
answer correctly instead of guessing.

### Proposed spec

1. **A small, additive extension to `ai_content.py`**: `generate_chat_reply(system,
   messages, max_tokens=600)`, alongside the existing `generate_text` (not replacing
   it — Cover Note/message-draft/report-summary keep using the single-turn function
   unchanged). Anthropic's Messages API already accepts a `system` field and a real
   `messages` array; today's client just doesn't expose them. Same `AiContentError`/
   fail-fast-when-unconfigured discipline as the rest of the module.

2. **`POST /education/ask`** — open to every role (`Depends(get_current_user)`, no
   `require_roles`, matching Education's own nav visibility today). Request:
   `{ question, context, history }`. `context` is the role-appropriate slice of the
   handbook the frontend already has loaded (`FULL_HANDBOOK`, `FAQ`, always;
   `ESTIMATOR_GUIDE` for sales/pm; `DIRECTOR_ADMIN_GUIDE` only when `role === "director"`
   — the exact same conditional Help.jsx's own tab visibility already uses, so the
   assistant can never surface Director-only material to another role even by mistake).
   `history` is the prior turns of this conversation (kept client-side only, in React
   state — nothing persisted server-side, same as every other AI feature in this app).
   The backend builds one system prompt from `context` ("answer only from this
   reference material; if the answer isn't in it, say so rather than guessing") and
   forwards `history + [question]` as the messages array. Response: `{ answer }`.

3. **Education.jsx becomes a chat panel**: message list, text input, Send button,
   loading state, and the same 503 "AI drafting is not configured" handling every other
   AI feature already has. Every answer carries a visible, permanent disclaimer: "AI-
   generated, based on the app's own handbook — verify with a Director for anything
   affecting pricing, approvals, or compliance." Nothing here is ever auto-sent, auto-
   saved, or treated as a decision — it's informational only, closer to a live help
   desk than to Cover Note/message drafting (which produce a document a human later
   saves). No "human reviews before it's used" step is needed here specifically
   *because* there's nothing downstream to review — the answer is the whole interaction.

4. **No live app data, ever.** The assistant answers from the static handbook text
   only — never queries a real project, Cost Sheet, or Rate Sheet, and never gets tool
   access to the database. This keeps it squarely an informational/how-to assistant,
   not an agent that can see or act on real business data — a materially different
   (and materially riskier) feature that this spec deliberately does not propose.

**Acceptance criteria:** every role can open Education and ask a question in plain
language and get an answer grounded in the actual handbook content (not invented); a
Sales/PM user never receives Director-only guidance, even by asking directly for it; a
follow-up question in the same session uses the earlier turns as context; the assistant
states it doesn't know rather than guessing when asked something outside the handbook's
scope; an unconfigured API key fails fast with the same 503 pattern as every other AI
feature, never a hang.

### Open decisions — need Director input before implementation

1. **Multi-turn chat vs. single Q&A each time.** This spec proposes real multi-turn
   (the small `generate_chat_reply` extension above) since the UX cost of "ask one
   thing, lose all context, ask the next thing as if it were the first" is real for an
   assistant, and the engineering cost is small. Confirm, or ask for single-shot Q&A
   instead (skips the `ai_content.py` extension entirely — `generate_text` as-is would
   do).
2. **Scope of "live data."** Proposed: strictly informational, no live app data, no
   database tool access (see point 4 above) — confirm, or flag if some bounded live
   lookup (e.g. "what's my Rate Sheet status for X") is actually wanted. That would be
   a different, larger, and more carefully access-controlled feature, not a small
   addition to this one.
3. **Where it lives.** Proposed: Education tab only for this wave. The Help screen
   already has all the same handbook content loaded and could get the same chat panel
   trivially later — flagging in case the Director wants both now rather than as a
   follow-on.

---

## Approval

Amendment 15 (Education tab AI assistant, multi-turn, handbook-grounded, no live data):
☑ Approved — "approve the Education assistant spec" (18 September 2026)

Decision 1 (multi-turn chat via the new `generate_chat_reply` extension): ☑ Resolved as
proposed.
Decision 2 (no live app data / no database tool access this wave): ☑ Resolved as
proposed.
Decision 3 (Education tab only for this wave, Help-screen integration deferred): ☑
Resolved as proposed.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 18 September 2026
