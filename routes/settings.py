"""Settings routes — user preferences and connected services."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models.user import User
from repositories.token_repo import TokenRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["Settings"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ConnectedService(BaseModel):
    provider: str
    connected: bool
    connected_at: str | None = None


class PreferencesResponse(BaseModel):
    tone: str = "professional"
    language: str = "English"
    notification_enabled: bool = True
    connected_services: list[ConnectedService] = []


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

KNOWN_PROVIDERS = ["google", "twitter", "whatsapp", "linkedin", "telegram", "discord"]


@router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return user preferences and which services are connected."""
    from config import settings
    tokens = TokenRepository.list_by_user(db, current_user.id)
    connected = {t.provider: t for t in tokens}

    services = []
    for provider in KNOWN_PROVIDERS:
        is_connected = False
        connected_at = None
        
        token = connected.get(provider)
        if token:
            if token.access_token == "disabled":
                is_connected = False
            else:
                is_connected = True
                connected_at = token.created_at.isoformat() if token.created_at else None
        elif provider == "twitter" and settings.TWITTER_BEARER_TOKEN:
            is_connected = True
        elif provider == "whatsapp" and settings.WHATSAPP_API_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID:
            is_connected = True

        services.append(
            ConnectedService(
                provider=provider,
                connected=is_connected,
                connected_at=connected_at,
            )
        )

    return PreferencesResponse(connected_services=services)


@router.get("/connected-services", response_model=list[ConnectedService])
async def list_connected_services(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all OAuth services the user has connected."""
    from config import settings
    tokens = TokenRepository.list_by_user(db, current_user.id)
    connected = {t.provider: t for t in tokens}
    
    services = []
    for provider in KNOWN_PROVIDERS:
        is_connected = False
        connected_at = None
        
        token = connected.get(provider)
        if token:
            if token.access_token == "disabled":
                is_connected = False
            else:
                is_connected = True
                connected_at = token.created_at.isoformat() if token.created_at else None
        elif provider == "twitter" and settings.TWITTER_BEARER_TOKEN:
            is_connected = True
        elif provider == "whatsapp" and settings.WHATSAPP_API_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID:
            is_connected = True
            
        if is_connected:
            services.append(
                ConnectedService(
                    provider=provider,
                    connected=True,
                    connected_at=connected_at,
                )
            )
            
    return services


@router.post("/disconnect/{provider}")
async def disconnect_service(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disconnect an OAuth service."""
    if provider not in KNOWN_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown provider '{provider}'. Supported: {', '.join(KNOWN_PROVIDERS)}",
        )

    from config import settings
    has_system_fallback = False
    if provider == "whatsapp" and settings.WHATSAPP_API_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID:
        has_system_fallback = True
    elif provider == "twitter" and settings.TWITTER_BEARER_TOKEN:
        has_system_fallback = True

    if has_system_fallback:
        # Upsert a disabled token marker to override the system fallback
        TokenRepository.upsert(
            db=db,
            user_id=current_user.id,
            provider=provider,
            access_token="disabled",
            refresh_token="disabled",
            token_uri="disabled",
        )
    else:
        # Just delete it since there is no system fallback
        TokenRepository.delete(db, user_id=current_user.id, provider=provider)

    return {"status": "disconnected", "provider": provider}


@router.post("/clear-data")
async def clear_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Clear all messages and memory logs for the authenticated user."""
    from models.message import Message
    from models.memory_item import MemoryItem
    try:
        db.query(Message).filter_by(user_id=current_user.id).delete()
        db.query(MemoryItem).filter_by(user_id=current_user.id).delete()
        db.commit()
        logger.info("Cleared all messages and memory logs for user_id=%d", current_user.id)
        return {"status": "success", "message": "All messages and memory items have been cleared."}
    except Exception as exc:
        db.rollback()
        logger.error("Failed to clear data for user_id=%d: %s", current_user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear database logs: {str(exc)}"
        )
