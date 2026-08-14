"""
Reply Agent

Generates suggested replies to messages using the configured LLM.
"""

from __future__ import annotations

import logging
from typing import Optional

from agents.base_agent import BaseAgent
from services.llm import LLMClient
from utils.prompts.reply import build_reply_prompt, build_improve_reply_prompt


logger = logging.getLogger(__name__)


class ReplyAgent(BaseAgent):
    """Generates context-aware suggested replies."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        super().__init__(
            agent_name="ReplyAgent",
            llm_client=llm_client,
        )

    async def generate_reply(
        self,
        recipient_name: str,
        email_content: str,
        context: Optional[str] = None,
        tone: str = "professional",
        language: str = "English",
        user_id: Optional[int] = None,
    ) -> dict:
        """
        Generate a suggested reply.

        Returns:
            {
                "reply": str,
                "tone": str
            }
        """

        prompt = build_reply_prompt(
            recipient_name=recipient_name,
            email_content=email_content,
            context=context,
            tone=tone,
            language=language,
        )

        raw = await self._call_llm(
            prompt,
            user_id=user_id,
        )

        # The reply agent returns plain text rather than requiring
        # a JSON response.
        reply = raw.strip() if raw else ""

        return {
            "reply": reply,
            "tone": tone,
        }

    async def improve_reply(
        self,
        original_email: str,
        reply_draft: str,
        user_id: Optional[int] = None,
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
        improved_text = await self._call_llm(prompt, user_id=user_id)
        return {"reply": improved_text.strip()}

    async def regenerate_reply(
        self,
        recipient_name: str,
        email_content: str,
        previous_reply: str,
        feedback: str,
        tone: str = "professional",
        language: str = "English",
        user_id: Optional[int] = None,
    ) -> dict:
        """
        Regenerate a reply using feedback on a previous suggestion.

        Uses the same request-specific LLM client configured on
        this agent.
        """

        prompt = f"""
You previously generated this reply:

{previous_reply}

The user provided this feedback:

{feedback}

Generate an improved reply to the following message.

Recipient:
{recipient_name}

Message:
{email_content}

Tone:
{tone}

Language:
{language}

Return only the improved reply text.
""".strip()

        raw = await self._call_llm(
            prompt,
            user_id=user_id,
        )

        reply = raw.strip() if raw else ""

        return {
            "reply": reply,
            "tone": tone,
        }