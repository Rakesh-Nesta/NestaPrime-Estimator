"""Amendment 13 (Section 12): thin client for Claude (Anthropic Messages
API), used to draft quotation cover notes, client message text, and
report summaries. Every caller treats the result as a *draft* -- a human
reviews/edits it before anything is saved or sent; this module never
writes to the database or sends anything itself.

Kept deliberately small, same shape as app/services/wa_gateway.py: one
call, no retry/queueing, no SDK dependency (httpx, already a project
dependency, same as wa_gateway/telegram).
"""

import httpx

from app.config import settings

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"


class AiContentError(Exception):
    """A draft could not be generated -- not configured, or any other
    non-2xx response. Callers treat this the same way wa_gateway/telegram
    failures are treated: fail visibly to the person who clicked
    "Draft with AI", never a hang, never a 500."""


def _require_configured() -> None:
    if not settings.anthropic_api_key:
        raise AiContentError("AI drafting is not configured (ANTHROPIC_API_KEY unset)")


def generate_text(prompt: str, max_tokens: int = 400) -> str:
    """Returns Claude's plain-text reply to a single-turn prompt. Raises
    AiContentError on any failure -- callers pass that through to the
    person who requested the draft rather than letting it 500."""
    _require_configured()
    try:
        res = httpx.post(
            ANTHROPIC_API_URL,
            json={
                "model": settings.anthropic_model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": ANTHROPIC_API_VERSION,
                "content-type": "application/json",
            },
            timeout=30,
        )
    except httpx.HTTPError as exc:
        raise AiContentError(f"AI drafting request failed: {exc}") from exc
    if res.status_code != 200:
        raise AiContentError(f"AI drafting returned {res.status_code}: {res.text[:200]}")
    body = res.json()
    try:
        return "".join(block["text"] for block in body["content"] if block.get("type") == "text").strip()
    except (KeyError, TypeError) as exc:
        raise AiContentError(f"AI drafting returned an unexpected response shape: {body}") from exc
