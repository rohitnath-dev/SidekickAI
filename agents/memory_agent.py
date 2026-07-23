from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from models.message import Message
from prompts.prompt_engine import build_memory_prompt

logger = logging.getLogger(__name__)


class MemoryAgent(BaseAgent):

    """
    Extracts useful long-term memories
    from communications.
    """

    def __init__(self) -> None:

        super().__init__(
            agent_name="MemoryAgent"
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def extract_memory(
        self,
        message: Message,
    ) -> List[Dict[str, Any]]:
        """
        Main entry point.
        """

        text = getattr(message, "text", None)

        if text is None:
            text = getattr(message, "body", None)

        if not text:
            logger.warning(
                "%s: message has no extractable text.",
                self.agent_name,
            )
            return []

        return self.extract_from_text(text)

    def extract_from_text(
        self,
        text: str,
    ) -> List[Dict[str, Any]]:
        """
        Extract memories directly
        from raw text.
        """

        if not text or not text.strip():
            logger.warning(
                "%s: empty text passed to extract_from_text.",
                self.agent_name,
            )
            return []

        prompt = self._build_prompt(text)

        response = self._call_llm(prompt)

        memories = self._parse_response(response)

        memories = self._validate_schema(memories)

        memories = self._normalize(memories)

        memories = self._remove_duplicates(memories)

        memories = self._sort_by_confidence(memories)

        return memories

    # ==========================================================
    # Prompt
    # ==========================================================

    def _build_prompt(
        self,
        text: str,
    ) -> str:
        """
        Construct memory prompt.
        """

        return build_memory_prompt(text)

    # ==========================================================
    # LLM
    # ==========================================================

    def _call_llm(
        self,
        prompt: str,
    ) -> str:
        """
        Send prompt to LLM.
        """

        # TODO: Replace this with the actual BaseAgent LLM call.
        # Example (uncomment and adjust once BaseAgent's real API is known):
        # return self.run(prompt)
        raise NotImplementedError(
            "MemoryAgent._call_llm: wire this up to BaseAgent's LLM "
            "invocation method once its API is confirmed."
        )

    # ==========================================================
    # Parsing
    # ==========================================================

    def _parse_response(
        self,
        response: str,
    ) -> List[Dict[str, Any]]:
        """
        Parse JSON response.
        """

        if not response or not isinstance(response, str):
            logger.warning(
                "%s: empty or invalid LLM response, nothing to parse.",
                self.agent_name,
            )
            return []

        cleaned = response.strip()

        if not cleaned:
            logger.warning(
                "%s: empty LLM response after stripping whitespace.",
                self.agent_name,
            )
            return []

        fenced_match = re.match(
            r"^```(?:json)?\s*(.*?)\s*```$",
            cleaned,
            flags=re.DOTALL,
        )

        if fenced_match:
            cleaned = fenced_match.group(1).strip()

        if not cleaned:
            logger.warning(
                "%s: empty content after removing markdown fence.",
                self.agent_name,
            )
            return []

        try:
            parsed = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.error(
                "%s: failed to parse LLM response as JSON: %s",
                self.agent_name,
                exc,
            )
            return []

        if isinstance(parsed, dict):
            parsed = parsed.get("memories", [])

        if not isinstance(parsed, list):
            logger.error(
                "%s: parsed response is not a list of memories.",
                self.agent_name,
            )
            return []

        return parsed

    # ==========================================================
    # Validation
    # ==========================================================

    def _validate_memory(
        self,
        memory: Dict[str, Any],
    ) -> bool:
        """
        Validate one memory object.
        """

        if not isinstance(memory, dict):
            return False

        required_fields = ("content", "confidence")

        for field in required_fields:
            if field not in memory:
                return False

        if not isinstance(memory.get("content"), str):
            return False

        if not memory["content"].strip():
            return False

        confidence = memory.get("confidence")

        if not isinstance(confidence, (int, float)):
            return False

        if isinstance(confidence, bool):
            return False

        if confidence < 0 or confidence > 1:
            return False

        return True

    def _validate_schema(
        self,
        memories: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Validate all memories.
        """

        if not isinstance(memories, list):
            return []

        return [
            memory
            for memory in memories
            if self._validate_memory(memory)
        ]

    # ==========================================================
    # Filtering
    # ==========================================================

    def _filter_low_value(
        self,
        memories: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Remove useless memories.
        """

        # Business-level judgement of what counts as "low value" is
        # the LLM's responsibility, not Python's. This method is kept
        # as a structural no-op so the pipeline shape and public API
        # are preserved.
        return memories

    def _remove_duplicates(
        self,
        memories: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate memories.
        """

        best_by_key: Dict[tuple, Dict[str, Any]] = {}
        order: List[tuple] = []

        for memory in memories:
            memory_type = memory.get("type", "")
            if not isinstance(memory_type, str):
                memory_type = ""

            content = memory.get("content", "")
            if not isinstance(content, str):
                content = ""

            key = (memory_type, content.strip().lower())

            confidence = memory.get("confidence", 0)
            if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
                confidence = 0

            if key not in best_by_key:
                best_by_key[key] = memory
                order.append(key)
            else:
                existing_confidence = best_by_key[key].get("confidence", 0)
                if not isinstance(existing_confidence, (int, float)) or isinstance(existing_confidence, bool):
                    existing_confidence = 0

                if confidence > existing_confidence:
                    best_by_key[key] = memory

        return [best_by_key[key] for key in order]

    # ==========================================================
    # Post Processing
    # ==========================================================

    def _normalize(
        self,
        memories: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Normalize values.
        """

        normalized: List[Dict[str, Any]] = []

        for memory in memories:
            normalized_memory = dict(memory)

            content = normalized_memory.get("content", "")
            if isinstance(content, str):
                normalized_memory["content"] = " ".join(content.split())

            confidence = normalized_memory.get("confidence")
            if isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
                normalized_memory["confidence"] = float(confidence)

            normalized.append(normalized_memory)

        return normalized

    def _sort_by_confidence(
        self,
        memories: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Highest confidence first.
        """

        return sorted(
            memories,
            key=lambda memory: memory.get("confidence", 0),
            reverse=True,
        )

    # ==========================================================
    # Future Features
    # ==========================================================

    def save_memory(
        self,
        memories: List[Dict[str, Any]],
    ) -> None:
        """
        Save into database.
        Future implementation.
        """

        raise NotImplementedError(
            "MemoryAgent.save_memory: persistence is out of scope for "
            "this agent and will be implemented by a repository layer."
        )

    def search_memory(
        self,
        query: str,
    ) -> List[Dict[str, Any]]:
        """
        Search stored memories.
        Future implementation.
        """

        raise NotImplementedError(
            "MemoryAgent.search_memory: persistence is out of scope for "
            "this agent and will be implemented by a repository layer."
        )

    def delete_memory(
        self,
        memory_id: str,
    ) -> bool:
        """
        Delete memory.
        Future implementation.
        """

        raise NotImplementedError(
            "MemoryAgent.delete_memory: persistence is out of scope for "
            "this agent and will be implemented by a repository layer."
        )

    def update_memory(
        self,
        memory_id: str,
        updates: Dict[str, Any],
    ) -> bool:
        """
        Update memory.
        Future implementation.
        """

        raise NotImplementedError(
            "MemoryAgent.update_memory: persistence is out of scope for "
            "this agent and will be implemented by a repository layer."
        )