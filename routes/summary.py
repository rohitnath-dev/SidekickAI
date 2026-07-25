"""Summary routes — email summarisation, thread summaries, action item extraction."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models.user import User
from repositories.message_repo import MessageRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/summary", tags=["Summary"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SummaryRequest(BaseModel):
    email_content: str
    context: Optional[str] = None


class ThreadSummaryRequest(BaseModel):
    thread_content: str


class ActionItemsRequest(BaseModel):
    email_content: str


class SummaryResponse(BaseModel):
    summary: Optional[str] = None
    key_points: list[str] = []
    action_items: list[str] = []
    sentiment: Optional[str] = None
    reply_required: Optional[bool] = None
    confidence_score: Optional[int] = None


class ActionItemsResponse(BaseModel):
    action_items: list


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/generate", response_model=SummaryResponse)
async def generate_summary(
    request: SummaryRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate an AI summary of an email."""
    from agents.summary_agent import SummaryAgent

    try:
        result = await SummaryAgent().generate_summary(
            email_content=request.email_content,
            context=request.context,
        )
    except Exception as exc:
        logger.error("Summary generation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return SummaryResponse(
        summary=result.get("summary"),
        key_points=result.get("key_points", []),
        action_items=result.get("action_items", []),
        sentiment=result.get("sentiment"),
        reply_required=result.get("reply_required"),
        confidence_score=result.get("confidence_score"),
    )


@router.post("/thread", response_model=dict)
async def summarize_thread(
    request: ThreadSummaryRequest,
    current_user: User = Depends(get_current_user),
):
    """Summarise an entire email thread."""
    from agents.summary_agent import SummaryAgent

    try:
        result = await SummaryAgent().summarize_thread(thread_content=request.thread_content)
    except Exception as exc:
        logger.error("Thread summary failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return result


@router.post("/action-items", response_model=ActionItemsResponse)
async def extract_action_items(
    request: ActionItemsRequest,
    current_user: User = Depends(get_current_user),
):
    """Extract action items from an email."""
    from agents.summary_agent import SummaryAgent

    try:
        result = await SummaryAgent().extract_action_items(email_content=request.email_content)
    except Exception as exc:
        logger.error("Action items extraction failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    items = result.get("action_items", [])
    return ActionItemsResponse(action_items=items)


@router.post("/message/{message_id}", response_model=SummaryResponse)
async def summarize_stored_message(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Summarise a stored message and save the result."""
    from agents.summary_agent import SummaryAgent

    msg = MessageRepository.get_by_id(db, message_id, current_user.id)
    if msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")

    try:
        result = await SummaryAgent().generate_summary(email_content=msg.to_context_string())
    except Exception as exc:
        logger.error("Message summary failed for msg %d: %s", message_id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    # Persist AI fields
    msg.update_from_ai(
        summary=result.get("summary"),
        sentiment=result.get("sentiment"),
        requires_reply=result.get("reply_required"),
        confidence_score=result.get("confidence_score"),
        action_items=str(result.get("action_items", [])),
    )
    db.commit()

    return SummaryResponse(
        summary=result.get("summary"),
        key_points=result.get("key_points", []),
        action_items=result.get("action_items", []),
        sentiment=result.get("sentiment"),
        reply_required=result.get("reply_required"),
        confidence_score=result.get("confidence_score"),
    )
