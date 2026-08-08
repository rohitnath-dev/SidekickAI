"""Gmail routes — OAuth connection and message management."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user, get_optional_user
from models.user import User
from repositories.message_repo import MessageRepository
from services.oauth import (
    generate_authorization_url,
    exchange_code_for_tokens,
    get_credentials,
    revoke_credentials,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gmail", tags=["Gmail"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SyncRequest(BaseModel):
    max_results: int = 20
    unread_only: bool = False
    category: Optional[str] = "primary"


class SyncResponse(BaseModel):
    synced: int
    total_stored: int
    status: str


class MessageResponse(BaseModel):
    id: int
    message_id: str
    thread_id: Optional[str]
    source: str
    sender: str
    recipient: Optional[str]
    subject: Optional[str]
    body: str
    priority: str
    status: str
    requires_reply: bool
    summary: Optional[str]
    sentiment: Optional[str]
    category: Optional[str]
    action_items: Optional[str]
    suggested_reply: Optional[str]
    is_processed: bool
    received_at: Optional[str]
    created_at: Optional[str]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _msg_to_response(msg) -> MessageResponse:
    d = msg.to_dict()
    return MessageResponse(**{k: d.get(k) for k in MessageResponse.model_fields})


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/authorize")
async def authorize(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Generate the Google OAuth consent URL."""
    # Resolve the token to pass as OAuth state
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split(" ")
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        token = request.query_params.get("token")

    try:
        url, state = generate_authorization_url(state=token)
    except Exception as exc:
        logger.error("Failed to generate authorization URL: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not generate Google authorization URL. Check GOOGLE_CLIENT_ID/SECRET.",
        )
    return {"authorization_url": url, "state": state}


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(default=""),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Exchange the OAuth code for tokens and store them."""
    user_id = None
    if current_user:
        user_id = current_user.id
    elif state:
        # Resolve token from state
        from dependencies import decode_access_token
        user_id_str = decode_access_token(state)
        if user_id_str:
            try:
                user_id = int(user_id_str)
            except (ValueError, TypeError):
                pass

    if not user_id:
        logger.error("OAuth callback failed: User could not be identified.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User session not found. Please log in again and reconnect.",
        )

    try:
        exchange_code_for_tokens(code=code, state=state, db=db, user_id=user_id)
    except Exception as exc:
        logger.error("OAuth exchange failed for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to exchange authorization code: {exc}",
        )
    
    # Return HTML response that automatically closes the popup
    return HTMLResponse(
        content="""
        <html>
            <head>
                <title>Authentication Successful</title>
                <script type="text/javascript">
                    if (window.opener) {
                        // Notify opener/parent page if applicable
                        window.opener.postMessage("gmail-connected", "*");
                    }
                    window.close();
                </script>
            </head>
            <body style="font-family: sans-serif; text-align: center; padding-top: 50px; background-color: #121214; color: #ffffff;">
                <h2>Google account connected successfully!</h2>
                <p>This window will close automatically.</p>
            </body>
        </html>
        """
    )


@router.delete("/disconnect")
async def disconnect(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke and delete stored Google credentials."""
    revoked = revoke_credentials(current_user.id, db)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Google account connected.",
        )
    return {"status": "disconnected"}


