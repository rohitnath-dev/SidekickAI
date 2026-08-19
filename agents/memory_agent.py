"""
Memory Agent.

Extracts durable user information from messages and persists it as
long-term memory.

Responsibilities:
- Extract durable facts using the LLM.
- Validate extracted memories.
- Prevent duplicate memories.
- Persist only useful memories.
- Retrieve stored memories.
- Delete user-owned memories.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from agents.base_agent import BaseAgent
from models.memory_item import MemoryItem
from models.message import Message
from repositories.memory_repo import MemoryRepository
from services.llm import LLMClient
from utils.prompts.memory import build_memory_prompt


logger = logging.getLogger(__name__)


class MemoryAgent(BaseAgent):
    """Extracts and manages long-term memory facts for users."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        super().__init__(
            agent_name="MemoryAgent",
            llm_client=llm_client,
        )

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    async def extract_memory(
        self,
        message: Message,
    ) -> list[dict]:
        """
        Extract durable facts from a stored message.

        Only information explicitly present in the message should be
        returned. Temporary or one-time information should be ignored.
        """

        message_content = message.to_context_string()

        prompt = build_memory_prompt(
            message_content
        )

        raw = await self._call_llm(
            prompt,
            user_id=message.user_id,
        )

        parsed = self.parse_json_response(
            raw
        )

        # --------------------------------------------------------------
        # Parse LLM response
        # --------------------------------------------------------------

        if isinstance(parsed, dict):
            memories_raw = parsed.get(
                "memories",
                [],
            )

        elif isinstance(parsed, list):
            memories_raw = parsed

        else:
            self.logger.warning(
                "MemoryAgent.extract_memory: "
                "unexpected LLM response shape"
            )
            return []

        if not isinstance(
            memories_raw,
            list,
        ):
            return []

        # --------------------------------------------------------------
        # Validate memories
        # --------------------------------------------------------------

        validated: list[dict] = []

        for item in memories_raw:
            if not isinstance(
                item,
                dict,
            ):
                continue

            content = item.get(
                "content"
            )

            confidence = item.get(
                "confidence"
            )

            # Content is mandatory.
            if (
                not isinstance(
                    content,
                    str,
                )
                or not content.strip()
            ):
                continue

            # Confidence is mandatory and must be numeric.
            if (
                not isinstance(
                    confidence,
                    (int, float),
                )
                or isinstance(
                    confidence,
                    bool,
                )
            ):
                continue

            # Clamp confidence to [0.0, 1.0].
            item["confidence"] = max(
                0.0,
                min(
                    1.0,
                    float(confidence),
                ),
            )

            # Normalize content before persistence.
            item["content"] = content.strip()

            validated.append(
                item
            )

        self.logger.info(
            "MemoryAgent.extract_memory: "
            "extracted %d valid memories for message_id=%s",
            len(validated),
            message.message_id,
        )

        return validated

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    async def save_memories(
        self,
        memories: list[dict],
        user_id: int,
        db: Session,
        source_message_id: Optional[str] = None,
    ) -> list[MemoryItem]:
        """
        Persist validated memories while preventing duplicates.

        Duplicate detection is scoped to the current user.
        """

        saved: list[MemoryItem] = []
        skipped_duplicates = 0

        for mem in memories:
            content = mem.get(
                "content"
            )

            if (
                not isinstance(
                    content,
                    str,
                )
                or not content.strip()
            ):
                continue

            content = content.strip()

            # ----------------------------------------------------------
            # Duplicate check
            # ----------------------------------------------------------

            existing = MemoryRepository.find_by_content(
                db=db,
                user_id=user_id,
                content=content,
            )

            if existing is not None:
                skipped_duplicates += 1

                self.logger.debug(
                    "MemoryAgent.save_memories: "
                    "skipping duplicate memory_id=%d "
                    "for user_id=%d",
                    existing.id,
                    user_id,
                )

                continue

            # ----------------------------------------------------------
            # Create memory through repository
            # ----------------------------------------------------------

            item = MemoryRepository.create(
                db=db,
                user_id=user_id,
                category=mem.get(
                    "category",
                    "personal",
                ),
                content=content,
                context=mem.get(
                    "context"
                ),
                related_person=mem.get(
                    "related_person"
                ),
                related_project=mem.get(
                    "related_project"
                ),
                retention_value=mem.get(
                    "retention_value",
                    "medium",
                ),
                confidence=float(
                    mem.get(
                        "confidence",
                        0.8,
                    )
                ),
                source_message_id=source_message_id,
            )

            saved.append(item)

        self.logger.info(
            "MemoryAgent.save_memories: "
            "saved=%d skipped_duplicates=%d user_id=%d",
            len(saved),
            skipped_duplicates,
            user_id,
        )

        return saved

    # ------------------------------------------------------------------
    # Extract + Save
    # ------------------------------------------------------------------

    async def extract_and_save_memory(
        self,
        message: Message,
        user_id: int,
        db: Session,
    ) -> list[MemoryItem]:
        """
        Extract memories from a message and persist useful memories.

        Duplicate memories are automatically ignored.
        """

        memories = await self.extract_memory(
            message
        )

        if not memories:
            return []

        return await self.save_memories(
            memories=memories,
            user_id=user_id,
            db=db,
            source_message_id=message.message_id,
        )

    # ------------------------------------------------------------------
    # Retrieve
    # ------------------------------------------------------------------

    async def get_memories(
        self,
        user_id: int,
        db: Session,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> list[MemoryItem]:
        """Retrieve stored memories belonging to the user."""

        return MemoryRepository.list_by_user(
            db=db,
            user_id=user_id,
            category=category,
            limit=limit,
        )

    async def get_relevant_memories(
        self,
        user_id: int,
        query: str,
        db: Session,
        limit: int = 10,
    ) -> list[MemoryItem]:
        """
        Retrieve memories relevant to the supplied message/context.
        """

        return MemoryRepository.find_relevant(
            db=db,
            user_id=user_id,
            query=query,
            limit=limit,
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search_memories(
        self,
        user_id: int,
        query: str,
        db: Session,
        limit: int = 20,
    ) -> list[MemoryItem]:
        """Search stored memories by content."""

        return MemoryRepository.search(
            db=db,
            user_id=user_id,
            query=query,
            limit=limit,
        )

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_memory(
        self,
        memory_id: int,
        user_id: int,
        db: Session,
    ) -> bool:
        """Delete a memory only if it belongs to the user."""

        deleted = MemoryRepository.delete(
            db=db,
            memory_id=memory_id,
            user_id=user_id,
        )

        if deleted:
            self.logger.info(
                "MemoryAgent.delete_memory: "
                "deleted memory_id=%d for user_id=%d",
                memory_id,
                user_id,
            )

        return deleted