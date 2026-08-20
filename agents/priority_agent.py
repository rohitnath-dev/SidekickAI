"""
Priority Agent

Analyses messages for urgency and importance using the configured LLM.
"""

from __future__ import annotations

import logging
from typing import Optional

from agents.base_agent import BaseAgent
from services.llm import LLMClient
from models.message import Message
from utils.prompts.priority import build_priority_prompt


logger = logging.getLogger(__name__)


_FALLBACK = {
    "score": 50,
    "priority_level": "medium",
    "requires_reply": False,
    "reason": "Unable to classify",
}


class PriorityAgent(BaseAgent):
    """Classifies message priority using LLM analysis."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        super().__init__(
            agent_name="PriorityAgent",
            llm_client=llm_client,
        )

    async def analyze(self, message: Message) -> dict:
        """
        Analyse a single message and return a priority dict.

        Returns:
            Dict with at minimum:
            - score (0-100 int)
            - priority_level
            - requires_reply
            - reason
        """
        # Dynamically fetch user AI config to strictly use their API key and prevent any fallbacks
        from database import SessionLocal
        from models.ai_config import UserAIConfig
        from services.llm import LLMClient

        BLOCKED_USER_IDS = {"user_3D8FF09H5k8W7d93riQ9tCJFHED"}
        BLOCKED_API_KEYS = {
            "sk-or-v1-ca6bffe906dd48684da0f99e3d16b8a1d466c94bf1a83fbc5f1e7071e0711b14a"
        }

        db = SessionLocal()
        try:
            config = None
            user_id = message.user_id
            if user_id in BLOCKED_USER_IDS:
                self.logger.warning("PriorityAgent: user_id %s is blocked. Safely skipping.", user_id)
                return {"priority_level": "medium", "requires_reply": False, "score": 0.5, "reason": "Blocked user ID"}

            if user_id:
                config = db.query(UserAIConfig).filter_by(user_id=user_id).first()
            
            if not config:
                # Fall back to shared system-level defaults instead of randomly picking a user's personal key
                self.llm = LLMClient(user_id=None)
            else:
                if config.user_id in BLOCKED_USER_IDS or config.api_key in BLOCKED_API_KEYS:
                    self.logger.warning("PriorityAgent: config user_id=%s or api_key=%s is blocked. Safely skipping.", config.user_id, config.api_key)
                    return {"priority_level": "medium", "requires_reply": False, "score": 0.5, "reason": "Blocked config"}

                if config.provider == "openrouter" and (not config.api_key or not config.api_key.strip()):
                    self.logger.warning("PriorityAgent: OpenRouter config has empty API key. Safely skipping.")
                    return {"priority_level": "medium", "requires_reply": False, "score": 0.5, "reason": "Empty API key"}

                self.llm = LLMClient(
                    provider=config.provider,
                    api_key=config.api_key,
                    base_url=config.base_url,
                    model=config.model,
                    user_id=user_id,
                )
                # Strictly override to avoid any fallback inside LLMClient
                if config.provider == "openrouter":
                    self.llm.openrouter_api_key = config.api_key or ""
        finally:
            db.close()

        message_content = message.to_context_string()

        prompt = build_priority_prompt(
            message_content,
            context=None,
        )

        raw = await self._call_llm(
            prompt,
            user_id=message.user_id,
        )

        result = self.parse_json_response(raw)

        if not isinstance(result, dict) or "score" not in result:
            self.logger.warning(
                "PriorityAgent.analyze: parse failure for message_id=%s",
                message.message_id,
            )
            return _FALLBACK.copy()

        # --------------------------------------------------------------
        # Normalize score to 0-100 integer
        # --------------------------------------------------------------

        try:
            score = int(
                float(
                    result.get(
                        "score",
                        50,
                    )
                )
            )

            score = max(
                0,
                min(100, score),
            )

        except (TypeError, ValueError):
            score = 50

        result["score"] = score

        # --------------------------------------------------------------
        # Ensure required fields
        # --------------------------------------------------------------

        result.setdefault(
            "priority_level",
            "medium",
        )

        result.setdefault(
            "requires_reply",
            False,
        )

        result.setdefault(
            "reason",
            "",
        )

        return result

    async def analyze_batch(
        self,
        messages: list[Message],
    ) -> list[dict]:
        """
        Analyse multiple messages and return sorted results.

        Returns:
            List of priority dicts sorted by score descending.
            Each result contains a 1-based rank and message_id.
        """

        results: list[dict] = []

        for message in messages:
            try:
                priority_dict = await self.analyze(
                    message
                )

            except Exception as exc:
                self.logger.error(
                    "Failed to analyze message %s in batch: %s",
                    message.message_id,
                    exc,
                )

                priority_dict = _FALLBACK.copy()

            # Attach message ID for reference.
            priority_dict["message_id"] = (
                message.message_id
            )

            results.append(
                priority_dict
            )

        # Sort highest priority first.
        results.sort(
            key=lambda item: item.get(
                "score",
                0,
            ),
            reverse=True,
        )

        # Add rank.
        for rank, item in enumerate(
            results,
            start=1,
        ):
            item["rank"] = rank

        return results