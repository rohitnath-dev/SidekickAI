from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from agents.gmail_agent import (
    get_authorization_url,
    exchange_authorization_code,
    sync_messages,
    list_messages,
)

router = APIRouter(
    prefix="/gmail",
    tags=["Gmail"],
)


class OAuthCallbackRequest(BaseModel):
    code: str = Field(..., min_length=1)


class SyncRequest(BaseModel):
    max_results: int = Field(default=20, ge=1, le=100)


class GmailMessageResponse(BaseModel):
    id: str
    thread_id: str
    sender: str
    subject: str
    snippet: str
    received_at: str


class SyncResponse(BaseModel):
    synced_messages: int
    status: str


@router.get(
    "/authorize",
    status_code=status.HTTP_200_OK,
)
async def authorize():
    pass


@router.get(
    "/callback",
    status_code=status.HTTP_200_OK,
)
async def callback(
    code: str = Query(...),
    db: Session = Depends(get_db),
):
    pass


@router.post(
    "/sync",
    response_model=SyncResponse,
    status_code=status.HTTP_200_OK,
)
async def sync(
    request: SyncRequest,
    db: Session = Depends(get_db),
):
    pass


@router.get(
    "/messages",
    response_model=list[GmailMessageResponse],
    status_code=status.HTTP_200_OK,
)
async def messages(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    pass
