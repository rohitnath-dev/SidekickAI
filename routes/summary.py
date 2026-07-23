import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from agents.summary_agent import (
    generate_summary,
    summarize_thread,
    extract_action_items,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/summary",
    tags=["Summary"],
)


class SummaryRequest(BaseModel):
    email_content: str = Field(..., min_length=1)
    context: str | None = None


class ThreadSummaryRequest(BaseModel):
    thread_content: str = Field(..., min_length=1)


class ActionItemsRequest(BaseModel):
    email_content: str = Field(..., min_length=1)


class SummaryResponse(BaseModel):
    summary: str


class ActionItemsResponse(BaseModel):
    action_items: list[str]


def _get_field(result: Any, field: str) -> Any:
    if isinstance(result, dict):
        return result.get(field)
    return getattr(result, field, None)


def _extract_summary_text(result: Any) -> str | None:
    summary_text = _get_field(result, "summary")

    if not isinstance(summary_text, str):
        return None

    if not summary_text.strip():
        return None

    return summary_text


def _extract_action_items_list(result: Any) -> list[str] | None:
    items = _get_field(result, "action_items")

    if not isinstance(items, list):
        return None

    if not all(isinstance(item, str) for item in items):
        return None

    return items


@router.post(
    "/generate",
    response_model=SummaryResponse,
    status_code=status.HTTP_200_OK,
)
async def generate(
    request: SummaryRequest,
    db: Session = Depends(get_db),
):
    try:
        result = generate_summary(
            email_content=request.email_content,
            context=request.context,
            db=db,
        )
    except Exception as exc:
        logger.error("Failed to generate summary: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate summary.",
        )

    summary_text = _extract_summary_text(result)

    if not summary_text:
        logger.error("Summary generation returned no usable summary text.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Summary generation returned no usable summary text.",
        )

    return SummaryResponse(summary=summary_text)


@router.post(
    "/thread",
    response_model=SummaryResponse,
    status_code=status.HTTP_200_OK,
)
async def thread(
    request: ThreadSummaryRequest,
    db: Session = Depends(get_db),
):
    try:
        result = summarize_thread(
            thread_content=request.thread_content,
            db=db,
        )
    except Exception as exc:
        logger.error("Failed to summarize thread: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to summarize thread.",
        )

    summary_text = _extract_summary_text(result)

    if not summary_text:
        logger.error("Thread summarization returned no usable summary text.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Thread summarization returned no usable summary text.",
        )

    return SummaryResponse(summary=summary_text)


@router.post(
    "/action-items",
    response_model=ActionItemsResponse,
    status_code=status.HTTP_200_OK,
)
async def action_items(
    request: ActionItemsRequest,
    db: Session = Depends(get_db),
):
    try:
        result = extract_action_items(
            email_content=request.email_content,
            db=db,
        )
    except Exception as exc:
        logger.error("Failed to extract action items: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to extract action items.",
        )

    items = _extract_action_items_list(result)

    if items is None:
        logger.error("Action item extraction returned no usable data.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Action item extraction returned no usable data.",
        )

    return ActionItemsResponse(action_items=items)


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
)
async def health():
    return {"status": "ok", "service": "Summary API"}