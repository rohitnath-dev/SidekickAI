from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from models.message import Message
from utils.prompts import (
    build_reply_prompt,
    build_improve_reply_prompt,
)

logger = logging.getLogger(__name__)


class ReplyAgent(BaseAgent):

    """
    AI reply generation agent.
    """

    def __init__(self) -> None:

        super().__init__(agent_name="ReplyAgent")

    # ==========================================================
    # Public API
    # ==========================================================

    def generate_reply(
        self,
        message: Message,
        context: Optional[str] = None,
        tone: str = "professional",
        language: str = "English",
    ) -> Dict[str, Any]:
        """
        Generate a reply.
        """

        prompt = self._build_prompt(message, context, tone, language)

        response = self._call_llm(prompt)

        reply = self._parse_response(response)

        if not self._validate_reply(reply):
            logger.error(
                "%s: generated reply failed validation.",
                self.agent_name,
            )
            return {}

        reply = dict(reply)

        reply["reply"] = self._clean_reply(reply.get("reply", ""))

        reply["reply"] = self._apply_style(reply["reply"], tone)

        if not self._check_completeness(reply["reply"]):
            logger.warning(
                "%s: generated reply did not pass completeness check.",
                self.agent_name,
            )

        return reply

    def improve_reply(
        self,
        original_email: str,
        draft: str,
    ) -> Dict[str, Any]:
        """
        Improve an existing draft.
        """

        prompt = self._build_improvement_prompt(original_email, draft)

        response = self._call_llm(prompt)

        reply = self._parse_response(response)

        if not self._validate_reply(reply):
            logger.error(
                "%s: improved reply failed validation.",
                self.agent_name,
            )
            return {}

        reply = dict(reply)

        reply["reply"] = self._clean_reply(reply.get("reply", ""))

        return reply

    def regenerate_reply(
        self,
        message: Message,
    ) -> Dict[str, Any]:
        """
        Generate another version.
        """

        return self.generate_reply(message)

    # ==========================================================
    # Prompt
    # ==========================================================

    def _build_prompt(
        self,
        message: Message,
        context: Optional[str],
        tone: str,
        language: str,
    ) -> str:
        """
        Build reply prompt.
        """

        return build_reply_prompt(message, context, tone, language)

    def _build_improvement_prompt(
        self,
        original_email: str,
        draft: str,
    ) -> str:
        """
        Build improvement prompt.
        """

        return build_improve_reply_prompt(original_email, draft)

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
            "ReplyAgent._call_llm: wire this up to BaseAgent's LLM "
            "invocation method once its API is confirmed."
        )

    # ==========================================================
    # Parsing
    # ==========================================================

    def _parse_response(
        self,
        response: str,
    ) -> Dict[str, Any]:
        """
        Parse reply response.
        """

        if not response or not isinstance(response, str):
            logger.warning(
                "%s: empty or invalid LLM response, nothing to parse.",
                self.agent_name,
            )
            return {}

        cleaned = response.strip()

        if not cleaned:
            logger.warning(
                "%s: empty LLM response after stripping whitespace.",
                self.agent_name,
            )
            return {}

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
            return {}

        try:
            parsed = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.error(
                "%s: failed to parse LLM response as JSON: %s",
                self.agent_name,
                exc,
            )
            return {}

        if isinstance(parsed, dict):
            if "reply" in parsed and isinstance(parsed["reply"], dict):
                parsed = parsed["reply"]

        if not isinstance(parsed, dict):
            logger.error(
                "%s: parsed response is not a valid reply object.",
                self.agent_name,
            )
            return {}

        return parsed

    # ==========================================================
    # Validation
    # ==========================================================

    def _validate_reply(
        self,
        reply: Dict[str, Any],
    ) -> bool:
        """
        Validate generated reply.
        """

        if not isinstance(reply, dict):
            return False

        if not reply:
            return False

        if "reply" not in reply:
            return False

        reply_text = reply.get("reply")

        if not isinstance(reply_text, str):
            return False

        if not reply_text.strip():
            return False

        return True

    # ==========================================================
    # Post Processing
    # ==========================================================

    def _clean_reply(
        self,
        reply: str,
    ) -> str:
        """
        Clean formatting.
        """

        if not isinstance(reply, str):
            return ""

        return " ".join(reply.split())

    def _apply_style(
        self,
        reply: str,
        tone: str,
    ) -> str:
        """
        Apply tone adjustments.
        """

        # Tone is applied by the LLM through the prompt. Python only
        # performs minimal, non-semantic formatting adjustments here
        # so the public API and pipeline shape are preserved.
        if not isinstance(reply, str):
            return ""

        return reply.strip()

    def _check_completeness(
        self,
        reply: str,
    ) -> bool:
        """
        Ensure reply answers
        the original email.
        """

        if not isinstance(reply, str):
            return False

        return bool(reply.strip())

    # ==========================================================
    # Future Features
    # ==========================================================

    def learn_user_style(
        self,
        examples: List[str],
    ) -> None:
        """
        Learn writing style.
        """

        raise NotImplementedError(
            "ReplyAgent.learn_user_style: style learning is out of scope "
            "for this agent and will be implemented separately."
        )

    def score_reply(
        self,
        reply: str,
    ) -> float:
        """
        Quality score.
        """

        raise NotImplementedError(
            "ReplyAgent.score_reply: quality scoring is out of scope for "
            "this agent and will be implemented separately."
        )

    def translate_reply(
        self,
        reply: str,
        language: str,
    ) -> str:
        """
        Translate reply.
        """

        raise NotImplementedError(
            "ReplyAgent.translate_reply: translation is out of scope for "
            "this agent and will be implemented separately."
        )