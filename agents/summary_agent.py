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
    build_thread_summary_prompt,
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
        email_content: str,
        context: str | None = None,
        user_id: Optional[str | int] = None,
    ) -> dict:
        """
        Generate a structured JSON summary of an email.

        Args:
            email_content: The raw email body text.
            context: Optional additional context for the LLM.
            user_id: Optional user ID for custom AI settings.

        Returns:
            Parsed summary dict or {} on failure.
        """
        prompt = build_summary_prompt(email_content, context)
        raw = await self._call_llm(prompt, user_id=user_id)
        result = self.parse_json_response(raw)

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
            "summary": result.get("summary", ""),
            "sentiment": result.get("sentiment", ""),
            "category": result.get("category", ""),
        }

    async def summarize_thread(self, thread_content: str, user_id: Optional[str | int] = None) -> dict:
        """
        Generate a structured JSON summary of an email thread.

        Args:
            thread_content: The full thread text.
            user_id: Optional user ID for custom AI settings.

        Returns:
            Parsed thread summary dict or {} on failure.
        """
        prompt = build_thread_summary_prompt(thread_content)
        raw = await self._call_llm(prompt, user_id=user_id)
        result = self.parse_json_response(raw)
        if not isinstance(result, dict):
            self.logger.warning(
                "SummaryAgent.summarize_thread: "
                "invalid LLM response"
            )
            return {}
        return result

    async def extract_action_items(self, email_content: str, user_id: Optional[str | int] = None) -> dict:
        """
        Extract action items from an email.

        Args:
            email_content: The raw email body text.
            user_id: Optional user ID for custom AI settings.

        Returns:
            Parsed action items dict or {} on failure.
        """
        prompt = build_action_items_prompt(email_content)
        raw = await self._call_llm(prompt, user_id=user_id)
        result = self.parse_json_response(raw)

        if not isinstance(result, dict):
            self.logger.warning(
                "SummaryAgent.extract_action_items: "
                "invalid LLM response"
            )
            return {
                "action_items": [],
            }

        action_items = result.get("action_items", [])
        if not isinstance(action_items, list):
            action_items = []

        return {
            "action_items": action_items,
        }
