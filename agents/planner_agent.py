from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from agents.gmail_agent import GmailAgent
from agents.priority_agent import PriorityAgent
from agents.memory_agent import MemoryAgent
from agents.reply_agent import ReplyAgent

from models.message import Message
from utils.prompts import build_daily_briefing_prompt

logger = logging.getLogger(__name__)


class PlannerAgent(BaseAgent):

    """
    Executive planning agent.
    """

    def __init__(self) -> None:

        super().__init__(agent_name="PlannerAgent")

        self.gmail = GmailAgent()
        self.priority = PriorityAgent()
        self.memory = MemoryAgent()
        self.reply = ReplyAgent()

    # ==========================================================
    # Public API
    # ==========================================================

    def generate_daily_briefing(self) -> Dict[str, Any]:
        """
        Main entry point.
        """

        messages = self._collect_messages()

        return self.generate_plan(messages)

    def generate_plan(
        self,
        messages: List[Message],
    ) -> Dict[str, Any]:
        """
        Generate action plan.
        """

        priorities = self._collect_priorities(messages)

        memories = self._collect_memories(messages)

        replies = self._collect_replies(messages)

        context: Dict[str, Any] = {
            "messages": messages,
            "priorities": priorities,
            "memories": memories,
            "replies": replies,
        }

        prompt = self._build_prompt(context)

        response = self._call_llm(prompt)

        plan = self._parse_response(response)

        if not self._validate_plan(plan):
            logger.error(
                "%s: generated plan failed validation.",
                self.agent_name,
            )
            return {}

        return plan

    # ==========================================================
    # Data Collection
    # ==========================================================

    def _collect_messages(self) -> List[Message]:
        """
        Fetch today's messages.
        """

        # TODO: Confirm the exact GmailAgent method used to fetch
        # today's messages, then wire it up here, e.g.:
        # return self.gmail.get_todays_messages()
        raise NotImplementedError(
            "PlannerAgent._collect_messages: wire this up to GmailAgent's "
            "message-fetching method once its API is confirmed."
        )

    def _collect_priorities(
        self,
        messages: List[Message],
    ) -> List[Dict[str, Any]]:
        """
        Analyze priorities.
        """

        # TODO: Confirm the exact PriorityAgent method used to score or
        # rank messages, then wire it up here, e.g.:
        # return self.priority.analyze(messages)
        raise NotImplementedError(
            "PlannerAgent._collect_priorities: wire this up to "
            "PriorityAgent's analysis method once its API is confirmed."
        )

    def _collect_memories(
        self,
        messages: List[Message],
    ) -> List[Dict[str, Any]]:
        """
        Retrieve useful memories.
        """

        memories: List[Dict[str, Any]] = []

        for message in messages:
            memories.extend(self.memory.extract_memory(message))

        return memories

    def _collect_replies(
        self,
        messages: List[Message],
    ) -> List[Dict[str, Any]]:
        """
        Generate draft replies.
        """

        # TODO: Confirm the exact ReplyAgent method used to draft
        # replies for a message, then wire it up here, e.g.:
        # return [self.reply.draft_reply(message) for message in messages]
        raise NotImplementedError(
            "PlannerAgent._collect_replies: wire this up to ReplyAgent's "
            "reply-drafting method once its API is confirmed."
        )

    # ==========================================================
    # Prompt
    # ==========================================================

    def _build_prompt(
        self,
        context: Dict[str, Any],
    ) -> str:
        """
        Build planner prompt.
        """

        return build_daily_briefing_prompt(context)

    # ==========================================================
    # LLM
    # ==========================================================

    def _call_llm(
        self,
        prompt: str,
    ) -> str:
        """
        Generate executive briefing.
        """

        # TODO: Replace this with the actual BaseAgent LLM call.
        # Example (uncomment and adjust once BaseAgent's real API is known):
        # return self.run(prompt)
        raise NotImplementedError(
            "PlannerAgent._call_llm: wire this up to BaseAgent's LLM "
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
        Parse planner response.
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

        if isinstance(parsed, list):
            parsed = {"tasks": parsed}

        if not isinstance(parsed, dict):
            logger.error(
                "%s: parsed response is not a valid plan object.",
                self.agent_name,
            )
            return {}

        return parsed

    # ==========================================================
    # Validation
    # ==========================================================

    def _validate_plan(
        self,
        plan: Dict[str, Any],
    ) -> bool:
        """
        Validate planner output.
        """

        if not isinstance(plan, dict):
            return False

        if not plan:
            return False

        return True

    # ==========================================================
    # Recommendation Engine
    # ==========================================================

    def _rank_tasks(
        self,
        tasks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Rank tasks.
        """

        if not isinstance(tasks, list):
            return []

        return sorted(
            tasks,
            key=lambda task: task.get("priority", 0),
            reverse=True,
        )

    def _detect_risks(
        self,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Detect risks.
        """

        # Risk detection is semantic judgement performed by the LLM
        # inside the planner prompt/response, not by Python business
        # rules. This method is kept as a structural no-op so the
        # public API and pipeline shape are preserved.
        return []

    def _recommend_actions(
        self,
        context: Dict[str, Any],
    ) -> List[str]:
        """
        Recommend actions.
        """

        # Recommendation generation is semantic judgement performed by
        # the LLM inside the planner prompt/response, not by Python
        # business rules. This method is kept as a structural no-op so
        # the public API and pipeline shape are preserved.
        return []

    # ==========================================================
    # Future Features
    # ==========================================================

    def schedule_tasks(
        self,
        plan: Dict[str, Any],
    ) -> None:
        """
        Calendar integration.
        """

        raise NotImplementedError(
            "PlannerAgent.schedule_tasks: calendar integration is out of "
            "scope for this agent and will be implemented separately."
        )

    def export_plan(
        self,
        plan: Dict[str, Any],
    ) -> str:
        """
        Export briefing.
        """

        raise NotImplementedError(
            "PlannerAgent.export_plan: export functionality is out of "
            "scope for this agent and will be implemented separately."
        )