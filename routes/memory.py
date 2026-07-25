"""Memory routes — extract, store, and query long-term facts."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models.user import User
from repositories.memory_repo import MemoryRepository
from repositories.message_repo import MessageRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["Memory"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class MemoryResponse(BaseModel):
    id: int
    category: str
    content: str
    context: Optional[str]
    related_person: Optional[str]
    related_project: Optional[str]
    retention_value: str
    confidence: float
    created_at: Optional[str]


class ExtractMemoryRequest(BaseModel):
    message_content: str


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _item_to_response(item) -> MemoryResponse:
    d = item.to_dict()
    return MemoryResponse(**{k: d.get(k) for k in MemoryResponse.model_fields})


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[MemoryResponse])
async def list_memories(
    category: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all memories for the current user."""
    items = MemoryRepository.list_by_user(
        db, user_id=current_user.id, category=category, limit=limit
    )
    return [_item_to_response(i) for i in items]


@router.get("/search", response_model=list[MemoryResponse])
async def search_memories(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Search memories by content."""
    items = MemoryRepository.search(db, user_id=current_user.id, query=q, limit=limit)
    return [_item_to_response(i) for i in items]


@router.post("/extract", response_model=list[MemoryResponse])
async def extract_memories(
    request: ExtractMemoryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Extract and persist memories from raw text."""
    from agents.memory_agent import MemoryAgent

    agent = MemoryAgent()
    try:
        raw_memories = await agent.extract_from_text(request.message_content)
        saved = await agent.save_memories(
            memories=raw_memories,
            user_id=current_user.id,
            db=db,
        )
    except Exception as exc:
        logger.error("Memory extraction failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return [_item_to_response(i) for i in saved]


@router.post("/message/{message_id}", response_model=list[MemoryResponse])
async def extract_from_message(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Extract and persist memories from a stored message."""
    from agents.memory_agent import MemoryAgent

    msg = MessageRepository.get_by_id(db, message_id, current_user.id)
    if msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")

    agent = MemoryAgent()
    try:
        raw_memories = await agent.extract_memory(msg)
        saved = await agent.save_memories(
            memories=raw_memories,
            user_id=current_user.id,
            db=db,
            source_message_id=msg.message_id,
        )
    except Exception as exc:
        logger.error("Memory extraction for message %d failed: %s", message_id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return [_item_to_response(i) for i in saved]


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a memory item owned by the current user."""
    deleted = MemoryRepository.delete(db, memory_id=memory_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found.")
    return {"deleted": True, "id": memory_id}
