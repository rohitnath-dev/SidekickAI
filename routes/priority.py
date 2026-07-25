"""Priority routes — message urgency and importance analysis."""

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
from services.llm import llm
from utils.prompts.priority import build_priority_prompt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/priority", tags=["Priority"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PriorityRequest(BaseModel):
    message_content: str
    context: Optional[str] = None


class PriorityResponse(BaseModel):
    score: int
    priority_level: str
    requires_reply: bool
    reason: str
    recommended_action: Optional[str] = None
    risk_if_ignored: Optional[str] = None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _parse_priority(result: dict) -> PriorityResponse:
    raw_score = result.get("score", result.get("priority_score", 50))
    try:
        score = max(0, min(100, int(round(float(raw_score)))))
    except (TypeError, ValueError):
        score = 50

    return PriorityResponse(
        score=score,
        priority_level=result.get("priority_level", "medium"),
        requires_reply=bool(result.get("requires_reply", False)),
        reason=result.get("reason", "Unable to classify."),
        recommended_action=result.get("recommended_action"),
        risk_if_ignored=result.get("risk_if_ignored"),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=PriorityResponse)
async def analyze_priority(
    request: PriorityRequest,
    current_user: User = Depends(get_current_user),
):
    """Analyse the priority of a raw message text."""
    prompt = build_priority_prompt(
        message_content=request.message_content,
        context=request.context,
    )
    try:
        raw = await llm.generate(prompt)
        # Strip markdown fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        result = {}
    except Exception as exc:
        logger.error("Priority analysis failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return _parse_priority(result)


@router.post("/message/{message_id}", response_model=PriorityResponse)
async def analyze_stored_message(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Analyse the priority of a stored message and update its record."""
    from agents.priority_agent import PriorityAgent

    msg = MessageRepository.get_by_id(db, message_id, current_user.id)
    if msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")

    try:
        result = await PriorityAgent().analyze(msg)
    except Exception as exc:
        logger.error("Priority for message %d failed: %s", message_id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    # Map priority level string to enum
    from models.message import MessagePriority
    level_str = result.get("priority_level", "medium").lower()
    try:
        priority_enum = MessagePriority(level_str)
    except ValueError:
        priority_enum = MessagePriority.MEDIUM

    msg.update_from_ai(
        priority=priority_enum,
        requires_reply=bool(result.get("requires_reply", False)),
        confidence_score=result.get("score"),
    )
    db.commit()

    return _parse_priority(result)
