"""Amendment 8 (Section 8): receives wa-gateway's outbound webhooks.

Reconciliation only, not the primary status signal -- POST /messages
already marks a WhatsApp send SENT/FAILED synchronously from wa-gateway's
own /sendText or /sendMedia response. This just confirms it once Baileys'
own message sync fires `message.sent` a moment later, matching an
inbound event to a Message row by provider_message_id. An unmatched event
(a message.sent from a conversation this app never initiated, or one that
already failed before wa-gateway returned an id) is ignored, not an
error -- wa-gateway's webhook otherwise sees every event on the instance,
most of which have nothing to do with this app."""

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.message import Message, MessageStatus

wa_gateway_webhook_router = APIRouter(prefix="/integrations/wa-gateway", tags=["integrations"])


@wa_gateway_webhook_router.post("/webhook", status_code=200)
async def receive_wa_gateway_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_webhook_secret: str | None = Header(default=None),
):
    if not settings.wa_gateway_webhook_secret or x_webhook_secret != settings.wa_gateway_webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid or missing webhook secret")

    payload = await request.json()
    if payload.get("event") != "message.sent":
        return {"ok": True}  # not something this endpoint reconciles

    msg_id = (payload.get("data") or {}).get("msgId")
    if not msg_id:
        return {"ok": True}

    message = db.query(Message).filter(Message.provider_message_id == msg_id).first()
    if message is not None and message.status != MessageStatus.SENT:
        message.status = MessageStatus.SENT
        db.commit()
    return {"ok": True}
