"""Memory routes — extract, store, search, and manage long-term facts."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models.user import User
from repositories.memory_repo import MemoryRepository
from repositories.message_repo import MessageRepository

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/memory",
    tags=["Memory"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class MemoryResponse(BaseModel):
    id: int
    category: str
    content: str
    context: Optional[str] = None
    related_person: Optional[str] = None
    related_project: Optional[str] = None
    retention_value: str
    confidence: float
    created_at: Optional[str] = None


class ExtractMemoryRequest(BaseModel):
    message_content: str = Field(
        ...,
        min_length=1,
        description="Text from which durable user memories should be extracted.",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _item_to_response(item) -> MemoryResponse:
    """Convert a MemoryItem ORM object into the API response schema."""

    data = item.to_dict()

    return MemoryResponse(
        **{
            field: data.get(field)
            for field in MemoryResponse.model_fields
        }
    )


# ---------------------------------------------------------------------------
# List memories
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=list[MemoryResponse],
)
async def list_memories(
    category: Optional[str] = Query(
        default=None,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    current_user: User = Depends(
        get_current_user,
    ),
    db: Session = Depends(
        get_db,
    ),
):
    """List stored memories belonging to the current user."""

    items = MemoryRepository.list_by_user(
        db=db,
        user_id=current_user.id,
        category=category,
        limit=limit,
    )

    return [
        _item_to_response(item)
        for item in items
    ]


# ---------------------------------------------------------------------------
# Search memories
# ---------------------------------------------------------------------------

@router.get(
    "/search",
    response_model=list[MemoryResponse],
)
async def search_memories(
    q: str = Query(
        ...,
        min_length=1,
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    current_user: User = Depends(
        get_current_user,
    ),
    db: Session = Depends(
        get_db,
    ),
):
    """Search the current user's stored memories."""

    items = MemoryRepository.search(
        db=db,
        user_id=current_user.id,
        query=q,
        limit=limit,
    )

    return [
        _item_to_response(item)
        for item in items
    ]


# ---------------------------------------------------------------------------
# Extract memories from raw text
# ---------------------------------------------------------------------------

@router.post(
    "/extract",
    response_model=list[MemoryResponse],
)
async def extract_memories(
    request: ExtractMemoryRequest,
    current_user: User = Depends(
        get_current_user,
    ),
    db: Session = Depends(
        get_db,
    ),
):
    """
    Extract durable memories from user-provided text and persist them.

    Used by the manual AI Fact Extractor in the frontend.
    """

    from agents.memory_agent import MemoryAgent

    agent = MemoryAgent()

    try:
        memories = await agent.extract_from_text(
            text=request.message_content,
            user_id=current_user.id,
        )

        saved = await agent.save_memories(
            memories=memories,
            user_id=current_user.id,
            db=db,
        )

    except Exception as exc:
        logger.exception(
            "Memory extraction failed for user_id=%s",
            current_user.id,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Memory processing temporarily unavailable.",
        ) from exc

    return [
        _item_to_response(item)
        for item in saved
    ]


# ---------------------------------------------------------------------------
# Extract memories from an existing message
# ---------------------------------------------------------------------------

@router.post(
    "/message/{message_id}",
    response_model=list[MemoryResponse],
)
async def extract_from_message(
    message_id: int,
    current_user: User = Depends(
        get_current_user,
    ),
    db: Session = Depends(
        get_db,
    ),
):
    """
    Extract durable memories from a stored message.

    The message must belong to the authenticated user.
    """

    from agents.memory_agent import MemoryAgent

    message = MessageRepository.get_by_id(
        db,
        message_id,
        current_user.id,
    )

    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found.",
        )

    agent = MemoryAgent()

    try:
        memories = await agent.extract_memory(
            message,
        )

        saved = await agent.save_memories(
            memories=memories,
            user_id=current_user.id,
            db=db,
            source_message_id=message.message_id,
        )

    except Exception as exc:
        logger.exception(
            "Memory extraction failed for message_id=%s user_id=%s",
            message_id,
            current_user.id,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to extract memories from this message.",
        ) from exc

    return [
        _item_to_response(item)
        for item in saved
    ]


# ---------------------------------------------------------------------------
# Delete memory
# ---------------------------------------------------------------------------

@router.delete(
    "/{memory_id}",
)
async def delete_memory(
    memory_id: int,
    current_user: User = Depends(
        get_current_user,
    ),
    db: Session = Depends(
        get_db,
    ),
):
    """Delete a memory owned by the current user."""

    deleted = MemoryRepository.delete(
        db=db,
        memory_id=memory_id,
        user_id=current_user.id,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found.",
        )

    return {
        "deleted": True,
        "id": memory_id,
    }