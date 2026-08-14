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

from collections import defaultdict
import asyncio

_sync_run_locks = defaultdict(asyncio.Lock)


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


@router.post("/sync")
async def sync_all_integrations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Trigger immediate synchronization for all connected integration sources.
    Does NOT run the AI pipeline.
    """
    # Prevent concurrent sync runs for this user
    lock = _sync_run_locks[current_user.id]
    if lock.locked():
         raise HTTPException(
             status_code=status.HTTP_409_CONFLICT,
             detail="Synchronization is already in progress. Please wait."
         )

    async with lock:
        from config import settings
        from datetime import datetime

        tokens = TokenRepository.list_by_user(db, current_user.id)
        connected_providers = set()

        # Check Gmail
        gmail_token = next((t for t in tokens if t.provider == "google"), None)
        if gmail_token and gmail_token.access_token and gmail_token.access_token != "disabled":
            connected_providers.add("gmail")

        # Check Telegram
        if any(t.provider == "telegram" and t.access_token and t.access_token != "disabled" for t in tokens):
            connected_providers.add("telegram")

        # Check Discord
        if any(t.provider == "discord" and t.access_token and t.access_token != "disabled" for t in tokens):
            connected_providers.add("discord")

        # Check Twitter
        if settings.TWITTER_BEARER_TOKEN and settings.TWITTER_USER_ID:
            disabled_token = next((t for t in tokens if t.provider == "twitter"), None)
            if not (disabled_token and disabled_token.access_token == "disabled"):
                connected_providers.add("twitter")

        synced_results = {}
        errors = []

        # 1. Gmail
        if "gmail" in connected_providers:
            try:
                from services.oauth import get_credentials
                creds = get_credentials(current_user.id, db)
                if creds:
                    from agents.gmail_agent import GmailAgent
                    agent = GmailAgent()
                    res = await agent.sync_messages(
                        creds=creds,
                        db=db,
                        user_id=current_user.id,
                        limit=20,
                        unread_only=False,
                    )
                    synced_results["gmail"] = res.get("synced", 0) if isinstance(res, dict) else 0
            except Exception as e:
                logger.error("Sync API: Gmail sync failed for user %d: %s", current_user.id, e)
                errors.append(f"Gmail: {str(e)}")

        # 2. Telegram
        if "telegram" in connected_providers:
            try:
                from routes.telegram import sync_telegram
                res = await sync_telegram(current_user=current_user, db=db)
                synced_results["telegram"] = getattr(res, "synced", 0) if hasattr(res, "synced") else (res.get("synced", 0) if isinstance(res, dict) else 0)
            except Exception as e:
                logger.error("Sync API: Telegram sync failed for user %d: %s", current_user.id, e)
                errors.append(f"Telegram: {str(e)}")

        # 3. Discord
        if "discord" in connected_providers:
            try:
                from routes.discord import sync_discord
                res = await sync_discord(current_user=current_user, db=db)
                synced_results["discord"] = getattr(res, "synced", 0) if hasattr(res, "synced") else (res.get("synced", 0) if isinstance(res, dict) else 0)
            except Exception as e:
                logger.error("Sync API: Discord sync failed for user %d: %s", current_user.id, e)
                errors.append(f"Discord: {str(e)}")

        # 4. Twitter
        if "twitter" in connected_providers:
            try:
                from routes.twitter import sync_twitter_mentions
                res = await sync_twitter_mentions(current_user=current_user, db=db)
                synced_results["twitter"] = res.get("synced", 0) if isinstance(res, dict) else 0
            except Exception as e:
                logger.error("Sync API: Twitter sync failed for user %d: %s", current_user.id, e)
                errors.append(f"Twitter: {str(e)}")

        total_synced = sum(synced_results.values())
        status_str = "success" if not errors else "partial_failure"

        if len(errors) == len(connected_providers) and connected_providers:
            status_str = "failure"
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"All sync operations failed: {'; '.join(errors)}"
            )

        return {
            "status": status_str,
            "synced": total_synced,
            "details": synced_results,
            "errors": errors
        }


# ---------------------------------------------------------------------------
# User AI/LLM Config Endpoints
# ---------------------------------------------------------------------------

class AIConfigResponse(BaseModel):
    configured: bool
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    has_api_key: bool = False


class AIConfigSaveRequest(BaseModel):
    provider: str  # "openrouter" or "ollama"
    model: str
    api_key: str | None = None
    base_url: str | None = None


class AIConfigTestRequest(BaseModel):
    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None


@router.get("/ai-config", response_model=AIConfigResponse)
async def get_user_ai_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve the current user's AI provider configuration."""
    from models.ai_config import UserAIConfig

    config = db.query(UserAIConfig).filter_by(user_id=current_user.id).first()
    if not config:
        return AIConfigResponse(configured=False)

    return AIConfigResponse(
        configured=True,
        provider=config.provider,
        model=config.model,
        base_url=config.base_url,
        has_api_key=bool(config.api_key and config.api_key.strip() != ""),
    )