@router.post("/sync", response_model=SyncResponse)
async def sync(
    request: SyncRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch new Gmail messages and store them in the database."""
    from agents.gmail_agent import GmailAgent

    creds = get_credentials(current_user.id, db)
    if creds is None:
        active_providers = get_active_providers(current_user.id, db)
        if active_providers:
            return SyncResponse(
                synced=0,
                total_stored=0,
                status="success",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Google account not connected. Call /gmail/authorize first.",
        )

    try:
        agent = GmailAgent()
        result = await agent.sync_messages(
            creds=creds,
            db=db,
            user_id=current_user.id,
            limit=request.max_results,
            unread_only=request.unread_only,
            category=request.category or "primary",
        )
    except Exception as exc:
        logger.error("Gmail sync failed for user %d: %s", current_user.id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gmail sync failed: {str(exc)}"
        )

    return SyncResponse(
        synced=result.get("synced", 0),
        total_stored=result.get("total_stored", 0),
        status="success",
    )

def get_active_providers(user_id: int, db: Session) -> set[str]:
    from repositories.token_repo import TokenRepository
    from config import settings
    
    tokens = TokenRepository.list_by_user(db, user_id)
    connected = {t.provider for t in tokens if t.access_token != "disabled"}
    
    # Check system default fallbacks
    if settings.TWITTER_BEARER_TOKEN and "twitter" not in connected:
        # Check if user explicitly disabled it
        disabled_token = next((t for t in tokens if t.provider == "twitter"), None)
        if not (disabled_token and disabled_token.access_token == "disabled"):
            connected.add("twitter")
            
    if settings.WHATSAPP_API_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID and "whatsapp" not in connected:
        # Check if user explicitly disabled it
        disabled_token = next((t for t in tokens if t.provider == "whatsapp"), None)
        if not (disabled_token and disabled_token.access_token == "disabled"):
            connected.add("whatsapp")
    return connected


@router.get("/messages", response_model=list[MessageResponse])
async def list_messages(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    unread_only: bool = Query(default=False),
    source: Optional[str] = Query(default=None),
    high_priority_only: bool = Query(default=False),
    category: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List stored messages for the current user."""
    active_providers = get_active_providers(current_user.id, db)
    
    # If source is specified, check if that source's provider is active
    if source:
        provider_map = {"GMAIL": "google", "TWITTER": "twitter", "WHATSAPP": "whatsapp", "LINKEDIN": "linkedin", "TELEGRAM": "telegram", "DISCORD": "discord"}
        provider = provider_map.get(source.upper())
        if not provider or provider not in active_providers:
            return []
            
    # If no active providers exist at all, return empty list immediately
    if not active_providers:
        return []

    messages = MessageRepository.list_by_user(
        db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
        source=source,
        high_priority_only=high_priority_only,
        category=category,
    )
    
    # Filter messages to only show those where source maps to an active provider
    provider_map = {"GMAIL": "google", "TWITTER": "twitter", "WHATSAPP": "whatsapp", "LINKEDIN": "linkedin", "TELEGRAM": "telegram", "DISCORD": "discord"}
    filtered_messages = []
    for m in messages:
        m_source = m.source.value.upper() if hasattr(m.source, "value") else str(m.source).upper()
        provider = provider_map.get(m_source)
        if provider in active_providers:
            filtered_messages.append(m)
            
    return [_msg_to_response(m) for m in filtered_messages]


@router.get("/messages/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single stored message by its database ID."""
    msg = MessageRepository.get_by_id(db, message_id, current_user.id)
    if msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")
    return _msg_to_response(msg)


@router.patch("/messages/{message_id}/read", response_model=MessageResponse)
async def mark_read(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a message as read."""
    msg = MessageRepository.get_by_id(db, message_id, current_user.id)
    if msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")
    msg.mark_as_read()
    db.commit()
    db.refresh(msg)
    return _msg_to_response(msg)


class StatusUpdateRequest(BaseModel):
    status: str


@router.patch("/messages/{message_id}/status", response_model=MessageResponse)
async def update_status(
    message_id: int,
    request: StatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a message's status (read, unread, replied, archived)."""
    msg = MessageRepository.get_by_id(db, message_id, current_user.id)
    if msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")

    from models.message import MessageStatus
    try:
        status_enum = MessageStatus(request.status.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status '{request.status}'. Allowed: read, unread, replied, archived."
        )

    msg.status = status_enum
    db.commit()
    db.refresh(msg)
    return _msg_to_response(msg)


@router.get("/profile")
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch the Gmail profile for the connected Google account."""
    from agents.gmail_agent import GmailAgent

    creds = get_credentials(current_user.id, db)
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Google account not connected.",
        )
    try:
        agent = GmailAgent()
        profile = await agent.get_profile(creds)
    except Exception as exc:
        logger.error("Failed to fetch Gmail profile for user %d: %s", current_user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch Gmail profile: {exc}",
        )
    return profile
