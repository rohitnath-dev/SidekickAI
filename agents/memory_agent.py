"""
Memory Agent

Extracts long-term facts from messages and persists them as MemoryItem records.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from agents.base_agent import BaseAgent
from models.memory_item import MemoryItem
from models.message import Message
from utils.prompts.memory import build_memory_prompt

logger = logging.getLogger(__name__)


class MemoryAgent(BaseAgent):
    """Extracts and manages long-term memory facts for users."""

    def __init__(self) -> None:
        super().__init__(agent_name="MemoryAgent")

    async def extract_memory(self, message: Message) -> list[dict]:
        """
        Extract memorable facts from a message.

        Args:
            message: A Message ORM object.

        Returns:
            List of validated memory dicts, each with at least
            'content' and 'confidence' keys.
        """
        message_content = message.to_context_string()
        prompt = build_memory_prompt(message_content)
        raw = await self._call_llm(prompt)
        parsed = self.parse_json_response(raw)

        # Expect {"memories": [...]}
        if isinstance(parsed, dict):
            memories_raw = parsed.get("memories", [])
        elif isinstance(parsed, list):
            memories_raw = parsed
        else:
            self.logger.warning("MemoryAgent.extract_memory: unexpected LLM response shape")
            return []

        if not isinstance(memories_raw, list):
            return []

        # Validate each memory
        validated: list[dict] = []
        for item in memories_raw:
            if not isinstance(item, dict):
                continue
            if "content" not in item or "confidence" not in item:
                continue
            if not isinstance(item.get("content"), str) or not item["content"].strip():
                continue
            confidence = item.get("confidence")
            if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
                continue
            # Clamp confidence to [0.0, 1.0]
            item["confidence"] = max(0.0, min(1.0, float(confidence)))
            validated.append(item)

        return validated

    async def save_memories(
        self,
        memories: list[dict],
        user_id: int,
        db: Session,
        source_message_id: Optional[str] = None,
    ) -> list[MemoryItem]:
        """
        Persist memory dicts as MemoryItem records in the database.

        Args:
            memories: List of validated memory dicts.
            user_id: The owning user's ID.
            db: SQLAlchemy session.
            source_message_id: Optional source message ID for traceability.

        Returns:
            List of saved MemoryItem ORM objects.
        """
        saved: list[MemoryItem] = []

        for mem in memories:
            item = MemoryItem(
                user_id=user_id,
                category=mem.get("category", "personal"),
                content=mem["content"],
                context=mem.get("context"),
                related_person=mem.get("related_person"),
                related_project=mem.get("related_project"),
                retention_value=mem.get("retention_value", "medium"),
                confidence=float(mem.get("confidence", 0.8)),
                source_message_id=source_message_id,
            )
            db.add(item)
            saved.append(item)

        if saved:
            db.commit()
            for item in saved:
                db.refresh(item)

        self.logger.info(
            "MemoryAgent.save_memories: saved %d memories for user_id=%d",
            len(saved),
            user_id,
        )
        return saved

    async def get_memories(
        self,
        user_id: int,
        db: Session,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> list[MemoryItem]:
        """
        Retrieve stored memories for a user.

        Args:
            user_id: The user's ID.
            db: SQLAlchemy session.
            category: Optional category filter.
            limit: Maximum number of results.

        Returns:
            List of MemoryItem objects sorted by confidence descending.
        """
        query = db.query(MemoryItem).filter_by(user_id=user_id)
        if category:
            query = query.filter_by(category=category)
        return (
            query.order_by(MemoryItem.confidence.desc())
            .limit(limit)
            .all()
        )

    async def delete_memory(
        self,
        memory_id: int,
        user_id: int,
        db: Session,
    ) -> bool:
        """
        Delete a memory item if it belongs to the given user.

        Returns:
            True if deleted, False if not found or unauthorized.
        """
        item = (
            db.query(MemoryItem)
            .filter_by(id=memory_id, user_id=user_id)
            .first()
        )
        if item is None:
            return False

        db.delete(item)
        db.commit()
        self.logger.info(
            "MemoryAgent.delete_memory: deleted memory_id=%d for user_id=%d",
            memory_id,
            user_id,
        )
        return True
