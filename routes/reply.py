"""Reply routes — draft generation, improvement, and regeneration."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models.user import User
from repositories.message_repo import MessageRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reply", tags=["Reply"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ReplyRequest(BaseModel):
    recipient_name: str
    email_content: str
    context: Optional[str] = None
    tone: str = "professional"
    language: str = "English"


class ImproveRequest(BaseModel):
    original_email: str
    reply_draft: str


class ReplyResponse(BaseModel):
    reply: str
    tone: Optional[str] = None
    language: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/generate", response_model=ReplyResponse)
async def generate_reply(
    request: ReplyRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate an AI-drafted reply to an email."""
    from agents.reply_agent import ReplyAgent

    try:
        result = await ReplyAgent().generate_reply(
            recipient_name=request.recipient_name,
            email_content=request.email_content,
            context=request.context,
            tone=request.tone,
            language=request.language,
        )
    except Exception as exc:
        logger.error("Reply generation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    reply_text = result.get("reply", "")
    if not reply_text:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM returned an empty reply.",
        )
    return ReplyResponse(reply=reply_text, tone=result.get("tone"), language=result.get("language"))


@router.post("/improve", response_model=ReplyResponse)
async def improve_reply(
    request: ImproveRequest,
    current_user: User = Depends(get_current_user),
):
    """Improve an existing draft reply."""
    from agents.reply_agent import ReplyAgent

    try:
        result = await ReplyAgent().improve_reply(
            original_email=request.original_email,
            reply_draft=request.reply_draft,
        )
    except Exception as exc:
        logger.error("Reply improvement failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return ReplyResponse(reply=result.get("reply", ""))


@router.post("/regenerate", response_model=ReplyResponse)
async def regenerate_reply(
    request: ReplyRequest,
    current_user: User = Depends(get_current_user),
):
    """Regenerate a reply with higher temperature for variety."""
    from agents.reply_agent import ReplyAgent

    try:
        result = await ReplyAgent().regenerate_reply(
            recipient_name=request.recipient_name,
            email_content=request.email_content,
            context=request.context,
            tone=request.tone,
            language=request.language,
        )
    except Exception as exc:
        logger.error("Reply regeneration failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return ReplyResponse(reply=result.get("reply", ""), tone=result.get("tone"), language=result.get("language"))


@router.post("/message/{message_id}", response_model=ReplyResponse)
async def reply_to_stored_message(
    message_id: int,
    tone: str = "professional",
    language: str = "English",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a reply for a stored message and save it."""
    from agents.reply_agent import ReplyAgent

    msg = MessageRepository.get_by_id(db, message_id, current_user.id)
    if msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")

    try:
        result = await ReplyAgent().generate_reply(
            recipient_name=msg.sender,
            email_content=msg.to_context_string(),
            tone=tone,
            language=language,
        )
    except Exception as exc:
        logger.error("Reply for message %d failed: %s", message_id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    reply_text = result.get("reply", "")
    if reply_text:
        msg.update_from_ai(suggested_reply=reply_text, requires_reply=True)
        db.commit()

    return ReplyResponse(reply=reply_text, tone=tone, language=language)


class ApproveReplyRequest(BaseModel):
    reply_text: str


@router.post("/message/{message_id}/approve")
async def approve_reply(
    message_id: int,
    request: ApproveReplyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve and dispatch the reply draft to the original platform."""
    msg = MessageRepository.get_by_id(db, message_id, current_user.id)
    if msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")

    from models.message import MessageSource
    from config import settings

    result = None
    try:
        if msg.source == MessageSource.GMAIL:
            from services.oauth import get_credentials
            from agents.gmail_agent import GmailAgent
            
            creds = get_credentials(current_user.id, db)
            if creds is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Google account not connected.",
                )
            result = GmailAgent().send_reply(creds, msg, request.reply_text)

        elif msg.source == MessageSource.WHATSAPP:
            from agents.whatsapp_agent import WhatsAppAgent
            from repositories.token_repo import TokenRepository
            
            token = TokenRepository.get(db, user_id=current_user.id, provider="whatsapp")
            if token and token.access_token != "disabled":
                api_token = token.access_token
                phone_number_id = token.refresh_token
            else:
                if token and token.access_token == "disabled":
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="WhatsApp is disconnected. Please connect in settings.",
                    )
                if not settings.WHATSAPP_API_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="WhatsApp is not configured. Set WHATSAPP_API_TOKEN and WHATSAPP_PHONE_NUMBER_ID, or connect via settings.",
                    )
                api_token = settings.WHATSAPP_API_TOKEN
                phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID

            result = await WhatsAppAgent().send_message(
                api_token=api_token,
                phone_number_id=phone_number_id,
                to=msg.sender,
                text=request.reply_text,
            )

        elif msg.source == MessageSource.TWITTER:
            from agents.twitter_agent import TwitterAgent
            
            if not all([
                settings.TWITTER_API_KEY,
                settings.TWITTER_API_SECRET,
                settings.TWITTER_ACCESS_TOKEN,
                settings.TWITTER_ACCESS_SECRET,
            ]):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Twitter/X write credentials not configured.",
                )
            result = await TwitterAgent().post_reply(
                api_key=settings.TWITTER_API_KEY,
                api_secret=settings.TWITTER_API_SECRET,
                access_token=settings.TWITTER_ACCESS_TOKEN,
                access_secret=settings.TWITTER_ACCESS_SECRET,
                tweet_id=msg.message_id,
                text=request.reply_text,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Replying is not supported for message source '{msg.source.value}'",
            )
    except Exception as exc:
        logger.error("Approve and send reply failed for message %d: %s", message_id, exc)
        if msg.source == MessageSource.GMAIL:
            from services.oauth import handle_google_error
            handle_google_error(exc)
        elif msg.source == MessageSource.WHATSAPP:
            from routes.whatsapp import handle_whatsapp_error
            handle_whatsapp_error(exc)
        else:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    # Mark as replied and update the reply body in db
    msg.suggested_reply = request.reply_text
    msg.mark_as_replied()
    db.commit()

    return {"status": "sent", "source": msg.source.value}
