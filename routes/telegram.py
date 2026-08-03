from __future__ import annotations

import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from dependencies import get_current_user
from models.user import User
from models.message import Message, MessageSource, MessagePriority, MessageStatus
from repositories.token_repo import TokenRepository
from services.ai_pipeline import process_message_ai

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["Telegram"])

class TelegramConnectRequest(BaseModel):
    bot_token: str

class SendTelegramRequest(BaseModel):
    to: str  # Chat ID
    text: str

@router.post("/connect")
async def connect_telegram(
    request: TelegramConnectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save Telegram bot token configuration."""
    TokenRepository.upsert(
        db=db,
        user_id=current_user.id,
        provider="telegram",
        access_token=request.bot_token,
        refresh_token="",
        token_uri="",
    )
    return {"status": "success", "message": "Telegram Bot Token saved successfully."}

@router.get("/status")
async def get_telegram_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check Telegram connection status."""
    token = TokenRepository.get(db, user_id=current_user.id, provider="telegram")
    if token and token.access_token != "disabled":
        return {"connected": True, "bot_token": token.access_token[:10] + "..."}
    return {"connected": False}

@router.post("/send")
async def send_telegram_message(
    request: SendTelegramRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a Telegram message via bot API."""
    token = TokenRepository.get(db, user_id=current_user.id, provider="telegram")
    if not token or token.access_token == "disabled":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram is disconnected. Please connect in Settings.",
        )
    
    import httpx
    url = f"https://api.telegram.org/bot{token.access_token}/sendMessage"
    payload = {"chat_id": request.to, "text": request.text}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            result = resp.json()
    except Exception as exc:
        logger.error("Telegram send failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Telegram API returned error: {str(exc)}",
        )
        
    # Store sent message in database
    db_msg = Message(
        user_id=current_user.id,
        message_id=str(result.get("result", {}).get("message_id", datetime.utcnow().timestamp())),
        source=MessageSource.TELEGRAM,
        sender="Me (Bot)",
        recipient=request.to,
        subject="Outgoing Telegram Message",
        body=request.text,
        priority=MessagePriority.MEDIUM,
        status=MessageStatus.READ,
        received_at=datetime.utcnow(),
        is_processed=True,
    )
    db.add(db_msg)
    db.commit()
    db.refresh(db_msg)
    
    return {"status": "success", "result": result}

@router.post("/webhook")
async def telegram_webhook(request: Request):
    """Receive incoming messages from Telegram Bot API webhook."""
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "message": "Invalid JSON body"}
        
    logger.info("Received Telegram webhook payload: %s", body)
    
    # Extract message from payload
    message = body.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text")
    message_id = message.get("message_id")
    
    if not chat_id or not text or not message_id:
        return {"status": "ignored"}
        
    db = SessionLocal()
    try:
        # Check if already processed
        existing = db.query(Message).filter_by(message_id=str(message_id), source=MessageSource.TELEGRAM).first()
        if existing:
            return {"status": "duplicate"}
            
        # Get first user
        user = db.query(User).first()
        user_id = user.id if user else 1
        
        # Save message
        sender_name = chat.get("username") or chat.get("first_name") or str(chat_id)
        db_msg = Message(
            user_id=user_id,
            message_id=str(message_id),
            source=MessageSource.TELEGRAM,
            sender=str(chat_id), # We store chat_id as sender so replies can target it
            recipient=sender_name,
            subject=f"Telegram Chat from {sender_name}",
            body=text,
            priority=MessagePriority.MEDIUM,
            status=MessageStatus.UNREAD,
            received_at=datetime.utcnow(),
        )
        db.add(db_msg)
        db.commit()
        db.refresh(db_msg)
        
        # Run AI priority pipeline
        try:
            await process_message_ai(db, db_msg)
        except Exception as e:
            logger.error("Failed to run AI pipeline on Telegram message: %s", e)
            
    except Exception as exc:
        logger.error("Failed to process Telegram webhook message: %s", exc)
    finally:
        db.close()
        
    return {"status": "success"}
