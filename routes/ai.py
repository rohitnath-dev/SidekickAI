"""
Sidekick AI — AI / LLM Routes

Handles:
- LLM health checks
- LLM test requests
- Manual message AI processing
- Full AI pipeline execution
- Request-specific LLM provider configuration

Supported providers:
- openrouter
- ollama

The frontend may provide:
- provider
- api_key
- model
- base_url

If these values are omitted, the application's configured defaults
are used.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models.message import Message
from models.user import User
from services.ai_pipeline import process_message_ai
from services.llm import (
    LLMAuthenticationError,
    LLMClient,
    LLMConnectionError,
    LLMException,
    LLMRateLimitError,
    LLMResponseError,
    llm,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/ai",
    tags=["AI"],
)


# ============================================================================
# Per-user AI locks
# ============================================================================

_ai_run_locks = defaultdict(
    asyncio.Lock
)


# ============================================================================
# Request models
# ============================================================================

class LLMConfigRequest(BaseModel):
    """
    Optional per-request LLM configuration.

    Example OpenRouter request:
    {
        "provider": "openrouter",
        "api_key": "user-api-key",
        "model": "openrouter/free"
    }

    Example Ollama request:
    {
        "provider": "ollama",
        "model": "llama3.2",
        "base_url": "http://localhost:11434"
    }
    """

    provider: Optional[str] = Field(
        default=None,
        description=(
            "LLM provider: openrouter or ollama"
        ),
    )

    api_key: Optional[str] = Field(
        default=None,
        description=(
            "User-provided API key. "
            "Required for OpenRouter when no "
            "server default exists."
        ),
    )

    model: Optional[str] = Field(
        default=None,
        description=(
            "Model to use. Uses configured default "
            "when omitted."
        ),
    )

    base_url: Optional[str] = Field(
        default=None,
        description=(
            "Optional provider base URL. "
            "Mainly used for Ollama."
        ),
    )


class TestPromptRequest(
    LLMConfigRequest
):
    prompt: Optional[str] = (
        "Hello, are you working?"
    )


class AnalyzeMessageRequest(
    LLMConfigRequest
):
    message_id: Optional[int] = None


class RunAIRequest(
    LLMConfigRequest
):
    pass


# ============================================================================
# LLM helpers
# ============================================================================

def _create_llm_client(
    config: LLMConfigRequest,
) -> LLMClient:
    """
    Create a request-specific LLMClient.

    API keys are never logged.
    """

    try:
        return LLMClient(
            provider=config.provider,
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


def _get_request_llm(
    config: LLMConfigRequest,
) -> LLMClient:
    """
    Return a request-specific LLM client when the
    request provides configuration.

    Otherwise return the application's default
    global LLM client.
    """

    has_request_config = any(
        value is not None
        for value in (
            config.provider,
            config.api_key,
            config.model,
            config.base_url,
        )
    )

    if not has_request_config:
        return llm

    return _create_llm_client(
        config
    )


def _llm_http_error(
    exc: Exception,
) -> HTTPException:
    """
    Convert internal LLM exceptions into safe
    HTTP responses.
    """

    if isinstance(
        exc,
        LLMAuthenticationError,
    ):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )

    if isinstance(
        exc,
        LLMRateLimitError,
    ):
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        )

    if isinstance(
        exc,
        LLMConnectionError,
    ):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )

    if isinstance(
        exc,
        LLMResponseError,
    ):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )

    if isinstance(
        exc,
        LLMException,
    ):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )

    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="LLM request failed.",
    )


# ============================================================================
# Health
# ============================================================================

@router.get("/health")
async def ai_health(
    current_user: User = Depends(
        get_current_user
    ),
):
    """
    Check the health of the current user's
    configured LLM.

    This uses the user's saved AI configuration
    when available, rather than the server-side
    default LLM client.
    """

    try:
        user_llm = LLMClient(
            user_id=current_user.id
        )

        return await user_llm.health_check_details()

    except Exception as exc:
        logger.error(
            "User LLM health check failed for user_id=%s: %s",
            current_user.id,
            exc,
            exc_info=True,
        )

        return {
            "status": "error",
            "provider": "unknown",
            "reason": "LLM health check failed.",
        }


# ============================================================================
# Test LLM
# ============================================================================

@router.post("/test")
async def ai_test(
    request: TestPromptRequest,
    current_user: User = Depends(
        get_current_user
    ),
):
    """
    Test the selected LLM configuration.

    Uses:
    1. Request-provided configuration, or
    2. Application defaults.
    """

    client = _get_request_llm(
        request
    )

    prompt = (
        request.prompt
        or "Hello, are you working?"
    )

    logger.info(
        "Executing LLM test for user_id=%s "
        "provider=%s model=%s",
        current_user.id,
        client.provider,
        client._active_model(),
    )

    try:
        response_text = await client.chat(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            max_tokens=100,
            user_id=current_user.id,
            caller="ai_test",
        )

        return {
            "status": "success",
            "provider": client.provider,
            "model": client._active_model(),
            "prompt": prompt,
            "response": response_text,
        }

    except Exception as exc:
        logger.error(
            "LLM test failed for user_id=%s: %s",
            current_user.id,
            exc,
            exc_info=True,
        )

        raise _llm_http_error(
            exc
        )


# ============================================================================
# Analyze messages
# ============================================================================

@router.post("/analyze")
async def analyze_messages(
    request: AnalyzeMessageRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(
        get_db
    ),
):
    """
    Run AI processing on:

    - one specific message, or
    - all unprocessed messages belonging to
      the current user.

    The same LLMClient is used for the entire
    operation.
    """

    lock = _ai_run_locks[
        current_user.id
    ]

    if lock.locked():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "AI processing is already "
                "in progress. Please wait."
            ),
        )

    client = _get_request_llm(
        request
    )

    async with lock:

        # --------------------------------------------------------------
        # Specific message
        # --------------------------------------------------------------

        if request.message_id is not None:

            message = (
                db.query(Message)
                .filter(
                    Message.id
                    == request.message_id,
                    Message.user_id
                    == current_user.id,
                )
                .first()
            )

            if not message:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        f"Message with ID "
                        f"{request.message_id} "
                        f"not found."
                    ),
                )

            try:
                logger.info(
                    "Running AI for message_id=%d "
                    "user_id=%d provider=%s model=%s",
                    message.id,
                    current_user.id,
                    client.provider,
                    client._active_model(),
                )

                await process_message_ai(
                    db=db,
                    message=message,
                    llm_client=client,
                )

                return {
                    "status": "success",
                    "provider": client.provider,
                    "model": client._active_model(),
                    "processed_count": 1,
                }

            except Exception as exc:
                logger.error(
                    "AI processing failed for message %d: %s",
                    message.id,
                    exc,
                    exc_info=True,
                )

                raise _llm_http_error(
                    exc
                )

        # --------------------------------------------------------------
        # All unprocessed messages
        # --------------------------------------------------------------

        unprocessed = (
            db.query(Message)
            .filter(
                Message.user_id
                == current_user.id,
                Message.is_processed
                == False,
            )
            .all()
        )

        if not unprocessed:
            return {
                "status": "success",
                "provider": client.provider,
                "model": client._active_model(),
                "processed_count": 0,
                "detail": (
                    "No unprocessed messages found."
                ),
            }

        count = 0
        errors: list[str] = []

        for message in unprocessed:

            try:
                await process_message_ai(
                    db=db,
                    message=message,
                    llm_client=client,
                )

                count += 1

            except Exception as exc:
                logger.error(
                    "AI processing failed for message %d: %s",
                    message.id,
                    exc,
                    exc_info=True,
                )

                errors.append(
                    f"Message {message.id}: "
                    "AI processing failed."
                )

        return {
            "status": (
                "success"
                if not errors
                else "partial_failure"
            ),
            "provider": client.provider,
            "model": client._active_model(),
            "processed_count": count,
            "errors": errors,
        }


# ============================================================================
# Authoritative AI Processing Job Endpoints
# ============================================================================

from services.job_manager import job_manager, AIJobState


@router.post("/job/start")
async def start_ai_job(
    request: RunAIRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Start or retrieve an authoritative Sync & AI processing job for current user.
    If a job is already in progress, returns the existing active job.
    """
    job = await job_manager.start_job(user_id=current_user.id, db=db, llm_config=request)
    return job.to_dict()


