"""Amendment 8 (Section 8): thin client for the Telegram Bot API.

Telegram has no separate "delivery status" webhook for outbound bot
messages -- the sendMessage/sendDocument HTTP call is itself synchronous:
a 200 `{"ok": true, "result": {"message_id": ...}}` IS the delivery
confirmation, an error response is a real failure. So unlike wa-gateway,
there's no reconciliation webhook needed on the Telegram side -- status
is decided entirely from this call's own response.
"""

import httpx

from app.config import settings


class TelegramError(Exception):
    """A Telegram send could not be completed -- not configured, an
    invalid/unreachable chat_id (the bot can only message a chat that
    has messaged it first), or any other API error. The caller (app/
    api/messages.py) catches this and records Message.status=FAILED."""


def _require_configured() -> None:
    if not settings.telegram_bot_token:
        raise TelegramError("Telegram is not configured (TELEGRAM_BOT_TOKEN unset)")


def _api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"


def _call(method: str, **kwargs) -> dict:
    try:
        res = httpx.post(_api_url(method), timeout=15, **kwargs)
    except httpx.HTTPError as exc:
        raise TelegramError(f"Telegram request failed: {exc}") from exc
    body = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
    if res.status_code != 200 or not body.get("ok"):
        raise TelegramError(f"Telegram API error ({res.status_code}): {body.get('description', res.text[:200])}")
    return body["result"]


def send_text(chat_id: str, text: str) -> str | None:
    """Returns Telegram's own message_id (used as Message.provider_message_id)."""
    _require_configured()
    result = _call("sendMessage", json={"chat_id": chat_id, "text": text})
    return str(result["message_id"]) if "message_id" in result else None


def send_document(chat_id: str, content: bytes, filename: str, caption: str | None = None) -> str | None:
    """content is the raw file bytes (not base64 -- Telegram's Bot API
    takes multipart file uploads directly, unlike wa-gateway)."""
    _require_configured()
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption
    result = _call("sendDocument", data=data, files={"document": (filename, content, "application/pdf")})
    return str(result["message_id"]) if "message_id" in result else None
