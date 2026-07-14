from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from agents.summary_agent import (
    generate_summary,
    summarize_thread,
    extract_action_items,
)

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


@router.post(
    "/generate",
    response_model=SummaryResponse,
    status_code=status.HTTP_200_OK,
)
async def generate(
    request: SummaryRequest,
    db: Session = Depends(get_db),
):
    pass


@router.post(
    "/thread",
    response_model=SummaryResponse,
    status_code=status.HTTP_200_OK,
)
async def thread(
    request: ThreadSummaryRequest,
    db: Session = Depends(get_db),
):
    pass


@router.post(
    "/action-items",
    response_model=ActionItemsResponse,
    status_code=status.HTTP_200_OK,
)
async def action_items(
    request: ActionItemsRequest,
    db: Session = Depends(get_db),
):
    pass


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
)
async def health():
    pass
