"""
Summary Agent

Generates email summaries, thread summaries, and action item lists
using the LLM via async prompts.
"""

from __future__ import annotations

import logging

from agents.base_agent import BaseAgent
from utils.prompts.summary import (
    build_action_items_prompt,
    build_summary_prompt,
    build_thread_summary_prompt,
)

logger = logging.getLogger(__name__)


class SummaryAgent(BaseAgent):
    """Generates summaries and extracts action items from emails."""

    def __init__(self) -> None:
        super().__init__(agent_name="SummaryAgent")

    async def generate_summary(
        self,
        email_content: str,
        context: str | None = None,
    ) -> dict:
        """
        Generate a structured JSON summary of an email.

        Args:
            email_content: The raw email body text.
            context: Optional additional context for the LLM.

        Returns:
            Parsed summary dict or {} on failure.
        """
        prompt = build_summary_prompt(email_content, context)
        raw = await self._call_llm(prompt)
        result = self.parse_json_response(raw)
        if not isinstance(result, dict):
            self.logger.warning("SummaryAgent.generate_summary: unexpected response type")
            return {}
        return result

    async def summarize_thread(self, thread_content: str) -> dict:
        """
        Generate a structured JSON summary of an email thread.

        Args:
            thread_content: The full thread text.

        Returns:
            Parsed thread summary dict or {} on failure.
        """
        prompt = build_thread_summary_prompt(thread_content)
        raw = await self._call_llm(prompt)
        result = self.parse_json_response(raw)
        if not isinstance(result, dict):
            self.logger.warning("SummaryAgent.summarize_thread: unexpected response type")
            return {}
        return result

    async def extract_action_items(self, email_content: str) -> dict:
        """
        Extract action items from an email.

        Args:
            email_content: The raw email body text.

        Returns:
            Parsed action items dict or {} on failure.
        """
        prompt = build_action_items_prompt(email_content)
        raw = await self._call_llm(prompt)
        result = self.parse_json_response(raw)
        if not isinstance(result, dict):
            self.logger.warning("SummaryAgent.extract_action_items: unexpected response type")
            return {}
        return result
