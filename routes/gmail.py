import logging

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

logger = logging.getLogger(__name__)

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
    try:
        authorization_url = get_authorization_url()
    except Exception as exc:
        logger.error("Failed to generate Gmail authorization URL: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate Gmail authorization URL.",
        )

    return {"authorization_url": authorization_url}


@router.get(
    "/callback",
    status_code=status.HTTP_200_OK,
)
async def callback(
    code: str = Query(...),
    db: Session = Depends(get_db),
):
    try:
        exchange_authorization_code(code=code, db=db)
    except Exception as exc:
        logger.error("Failed to exchange Gmail authorization code: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to exchange Gmail authorization code.",
        )

    return {"status": "success"}


@router.post(
    "/sync",
    response_model=SyncResponse,
    status_code=status.HTTP_200_OK,
)
async def sync(
    request: SyncRequest,
    db: Session = Depends(get_db),
):
    try:
        result = sync_messages(max_results=request.max_results, db=db)
    except Exception as exc:
        logger.error("Failed to sync Gmail messages: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to sync Gmail messages.",
        )

    if result is None:
        logger.error("Gmail sync returned no result.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gmail sync returned no result.",
        )

    synced_messages = getattr(result, "synced_messages", None)
    if synced_messages is None and isinstance(result, dict):
        synced_messages = result.get("synced_messages")

    sync_status = getattr(result, "status", None)
    if sync_status is None and isinstance(result, dict):
        sync_status = result.get("status")

    if synced_messages is None or sync_status is None:
        logger.error("Gmail sync result is missing expected fields.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gmail sync result is missing expected fields.",
        )

    return SyncResponse(synced_messages=synced_messages, status=sync_status)


@router.get(
    "/messages",
    response_model=list[GmailMessageResponse],
    status_code=status.HTTP_200_OK,
)
async def messages(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    try:
        stored_messages = list_messages(limit=limit, db=db)
    except Exception as exc:
        logger.error("Failed to retrieve Gmail messages: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve Gmail messages.",
        )

    if stored_messages is None:
        logger.error("Gmail message retrieval returned no result.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gmail message retrieval returned no result.",
        )

    return stored_messages