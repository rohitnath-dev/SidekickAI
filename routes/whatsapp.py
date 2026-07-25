"""WhatsApp routes — Meta Cloud API integration."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from config import settings
from dependencies import get_current_user
from models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SendMessageRequest(BaseModel):
    to: str          # E.164 phone number e.g. "15551234567"
    text: str


class ReplyRequest(BaseModel):
    sender_name: str
    message_content: str
    to: str
    context: Optional[str] = None
    auto_send: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_whatsapp():
    if not settings.WHATSAPP_API_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp is not configured. Set WHATSAPP_API_TOKEN and WHATSAPP_PHONE_NUMBER_ID.",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
):
    """Webhook verification endpoint for Meta (no auth required)."""
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verified.")
        return hub_challenge
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Webhook verification failed.")


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def receive_webhook(request: Request):
    """Receive incoming WhatsApp messages from Meta (no auth required)."""
    from agents.whatsapp_agent import WhatsAppAgent

    try:
        body = await request.json()
    except Exception:
        return {"status": "ok"}

    try:
        messages = await WhatsAppAgent().get_webhook_messages(body)
        for msg in messages:
            logger.info(
                "WhatsApp message from %s: %s",
                msg.get("from"),
                msg.get("text", "")[:80],
            )
    except Exception as exc:
        logger.error("WhatsApp webhook processing error: %s", exc)

    # Always return 200 to Meta
    return {"status": "ok"}


@router.post("/send")
async def send_message(
    request: SendMessageRequest,
    current_user: User = Depends(get_current_user),
):
    """Send a WhatsApp message."""
    from agents.whatsapp_agent import WhatsAppAgent

    _require_whatsapp()
    try:
        result = await WhatsAppAgent().send_message(
            api_token=settings.WHATSAPP_API_TOKEN,
            phone_number_id=settings.WHATSAPP_PHONE_NUMBER_ID,
            to=request.to,
            text=request.text,
        )
    except Exception as exc:
        logger.error("WhatsApp send failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    msg_id = None
    if isinstance(result, dict):
        msgs = result.get("messages", [])
        if msgs:
            msg_id = msgs[0].get("id")

    return {"status": "sent", "message_id": msg_id}


@router.post("/reply/generate")
async def generate_reply(
    request: ReplyRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate an AI reply to a WhatsApp message."""
    from agents.whatsapp_agent import WhatsAppAgent

    try:
        reply_text = await WhatsAppAgent().generate_reply_text(
            sender_name=request.sender_name,
            message_content=request.message_content,
            context=request.context,
        )
    except Exception as exc:
        logger.error("WhatsApp reply generation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return {"reply_text": reply_text}


@router.post("/reply/send")
async def send_reply(
    request: ReplyRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate and send an AI reply to a WhatsApp message."""
    from agents.whatsapp_agent import WhatsAppAgent

    _require_whatsapp()
    agent = WhatsAppAgent()
    try:
        reply_text = await agent.generate_reply_text(
            sender_name=request.sender_name,
            message_content=request.message_content,
            context=request.context,
        )
        result = await agent.send_message(
            api_token=settings.WHATSAPP_API_TOKEN,
            phone_number_id=settings.WHATSAPP_PHONE_NUMBER_ID,
            to=request.to,
            text=reply_text,
        )
    except Exception as exc:
        logger.error("WhatsApp reply send failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    msg_id = None
    if isinstance(result, dict):
        msgs = result.get("messages", [])
        if msgs:
            msg_id = msgs[0].get("id")

    return {"status": "sent", "reply_text": reply_text, "message_id": msg_id}
