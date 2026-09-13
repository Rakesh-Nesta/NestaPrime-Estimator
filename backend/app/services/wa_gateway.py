"""Amendment 8 (Section 8): thin client for the company's self-hosted
wa-gateway (Baileys/WhatsApp Web protocol -- not a paid BSP, per the
Director's decision to investigate wa-gateway before any paid provider).

Kept deliberately small: two calls (sendText, sendMedia) plus the shared
request helper. No retry/queueing here -- a send that fails surfaces as
Message.status=FAILED immediately, same synchronous-request style as the
rest of this app; a PM/Sales can just try again from the Messages panel.
"""

import httpx

from app.config import settings


class WaGatewayError(Exception):
    """A WhatsApp send could not be completed -- not configured, the
    instance isn't connected (409, e.g. no paired number), or any other
    non-2xx response. The caller (app/api/messages.py) catches this and
    records Message.status=FAILED rather than letting it 500."""


def _require_configured() -> None:
    if not settings.wa_gateway_base_url or not settings.wa_gateway_api_key:
        raise WaGatewayError("wa-gateway is not configured (WA_GATEWAY_BASE_URL/WA_GATEWAY_API_KEY unset)")


def _headers() -> dict:
    return {"X-API-Key": settings.wa_gateway_api_key}


def send_text(to: str, text: str, instance_id: str = "default") -> str | None:
    """Returns wa-gateway's own message id when available (used as
    Message.provider_message_id), or None if the response didn't carry
    one. Raises WaGatewayError on any failure."""
    _require_configured()
    try:
        res = httpx.post(
            f"{settings.wa_gateway_base_url}/sendText",
            json={"instanceId": instance_id, "to": to, "text": text},
            headers=_headers(),
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise WaGatewayError(f"wa-gateway request failed: {exc}") from exc
    if res.status_code != 200:
        raise WaGatewayError(f"wa-gateway /sendText returned {res.status_code}: {res.text[:200]}")
    return _extract_message_id(res)


def send_media(
    to: str, document_type: str, base64_content: str, filename: str, mimetype: str,
    caption: str | None = None, instance_id: str = "default",
) -> str | None:
    """document_type is wa-gateway's own enum: image/video/audio/document
    -- always "document" for the PDFs this app sends. base64_content is
    the raw file content, base64-encoded, with no data: URI prefix
    (wa-gateway's own `base64` field, matching its `url`-or-`base64`
    either/or design -- base64 avoids needing our server reachable by
    wa-gateway over a public URL)."""
    _require_configured()
    payload = {
        "instanceId": instance_id, "to": to, "type": document_type,
        "base64": base64_content, "fileName": filename, "mimetype": mimetype,
    }
    if caption:
        payload["caption"] = caption
    try:
        res = httpx.post(
            f"{settings.wa_gateway_base_url}/sendMedia", json=payload, headers=_headers(), timeout=30,
        )
    except httpx.HTTPError as exc:
        raise WaGatewayError(f"wa-gateway request failed: {exc}") from exc
    if res.status_code != 200:
        raise WaGatewayError(f"wa-gateway /sendMedia returned {res.status_code}: {res.text[:200]}")
    return _extract_message_id(res)


def _extract_message_id(res: httpx.Response) -> str | None:
    try:
        body = res.json()
    except ValueError:
        return None
    # wa-gateway's own reply shape isn't guaranteed to carry the message
    # id inline (Baileys reports it asynchronously via the message.sent
    # webhook -- see app/api/wa_gateway_webhook.py) -- take it if present,
    # leave it for the webhook to fill in via provider_message_id
    # otherwise.
    return body.get("id") or body.get("messageId") or body.get("key", {}).get("id")
