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

KNOWN_PROVIDERS = ["google", "twitter", "whatsapp"]


@router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return user preferences and which services are connected."""
    tokens = TokenRepository.list_by_user(db, current_user.id)
    connected = {t.provider: t for t in tokens}

    services = []
    for provider in KNOWN_PROVIDERS:
        token = connected.get(provider)
        services.append(
            ConnectedService(
                provider=provider,
                connected=token is not None,
                connected_at=token.created_at.isoformat() if token else None,
            )
        )

    return PreferencesResponse(connected_services=services)


@router.get("/connected-services", response_model=list[ConnectedService])
async def list_connected_services(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all OAuth services the user has connected."""
    tokens = TokenRepository.list_by_user(db, current_user.id)
    return [
        ConnectedService(
            provider=t.provider,
            connected=True,
            connected_at=t.created_at.isoformat() if t.created_at else None,
        )
        for t in tokens
    ]


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
    deleted = TokenRepository.delete(db, user_id=current_user.id, provider=provider)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No connected {provider} account found.",
        )
    return {"status": "disconnected", "provider": provider}
