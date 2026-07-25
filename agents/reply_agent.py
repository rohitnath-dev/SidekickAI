"""
Reply Agent

Generates and improves email replies using the LLM.
"""

from __future__ import annotations

import logging
from typing import Optional

from agents.base_agent import BaseAgent
from utils.prompts.reply import build_improve_reply_prompt, build_reply_prompt

logger = logging.getLogger(__name__)


class ReplyAgent(BaseAgent):
    """Generates smart email replies and improvements via LLM."""

    def __init__(self) -> None:
        super().__init__(agent_name="ReplyAgent")

    async def generate_reply(
        self,
        recipient_name: str,
        email_content: str,
        context: Optional[str] = None,
        tone: str = "professional",
        language: str = "English",
    ) -> dict:
        """
        Generate a reply to an email.

        The LLM returns plain text (not JSON).

        Returns:
            {"reply": str, "tone": str, "language": str}
        """
        prompt = build_reply_prompt(
            recipient_name=recipient_name,
            email_content=email_content,
            context=context,
            tone=tone,
            language=language,
        )
        reply_text = await self._call_llm(prompt)
        return {
            "reply": reply_text.strip(),
            "tone": tone,
            "language": language,
        }

    async def improve_reply(
        self,
        original_email: str,
        reply_draft: str,
    ) -> dict:
        """
        Improve an existing reply draft.

        The LLM returns improved plain text.

        Returns:
            {"reply": str}
        """
        prompt = build_improve_reply_prompt(
            original_email=original_email,
            reply_draft=reply_draft,
        )
        improved_text = await self._call_llm(prompt)
        return {"reply": improved_text.strip()}

    async def regenerate_reply(
        self,
        recipient_name: str,
        email_content: str,
        context: Optional[str] = None,
        tone: str = "professional",
        language: str = "English",
    ) -> dict:
        """
        Regenerate a reply with higher temperature for variation.

        Returns:
            {"reply": str, "tone": str, "language": str}
        """
        prompt = build_reply_prompt(
            recipient_name=recipient_name,
            email_content=email_content,
            context=context,
            tone=tone,
            language=language,
        )
        reply_text = await self.llm.generate(prompt, temperature=0.7)
        return {
            "reply": reply_text.strip(),
            "tone": tone,
            "language": language,
        }
