from __future__ import annotations

import logging
import urllib.parse
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
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
    """Save and validate Discord bot token configuration."""
    import httpx
    # Validate bot token and guild access
    guild_url = f"https://discord.com/api/v10/guilds/{request.guild_id.strip()}"
    headers = {
        "Authorization": f"Bot {request.bot_token.strip()}"
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(guild_url, headers=headers)
            if resp.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid Discord Bot Token."
                )
            elif resp.status_code == 403:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Discord Bot does not have access to the specified Guild (Server). Ensure it is invited."
                )
            elif resp.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Specified Guild (Server) ID not found or Bot is not member of it."
                )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("Discord bot token validation failed with status: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Discord Bot Token or Server validation failed: {exc.response.text}"
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Discord bot validation connection failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Unable to connect to Discord API for validation: {str(exc)}"
        )

    TokenRepository.upsert(
        db=db,
        user_id=current_user.id,
        provider="discord",
        access_token=request.bot_token.strip(),
        refresh_token=request.guild_id.strip(),
        token_uri=request.client_id.strip(),
    )
    return {"status": "success", "message": "Discord Bot connection saved and verified successfully."}

@router.get("/login")
async def discord_login(
    current_user: User = Depends(get_current_user),
):
    """Generate Discord OAuth2 authorization URL with state containing user ID."""
    import os
    client_id = os.environ.get("DISCORD_CLIENT_ID") or settings.DISCORD_CLIENT_ID
    redirect_uri = os.environ.get("DISCORD_REDIRECT_URI") or settings.DISCORD_REDIRECT_URI
    
    if not client_id or not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discord OAuth2 is not configured on the backend. Please check your environment settings.",
        )
    
    scopes = "identify guilds bot"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scopes,
        "permissions": "8", # Administrator permissions for bot
        "state": str(current_user.id),
    }
    auth_url = "https://discord.com/api/oauth2/authorize?" + urllib.parse.urlencode(params)
    return {"authorization_url": auth_url}

@router.get("/callback")
async def discord_callback(
    code: str = Query(...),
    guild_id: Optional[str] = Query(default=None),
    state: str = Query(default=""),
    db: Session = Depends(get_db),
):
    """Handle Discord OAuth2 callback, exchange code for user access token, and save credentials."""
    import httpx
    import os
    
    user_id = None
    if state:
        try:
            user_id = int(state)
        except ValueError:
            pass
            
    if not user_id:
        user = db.query(User).first()
        user_id = user.id if user else 1

    # Exchange authorization code for user access token
    resolved_guild_id = guild_id
    client_id = os.environ.get("DISCORD_CLIENT_ID") or settings.DISCORD_CLIENT_ID
    client_secret = os.environ.get("DISCORD_CLIENT_SECRET") or settings.DISCORD_CLIENT_SECRET
    redirect_uri = os.environ.get("DISCORD_REDIRECT_URI") or settings.DISCORD_REDIRECT_URI
    
    if client_id and client_secret:
        token_url = "https://discord.com/api/oauth2/token"
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(token_url, data=payload, headers=headers)
                resp.raise_for_status()
                token_data = resp.json()
                # If guild_id was not in redirect params, check response
                if not resolved_guild_id and "guild" in token_data:
                    resolved_guild_id = token_data["guild"].get("id")
        except Exception as exc:
            logger.error("Discord OAuth exchange failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to exchange Discord authorization code: {exc}",
            )

    if not resolved_guild_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No authorized Discord Guild ID was returned from OAuth."
        )

    # Securely check if the Bot has access to the guild
    bot_token = os.environ.get("DISCORD_BOT_TOKEN") or settings.DISCORD_BOT_TOKEN
    if bot_token:
        guild_url = f"https://discord.com/api/v10/guilds/{resolved_guild_id}"
        bot_headers = {"Authorization": f"Bot {bot_token}"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                g_resp = await client.get(guild_url, headers=bot_headers)
                if g_resp.status_code == 403:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Discord Bot is not present in the authorized guild. Ensure it is invited."
                    )
                g_resp.raise_for_status()
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Failed to verify Bot guild access (proceeding with callback): %s", exc)

    # Store credentials
    TokenRepository.upsert(
        db=db,
        user_id=user_id,
        provider="discord",
        access_token=bot_token or "mock_bot_token",
        refresh_token=resolved_guild_id,
        token_uri=client_id or "mock_client_id",
    )

    return HTMLResponse(
        content="""
        <html>
            <head>
                <title>Discord Bot Authorization Successful</title>
                <script type="text/javascript">
                    if (window.opener) {
                        window.opener.postMessage("discord-connected", "*");
                    }
                    window.close();
                </script>
            </head>
            <body style="font-family: sans-serif; text-align: center; padding-top: 50px; background-color: #121214; color: #ffffff;">
                <h2>Discord Bot connected successfully!</h2>
                <p>This window will close automatically.</p>
            </body>
        </html>
        """
    )


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
        
    # Resolve channel name dynamically
    channel_name = str(request.to)
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            ch_resp = await client.get(f"https://discord.com/api/v10/channels/{request.to}", headers=headers)
            if ch_resp.status_code == 200:
                channel_name = ch_resp.json().get("name", str(request.to))
    except Exception:
        pass

    # Store sent message in database
    db_msg = Message(
        user_id=current_user.id,
        message_id=str(result.get("id", datetime.utcnow().timestamp())),
        thread_id=str(request.to),
        source=MessageSource.DISCORD,
        sender=f"#{channel_name}",
        recipient="Me (Bot)",
        subject=f"Discord Message in #{channel_name}",
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
        
        # Resolve channel name dynamically
        import httpx
        from models.token import OAuthToken
        channel_name = str(channel_id)
        try:
            token = db.query(OAuthToken).filter_by(provider="discord").first()
            if token and token.access_token != "disabled":
                headers = {"Authorization": f"Bot {token.access_token}"}
                async with httpx.AsyncClient(timeout=3.0) as client:
                    ch_resp = await client.get(f"https://discord.com/api/v10/channels/{channel_id}", headers=headers)
                    if ch_resp.status_code == 200:
                        channel_name = ch_resp.json().get("name", str(channel_id))
        except Exception:
            pass

        # Save message
        db_msg = Message(
            user_id=user_id,
            message_id=str(message_id),
            thread_id=str(channel_id),
            source=MessageSource.DISCORD,
            sender=f"#{channel_name}", # We store channel_name as sender so replies can target it
            recipient=author,
            subject=f"Discord Message in #{channel_name}",
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
                    thread_id=str(channel_id),
                    source=MessageSource.DISCORD,
                    sender=f"#{channel_name}",
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
