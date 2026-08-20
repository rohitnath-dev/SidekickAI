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

        db = SessionLocal()
        try:
            config = db.query(UserAIConfig).filter_by(user_id=message.user_id).first()
            if not config:
                raise ValueError(f"No AI configuration found for user_id={message.user_id}")
            if config.provider == "openrouter" and (not config.api_key or not config.api_key.strip()):
                raise ValueError(f"No OpenRouter API key configured for user_id={message.user_id}")

            self.llm = LLMClient(
                provider=config.provider,
                api_key=config.api_key,
                base_url=config.base_url,
                model=config.model,
                user_id=message.user_id,
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