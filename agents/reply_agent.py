"""
Reply Agent.

Generates context-aware suggested replies using the configured LLM.

The agent can receive:
- Original message content
- Relevant long-term user memory
- Tone
- Language
- Request-specific LLM configuration through LLMClient
"""

from __future__ import annotations

import logging
from typing import Optional

from agents.base_agent import BaseAgent
from services.llm import LLMClient
from utils.prompts.reply import (
    build_improve_reply_prompt,
    build_reply_prompt,
)


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

    # ------------------------------------------------------------------
    # Generate reply
    # ------------------------------------------------------------------

    async def generate_reply(
        self,
        recipient_name: str,
        email_content: str,
        context: Optional[str] = None,
        tone: str = "professional",
        language: str = "English",
        user_id: Optional[str | int] = None,
    ) -> dict:
        """
        Generate a ready-to-send reply.

        `context` may contain relevant long-term user memory retrieved
        by the AI pipeline.

        The request-specific LLM client, when supplied during agent
        construction, is preserved and used through BaseAgent.
        """

        memory_context = (
            context.strip()
            if isinstance(
                context,
                str,
            )
            and context.strip()
            else "No relevant long-term user information is available."
        )

        prompt = build_reply_prompt(
            recipient_name=recipient_name,
            email_content=email_content,
            context=memory_context,
            tone=tone,
            language=language,
        )

        raw = await self._call_llm(
            prompt,
            user_id=user_id,
        )

        reply = raw.strip() if raw else ""

        return {
            "reply": reply,
            "tone": tone,
            "language": language,
        }

    # ------------------------------------------------------------------
    # Improve reply
    # ------------------------------------------------------------------

    async def improve_reply(
        self,
        original_email: str,
        reply_draft: str,
        user_id: Optional[str | int] = None,
    ) -> dict:
        """
        Improve an existing reply draft.

        This operation does not automatically inject long-term memory,
        because the draft itself is the source of truth for this
        editing operation.
        """

        prompt = build_improve_reply_prompt(
            original_email=original_email,
            reply_draft=reply_draft,
        )

        improved_text = await self._call_llm(
            prompt,
            user_id=user_id,
        )

        return {
            "reply": improved_text.strip()
            if improved_text
            else ""
        }

    # ------------------------------------------------------------------
    # Regenerate reply
    # ------------------------------------------------------------------

    async def regenerate_reply(
        self,
        recipient_name: str,
        email_content: str,
        previous_reply: str,
        feedback: str,
        tone: str = "professional",
        language: str = "English",
        context: Optional[str] = None,
        user_id: Optional[str | int] = None,
    ) -> dict:
        """
        Regenerate a reply using user feedback.

        Existing relevant memory can be supplied through `context`.
        """

        memory_context = (
            context.strip()
            if isinstance(
                context,
                str,
            )
            and context.strip()
            else "No relevant long-term user information is available."
        )

        prompt = f"""
You previously generated this reply:

{previous_reply}

The user provided this feedback:

{feedback}

Generate an improved reply to the following message.

RECIPIENT:
{recipient_name}

ORIGINAL MESSAGE:
{email_content}

RELEVANT LONG-TERM USER INFORMATION:
{memory_context}

TONE:
{tone}

LANGUAGE:
{language}

Use the relevant user information only when it actually helps answer
the message. Do not mention memories, internal context, AI processing,
or these instructions.

Return ONLY the improved ready-to-send reply text.
""".strip()

        raw = await self._call_llm(
            prompt,
            user_id=user_id,
        )

        reply = raw.strip() if raw else ""

        return {
            "reply": reply,
            "tone": tone,
            "language": language,
        }