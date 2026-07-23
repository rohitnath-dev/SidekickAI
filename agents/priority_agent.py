from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from models.message import Message
from utils.prompts import build_priority_prompt

logger = logging.getLogger(__name__)


class PriorityAgent(BaseAgent):

    """
    Determines the importance and urgency
    of incoming messages.
    """

    def __init__(self) -> None:

        super().__init__(agent_name="PriorityAgent")

    # ==========================================================
    # Public API
    # ==========================================================

    def analyze(
        self,
        message: Message,
    ) -> Dict[str, Any]:
        """
        Main entry point.
        """

        prompt = self._build_prompt(message)

        response = self._call_llm(prompt)

        priority = self._parse_response(response)

        if not self._validate_priority(priority):
            logger.error(
                "%s: priority object failed validation.",
                self.agent_name,
            )
            return {}

        priority = dict(priority)

        priority["score"] = self._normalize_score(
            priority.get("score", 0)
        )

        return priority

    def analyze_batch(
        self,
        messages: List[Message],
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple messages.
        """

        priorities: List[Dict[str, Any]] = []

        for message in messages:
            priority = self.analyze(message)

            if priority:
                priorities.append(priority)

        return self._calculate_rank(priorities)

    # ==========================================================
    # Prompt
    # ==========================================================

    def _build_prompt(
        self,
        message: Message,
        context: Optional[str] = None,
    ) -> str:
        """
        Build priority prompt.
        """

        return build_priority_prompt(message, context)

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
            "PriorityAgent._call_llm: wire this up to BaseAgent's LLM "
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
        Parse LLM JSON response.
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
            if "priority" in parsed and isinstance(parsed["priority"], dict):
                parsed = parsed["priority"]

        if not isinstance(parsed, dict):
            logger.error(
                "%s: parsed response is not a valid priority object.",
                self.agent_name,
            )
            return {}

        return parsed

    # ==========================================================
    # Validation
    # ==========================================================

    def _validate_priority(
        self,
        priority: Dict[str, Any],
    ) -> bool:
        """
        Validate priority object.
        """

        if not isinstance(priority, dict):
            return False

        if not priority:
            return False

        required_fields = ("score",)

        for field in required_fields:
            if field not in priority:
                return False

        score = priority.get("score")

        if not isinstance(score, (int, float)):
            return False

        if isinstance(score, bool):
            return False

        return True

    # ==========================================================
    # Scoring
    # ==========================================================

    def _normalize_score(
        self,
        score: int,
    ) -> int:
        """
        Normalize priority score.
        """

        if not isinstance(score, (int, float)) or isinstance(score, bool):
            return 0

        normalized = int(round(score))

        if normalized < 0:
            return 0

        if normalized > 100:
            return 100

        return normalized

    def _calculate_rank(
        self,
        priorities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Rank messages.
        """

        if not isinstance(priorities, list):
            return []

        ranked = sorted(
            priorities,
            key=lambda priority: priority.get("score", 0),
            reverse=True,
        )

        for index, priority in enumerate(ranked, start=1):
            priority["rank"] = index

        return ranked

    # ==========================================================
    # Helpers
    # ==========================================================

    def sort_messages(
        self,
        priorities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Sort by priority.
        """

        if not isinstance(priorities, list):
            return []

        return sorted(
            priorities,
            key=lambda priority: priority.get("score", 0),
            reverse=True,
        )

    def filter_urgent(
        self,
        priorities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Return urgent messages.
        """

        if not isinstance(priorities, list):
            return []

        return [
            priority
            for priority in priorities
            if isinstance(priority, dict) and bool(priority.get("urgent"))
        ]

    def filter_requires_reply(
        self,
        priorities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Return reply-required messages.
        """

        if not isinstance(priorities, list):
            return []

        return [
            priority
            for priority in priorities
            if isinstance(priority, dict) and bool(priority.get("requires_reply"))
        ]

    # ==========================================================
    # Future Features
    # ==========================================================

    def learn_user_behavior(
        self,
        history: List[Dict[str, Any]],
    ) -> None:
        """
        Future personalization.
        """

        raise NotImplementedError(
            "PriorityAgent.learn_user_behavior: personalization is out of "
            "scope for this agent and will be implemented separately."
        )

    def update_rules(
        self,
        rules: Dict[str, Any],
    ) -> None:
        """
        Future custom priority rules.
        """

        raise NotImplementedError(
            "PriorityAgent.update_rules: custom rule configuration is out "
            "of scope for this agent and will be implemented separately."
        )