@router.get("/job/status")
async def get_ai_job_status(
    current_user: User = Depends(get_current_user),
):
    """Get active or latest processing job status for current user."""
    job = job_manager.get_job(str(current_user.id))
    if not job:
        return {
            "has_job": False,
            "state": "idle",
            "current_stage": "No processing job found.",
            "connected_integrations": [],
            "total_items_discovered": 0,
            "items_processed": 0,
            "errors": [],
            "briefing": None,
        }
    
    res = job.to_dict()
    res["has_job"] = True
    return res


@router.post("/job/cancel")
async def cancel_ai_job(
    current_user: User = Depends(get_current_user),
):
    """Cancel any active processing job for current user."""
    cancelled = await job_manager.cancel_job(current_user.id)
    return {"status": "success" if cancelled else "no_active_job", "cancelled": cancelled}


@router.post("/job/retry")
async def retry_ai_job(
    request: RunAIRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reset failed/stale job and start a new processing run."""
    user_id_str = str(current_user.id)
    job = job_manager.get_job(user_id_str)
    if job:
        job.state = AIJobState.STALE  # Force reset existing job
    new_job = await job_manager.start_job(user_id=current_user.id, db=db, llm_config=request)
    return new_job.to_dict()


@router.post("/run")
async def run_ai_pipeline(
    request: RunAIRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Backwards-compatible endpoint for running AI pipeline."""
    job = await job_manager.start_job(user_id=current_user.id, db=db, llm_config=request)
    return job.to_dict()
