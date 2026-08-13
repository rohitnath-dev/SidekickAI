"""
Memory Agent

Extracts long-term facts from messages and persists them
as MemoryItem records.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from agents.base_agent import BaseAgent
from models.memory_item import MemoryItem
from models.message import Message
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

    async def extract_memory(
        self,
        message: Message,
    ) -> list[dict]:
        """
        Extract memorable facts from a message.

        Args:
            message:
                A Message ORM object.

        Returns:
            List of validated memory dictionaries.
        """

        message_content = (
            message.to_context_string()
        )

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
        # Parse response
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

            if (
                "content" not in item
                or "confidence" not in item
            ):
                continue

            content = item.get(
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

            confidence = item.get(
                "confidence"
            )

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

    async def extract_and_save_memory(
        self,
        message: Message,
        user_id: int,
        db: Session,
    ) -> list[MemoryItem]:
        """
        Extract memories from a message and immediately persist them.

        This convenience method keeps extraction and persistence
        together while still using the configured request-specific
        LLM client.
        """

        memories = await self.extract_memory(
            message
        )

        if not memories:
            return []

        return await self._save_memories(
            memories=memories,
            user_id=user_id,
            db=db,
            source_message_id=message.message_id,
        )

    async def _save_memories(
        self,
        memories: list[dict],
        user_id: int,
        db: Session,
        source_message_id: Optional[str] = None,
    ) -> list[MemoryItem]:
        """
        Internal persistence helper.
        """

        saved: list[MemoryItem] = []

        for mem in memories:

            item = MemoryItem(
                user_id=user_id,
                category=mem.get(
                    "category",
                    "personal",
                ),
                content=mem["content"],
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

            db.add(item)
            saved.append(item)

        if saved:

            db.commit()

            for item in saved:
                db.refresh(item)

        self.logger.info(
            "MemoryAgent.save_memories: "
            "saved %d memories for user_id=%d",
            len(saved),
            user_id,
        )

        return saved

    async def save_memories(
        self,
        memories: list[dict],
        user_id: int,
        db: Session,
        source_message_id: Optional[str] = None,
    ) -> list[MemoryItem]:
        """
        Public method for persisting already-validated memories.
        """

        return await self._save_memories(
            memories=memories,
            user_id=user_id,
            db=db,
            source_message_id=source_message_id,
        )