"""
Summary Agent

Generates concise summaries, sentiment analysis, categories,
and action items from messages using the configured LLM.
"""

from __future__ import annotations

import logging
from typing import Optional

from agents.base_agent import BaseAgent
from services.llm import LLMClient
from utils.prompts.summary import (
    build_summary_prompt,
    build_action_items_prompt,
)


logger = logging.getLogger(__name__)


class SummaryAgent(BaseAgent):
    """Generates summaries and extracts action items."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        super().__init__(
            agent_name="SummaryAgent",
            llm_client=llm_client,
        )

    async def generate_summary(
        self,
        content: str,
    ) -> dict:
        """
        Generate a concise summary with sentiment and category.

        Returns:
            {
                "summary": str,
                "sentiment": str,
                "category": str
            }
        """

        prompt = build_summary_prompt(
            content,
        )

        raw = await self._call_llm(
            prompt,
        )

        result = self.parse_json_response(
            raw,
        )

        if not isinstance(result, dict):
            self.logger.warning(
                "SummaryAgent.generate_summary: "
                "invalid LLM response"
            )
            return {
                "summary": "",
                "sentiment": "",
                "category": "",
            }

        return {
            "summary": result.get(
                "summary",
                "",
            ),
            "sentiment": result.get(
                "sentiment",
                "",
            ),
            "category": result.get(
                "category",
                "",
            ),
        }

    async def extract_action_items(
        self,
        content: str,
    ) -> dict:
        """
        Extract actionable tasks from a message.

        Returns:
            {
                "action_items": [...]
            }
        """

        prompt = build_action_items_prompt(
            content,
        )

        raw = await self._call_llm(
            prompt,
        )

        result = self.parse_json_response(
            raw,
        )

        if not isinstance(result, dict):
            self.logger.warning(
                "SummaryAgent.extract_action_items: "
                "invalid LLM response"
            )
            return {
                "action_items": [],
            }

        action_items = result.get(
            "action_items",
            [],
        )

        if not isinstance(
            action_items,
            list,
        ):
            action_items = []

        return {
            "action_items": action_items,
        }