"""Gmail routes — OAuth connection and message management."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
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
async def authorize(current_user: User = Depends(get_current_user)):
    """Generate the Google OAuth consent URL."""
    try:
        url, state = generate_authorization_url()
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Exchange the OAuth code for tokens and store them."""
    try:
        exchange_code_for_tokens(code=code, state=state, db=db, user_id=current_user.id)
    except Exception as exc:
        logger.error("OAuth exchange failed for user %d: %s", current_user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to exchange authorization code: {exc}",
        )
    return {"status": "success", "message": "Google account connected successfully."}


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
        )
    except Exception as exc:
        logger.error("Gmail sync failed for user %d: %s", current_user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gmail sync failed: {exc}",
        )

    return SyncResponse(
        synced=result.get("synced", 0),
        total_stored=result.get("total_stored", 0),
        status="success",
    )


@router.get("/messages", response_model=list[MessageResponse])
async def list_messages(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    unread_only: bool = Query(default=False),
    source: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List stored messages for the current user."""
    messages = MessageRepository.list_by_user(
        db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
        source=source,
    )
    return [_msg_to_response(m) for m in messages]


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
