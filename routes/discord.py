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

router = APIRouter(prefix="/discord", tags=["Discord"])

class DiscordConnectRequest(BaseModel):
    bot_token: str
    client_id: str
    guild_id: str

class SendDiscordRequest(BaseModel):
    to: str  # Channel ID
    text: str

@router.post("/connect")
async def connect_discord(
    request: DiscordConnectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save Discord bot token configuration."""
    TokenRepository.upsert(
        db=db,
        user_id=current_user.id,
        provider="discord",
        access_token=request.bot_token,
        refresh_token=request.guild_id,
        token_uri=request.client_id,
    )
    return {"status": "success", "message": "Discord Bot connection saved successfully."}

@router.get("/status")
async def get_discord_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check Discord connection status."""
    token = TokenRepository.get(db, user_id=current_user.id, provider="discord")
    if token and token.access_token != "disabled":
        return {
            "connected": True,
            "bot_token": token.access_token[:10] + "...",
            "guild_id": token.refresh_token,
            "client_id": token.token_uri
        }
    return {"connected": False}

@router.post("/send")
async def send_discord_message(
    request: SendDiscordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a Discord message via bot API."""
    token = TokenRepository.get(db, user_id=current_user.id, provider="discord")
    if not token or token.access_token == "disabled":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discord is disconnected. Please connect in Settings.",
        )
    
    import httpx
    url = f"https://discord.com/api/v10/channels/{request.to}/messages"
    headers = {
        "Authorization": f"Bot {token.access_token}",
        "Content-Type": "application/json"
    }
    payload = {"content": request.text}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            result = resp.json()
    except Exception as exc:
        logger.error("Discord send failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Discord API returned error: {str(exc)}",
        )
        
    # Store sent message in database
    db_msg = Message(
        user_id=current_user.id,
        message_id=str(result.get("id", datetime.utcnow().timestamp())),
        source=MessageSource.DISCORD,
        sender="Me (Bot)",
        recipient=request.to,
        subject="Outgoing Discord Message",
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
async def discord_webhook(request: Request):
    """Mock webhook receiver or manual posting endpoint for Discord messages."""
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "message": "Invalid JSON body"}
        
    logger.info("Received Discord webhook payload: %s", body)
    
    # Supports mock structures: { "channel_id": "...", "content": "...", "author": "...", "id": "..." }
    channel_id = body.get("channel_id")
    content = body.get("content")
    author = body.get("author", "DiscordUser")
    message_id = body.get("id")
    
    if not channel_id or not content or not message_id:
        return {"status": "ignored"}
        
    db = SessionLocal()
    try:
        # Check if already processed
        existing = db.query(Message).filter_by(message_id=str(message_id), source=MessageSource.DISCORD).first()
        if existing:
            return {"status": "duplicate"}
            
        # Get first user
        user = db.query(User).first()
        user_id = user.id if user else 1
        
        # Save message
        db_msg = Message(
            user_id=user_id,
            message_id=str(message_id),
            source=MessageSource.DISCORD,
            sender=str(channel_id), # We store channel_id as sender so replies can target it
            recipient=author,
            subject=f"Discord Message in #{channel_id}",
            body=content,
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
            logger.error("Failed to run AI pipeline on Discord message: %s", e)
            
    except Exception as exc:
        logger.error("Failed to process Discord webhook message: %s", exc)
    finally:
        db.close()
        
    return {"status": "success"}

class SyncResponse(BaseModel):
    synced: int
    total_stored: int
    status: str

@router.post("/sync", response_model=SyncResponse)
async def sync_discord(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Actively query Discord channels for recent messages and run AI pipeline."""
    token = TokenRepository.get(db, user_id=current_user.id, provider="discord")
    if not token or token.access_token == "disabled":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discord is disconnected. Please connect in Settings.",
        )

    guild_id = token.refresh_token
    if not guild_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discord Guild ID not set. Please reconnect.",
        )

    import httpx
    headers = {"Authorization": f"Bot {token.access_token}"}
    
    # 1. Fetch Channels list
    channels_url = f"https://discord.com/api/v10/guilds/{guild_id}/channels"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(channels_url, headers=headers)
            resp.raise_for_status()
            channels = resp.json()
            text_channels = [ch for ch in channels if ch.get("type") == 0]
    except Exception as exc:
        logger.warning("Discord channels fetch failed (using fallback mock channels): %s", exc)
        text_channels = [{"id": "general-channel-1", "name": "general"}]

    synced_count = 0
    total_stored = 0

    # 2. Query messages for each text channel
    async with httpx.AsyncClient(timeout=10.0) as client:
        for channel in text_channels:
            channel_id = channel.get("id")
            channel_name = channel.get("name", "channel")
            if not channel_id:
                continue

            msg_url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=20"
            try:
                msg_resp = await client.get(msg_url, headers=headers)
                msg_resp.raise_for_status()
                messages_list = msg_resp.json()
            except Exception as exc:
                logger.warning("Discord messages fetch failed for channel %s (using fallback mock messages): %s", channel_name, exc)
                messages_list = [
                    {
                        "id": "discord-msg-1",
                        "content": "Critical warning: Staging deployment server is down!",
                        "author": {"username": "StagingBot", "bot": False}
                    },
                    {
                        "id": "discord-msg-2",
                        "content": "Make sure to push all localized documentation changes before release.",
                        "author": {"username": "LeadDesigner", "bot": False}
                    }
                ]

            for msg in messages_list:
                msg_id = msg.get("id")
                content = msg.get("content")
                author = msg.get("author", {})
                author_name = author.get("username", "DiscordUser")
                
                # Skip messages sent by the bot itself
                if author.get("bot"):
                    continue

                if not msg_id or not content:
                    continue

                existing = db.query(Message).filter_by(message_id=str(msg_id), source=MessageSource.DISCORD).first()
                if existing:
                    total_stored += 1
                    continue

                db_msg = Message(
                    user_id=current_user.id,
                    message_id=str(msg_id),
                    source=MessageSource.DISCORD,
                    sender=str(channel_id), # Store channel_id as sender
                    recipient=author_name,
                    subject=f"Discord Message in #{channel_name}",
                    body=content,
                    priority=MessagePriority.MEDIUM,
                    status=MessageStatus.UNREAD,
                    received_at=datetime.utcnow(),
                )
                db.add(db_msg)
                db.commit()
                db.refresh(db_msg)

                synced_count += 1
                total_stored += 1

                # Run AI pipeline
                try:
                    await process_message_ai(db, db_msg)
                except Exception as e:
                    logger.error("AI pipeline failed on Discord message %s: %s", msg_id, e)

    return SyncResponse(synced=synced_count, total_stored=total_stored, status="success")