@router.post("/ai-config")
async def save_user_ai_config(
    request: AIConfigSaveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save or update the user's AI provider configuration."""
    from models.ai_config import UserAIConfig

    if request.provider not in ("openrouter", "ollama"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid provider. Must be either 'openrouter' or 'ollama'."
        )

    if not request.model.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model name cannot be empty."
        )

    config = db.query(UserAIConfig).filter_by(user_id=current_user.id).first()
    if not config:
        config = UserAIConfig(user_id=current_user.id)
        db.add(config)

    config.provider = request.provider
    config.model = request.model.strip()

    if request.provider == "openrouter":
        config.base_url = None
        # Only update the API key if a new non-empty, non-placeholder one is provided
        if request.api_key and not request.api_key.startswith("•••"):
            config.api_key = request.api_key.strip()
        elif not config.api_key:
            # If no API key was saved before and none is provided now
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API Key is required for OpenRouter configuration."
            )
    else:  # ollama
        config.api_key = None
        config.base_url = (request.base_url or "http://localhost:11434").strip().rstrip("/")

    db.commit()
    logger.info("Saved AI configuration for user_id=%d, provider=%s", current_user.id, request.provider)
    return {"status": "success", "message": "AI configuration saved successfully."}


@router.post("/ai-config/test")
async def test_user_ai_config_connection(
    request: AIConfigTestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify provider connectivity with the specified settings."""
    from services.llm import LLMException, LLMConnectionError, LLMAuthenticationError
    import httpx

    provider = request.provider
    model = request.model
    api_key = request.api_key
    base_url = request.base_url

    if provider not in ("openrouter", "ollama"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid provider. Must be either 'openrouter' or 'ollama'."
        )

    if not model.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model name cannot be empty."
        )

    # If it is OpenRouter and API key is placeholder/empty, look up existing saved key
    if provider == "openrouter":
        if not api_key or api_key.startswith("•••"):
            from models.ai_config import UserAIConfig
            config = db.query(UserAIConfig).filter_by(user_id=current_user.id).first()
            if config and config.api_key:
                api_key = config.api_key
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="API key is required."
                )
    
    # Perform connection test
    if provider == "openrouter":
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://sidekick.ai",
            "X-Title": "Sidekick AI",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload,
                    headers=headers
                )
                if response.status_code != 200:
                    status_code = response.status_code
                    try:
                        body = response.json()
                    except Exception:
                        body = response.text
                    
                    if status_code == 401:
                        raise LLMAuthenticationError("Authentication failed. Please verify your OpenRouter API key.")
                    raise LLMException(f"OpenRouter returned error status {status_code}: {body}")
        except httpx.ConnectError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to connect to OpenRouter. Please check your internet connection."
            )
        except LLMAuthenticationError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc)
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"OpenRouter test connection failed: {exc}"
            )
    else:  # ollama
        url = (base_url or "http://localhost:11434").strip().rstrip("/")
        full_url = f"{url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(full_url, json=payload)
                if response.status_code != 200:
                    body = response.text
                    if "model" in str(body).lower() and "not found" in str(body).lower():
                        raise LLMException(f"Model '{model}' is not found in your Ollama installation. Please pull it first using 'ollama pull {model}'.")
                    raise LLMException(f"Ollama returned error status {response.status_code}")
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Couldn't connect to Ollama. Make sure Ollama is running and the configured URL is correct."
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc)
            )

    return {"status": "success", "message": "Connection successful"}
