"""
Priority routes — message urgency and importance analysis.

Supports:
- Raw message priority analysis
- Stored message priority analysis
- Request-specific LLM configuration
- Server-side default LLM fallback
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models.user import User
from repositories.message_repo import MessageRepository
from services.llm import LLMClient, llm
from utils.prompts.priority import build_priority_prompt


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/priority",
    tags=["Priority"],
)


# ============================================================================
# Schemas
# ============================================================================


class PriorityRequest(BaseModel):
    """
    Request for analysing the priority of a raw message.

    LLM configuration is optional.

    If provider/api_key/model/base_url are omitted,
    the application's default LLM configuration is used.
    """

    # Message data
    message_content: str
    context: Optional[str] = None

    # Optional request-specific LLM configuration
    provider: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None


class PriorityResponse(BaseModel):
    """
    Normalized priority analysis response.
    """

    score: int
    priority_level: str
    requires_reply: bool
    reason: str
    recommended_action: Optional[str] = None
    risk_if_ignored: Optional[str] = None


# ============================================================================
# LLM Helpers
# ============================================================================


def _get_request_llm(request: PriorityRequest) -> LLMClient:
    """
    Return a request-specific LLM client when configuration is supplied.

    If no LLM configuration is provided, return the application's
    existing global/default LLM client.

    API keys are never logged.
    """

    has_request_config = any(
        value is not None
        for value in (
            request.provider,
            request.api_key,
            request.model,
            request.base_url,
        )
    )

    if not has_request_config:
        return llm

    try:
        return LLMClient(
            provider=request.provider,
            api_key=request.api_key,
            model=request.model,
            base_url=request.base_url,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


# ============================================================================
# JSON Helpers
# ============================================================================


def _clean_llm_json(raw: str) -> str:
    """
    Clean common LLM JSON formatting issues.

    Handles:
    - Markdown code fences
    - Leading/trailing whitespace
    """

    if not raw:
        return ""

    cleaned = raw.strip()

    # Handle:
    # ```json
    # {...}
    # ```
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()

        if len(lines) >= 3:
            # Remove opening and closing fences
            cleaned = "\n".join(lines[1:-1]).strip()

    return cleaned


def _parse_llm_result(raw: str) -> dict:
    """
    Parse an LLM response into a dictionary.

    Returns an empty dictionary if the response cannot be parsed.
    """

    cleaned = _clean_llm_json(raw)

    if not cleaned:
        return {}

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning(
            "Priority LLM returned invalid JSON: %s",
            cleaned[:500],
        )
        return {}

    if not isinstance(result, dict):
        logger.warning(
            "Priority LLM returned non-object JSON: %s",
            type(result).__name__,
        )
        return {}

    return result


# ============================================================================
# Response Normalization
# ============================================================================


def _parse_priority(result: dict) -> PriorityResponse:
    """
    Normalize raw LLM priority output into the API response schema.

    Supports both:
        score
    and:
        priority_score

    Score is always clamped to 0-100.
    """

    raw_score = result.get(
        "score",
        result.get("priority_score", 50),
    )

    try:
        score = max(
            0,
            min(
                100,
                int(round(float(raw_score))),
            ),
        )

    except (TypeError, ValueError):
        score = 50

    priority_level = str(
        result.get("priority_level", "medium")
    ).lower()

    if priority_level not in {
        "low",
        "medium",
        "high",
        "critical",
    }:
        priority_level = "medium"

    requires_reply = result.get(
        "requires_reply",
        result.get("requires_immediate_reply", False),
    )

    # Normalize boolean safely
    if isinstance(requires_reply, str):
        requires_reply = requires_reply.lower() in {
            "true",
            "1",
            "yes",
            "y",
        }
    else:
        requires_reply = bool(requires_reply)

    return PriorityResponse(
        score=score,
        priority_level=priority_level,
        requires_reply=requires_reply,
        reason=str(
            result.get(
                "reason",
                "Unable to classify.",
            )
        ),
        recommended_action=result.get(
            "recommended_action"
        ),
        risk_if_ignored=result.get(
            "risk_if_ignored"
        ),
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/analyze",
    response_model=PriorityResponse,
)
async def analyze_priority(
    request: PriorityRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Analyse the priority of a raw message.

    The frontend can optionally provide:

        provider
        api_key
        model
        base_url

    If none are provided, the configured global LLM client is used.
    """

    prompt = build_priority_prompt(
        message_content=request.message_content,
        context=request.context,
    )

    request_llm = _get_request_llm(request)

    try:
        logger.info(
            "Priority analysis request: provider=%s model=%s user_id=%s",
            getattr(request_llm, "provider", "unknown"),
            getattr(
                request_llm,
                "_active_model",
                lambda: "unknown",
            )(),
            current_user.id,
        )

        raw = await request_llm.generate(
            prompt=prompt,
            user_id=current_user.id,
            caller="PriorityRoute",
        )

        result = _parse_llm_result(raw)

    except HTTPException:
        raise

    except Exception as exc:
        logger.error(
            "Priority analysis failed: %s",
            exc,
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Priority analysis failed.",
        ) from exc

    return _parse_priority(result)


# ============================================================================
# Stored Message Endpoint
# ============================================================================


@router.post(
    "/message/{message_id}",
    response_model=PriorityResponse,
)
async def analyze_stored_message(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Analyse the priority of a stored message and update its record.

    This endpoint continues to use PriorityAgent, which in turn uses
    BaseAgent's configured LLM client.
    """

    from agents.priority_agent import PriorityAgent

    msg = MessageRepository.get_by_id(
        db,
        message_id,
        current_user.id,
    )

    if msg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found.",
        )

    try:
        result = await PriorityAgent().analyze(msg)

    except Exception as exc:
        logger.error(
            "Priority for message %d failed: %s",
            message_id,
            exc,
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Priority analysis failed.",
        ) from exc

    # ------------------------------------------------------------------------
    # Map priority level string to enum
    # ------------------------------------------------------------------------

    from models.message import MessagePriority

    level_str = str(
        result.get(
            "priority_level",
            "medium",
        )
    ).lower()

    try:
        priority_enum = MessagePriority(level_str)

    except ValueError:
        priority_enum = MessagePriority.MEDIUM

    # ------------------------------------------------------------------------
    # Update stored message
    # ------------------------------------------------------------------------

    msg.update_from_ai(
        priority=priority_enum,
        requires_reply=bool(
            result.get(
                "requires_reply",
                False,
            )
        ),
        confidence_score=result.get(
            "score",
            result.get("priority_score"),
        ),
    )

    db.commit()

    return _parse_priority(result)