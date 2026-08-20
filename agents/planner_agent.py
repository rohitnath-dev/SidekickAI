"""
Planner Agent

Generates executive daily briefings by combining recent messages,
priority analysis, and (optionally) calendar data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from agents.base_agent import BaseAgent
from models.message import Message, MessageSource
from services.llm import LLMClient
from utils.prompts.planner import build_daily_briefing_prompt


logger = logging.getLogger(__name__)


class PlannerAgent(BaseAgent):
    """Creates daily briefing summaries for the user."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        super().__init__(
            agent_name="PlannerAgent",
            llm_client=llm_client,
        )

    async def generate_daily_briefing(
        self,
        user_id: str | int,
        db: Session,
        creds=None,
    ) -> dict:
        """
        Generate an executive daily briefing.

        - Fetches recent messages from DB (last 24 h, limit 50).
        - Analyses high-priority messages using PriorityAgent.
        - Builds email summary strings from the top messages.
        - Calls the configured LLM with the daily briefing prompt.
        - Returns parsed JSON dict.
        """
        # Dynamically fetch user AI config to strictly use their API key and prevent any fallbacks
        from models.ai_config import UserAIConfig
        from services.llm import LLMClient

        config = db.query(UserAIConfig).filter_by(user_id=user_id).first()
        if not config:
            raise ValueError(f"No AI configuration found for user_id={user_id}")
        if config.provider == "openrouter" and (not config.api_key or not config.api_key.strip()):
            raise ValueError(f"No OpenRouter API key configured for user_id={user_id}")

        self.llm = LLMClient(
            provider=config.provider,
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            user_id=user_id,
        )
        # Strictly override to avoid any fallback inside LLMClient
        if config.provider == "openrouter":
            self.llm.openrouter_api_key = config.api_key or ""

        # Lazy import to avoid circular dependencies.
        from agents.priority_agent import PriorityAgent

        # IMPORTANT:
        # Use the same request-specific LLM client that PlannerAgent
        # itself is using.
        priority_agent = PriorityAgent(
            llm_client=self.llm,
        )

        today_date = datetime.utcnow().strftime(
            "%Y-%m-%d"
        )

        try:
            # ----------------------------------------------------------
            # 1. Fetch recent messages
            # ----------------------------------------------------------

            cutoff = (
                datetime.utcnow()
                - timedelta(hours=24)
            )

            messages: list[Message] = (
                db.query(Message)
                .filter(
                    Message.user_id == user_id,
                    Message.received_at >= cutoff,
                )
                .order_by(
                    Message.received_at.desc()
                )
                .limit(50)
                .all()
            )

            # ----------------------------------------------------------
            # 2. Prioritise messages
            # ----------------------------------------------------------

            high_priority_items: list[dict] = []
            email_summaries: list[str] = []

            if messages:

                priority_results = (
                    await priority_agent.analyze_batch(
                        messages
                    )
                )

                # Pair priority results correctly by message ID.
                pri_map = {
                    pri.get("message_id"): pri
                    for pri in priority_results
                    if pri.get("message_id")
                }

                # Build summary strings for top 10 messages.
                for i, msg in enumerate(messages):

                    if i >= 10:
                        break

                    subject = (
                        msg.subject
                        or "(no subject)"
                    )

                    sender = (
                        msg.sender
                        or "unknown"
                    )

                    pri = pri_map.get(
                        msg.message_id,
                        {},
                    )

                    score = pri.get(
                        "score",
                        50,
                    )

                    snippet = (
                        msg.body[:200]
                        .replace("\n", " ")
                        if msg.body
                        else ""
                    )

                    email_summaries.append(
                        f"- [{score}/100] "
                        f"From: {sender} | "
                        f"Subject: {subject} | "
                        f"{snippet}"
                    )

                # Collect high-priority messages.
                for msg in messages:

                    pri = pri_map.get(
                        msg.message_id,
                        {},
                    )

                    if pri.get(
                        "score",
                        0,
                    ) >= 70:

                        high_priority_items.append(
                            f"- "
                            f"{msg.subject or '(no subject)'} "
                            f"from {msg.sender} "
                            f"[score={pri.get('score', 0)}, "
                            f"reason={pri.get('reason', '')}]"
                        )

            emails_summary = (
                "\n".join(email_summaries)
                if email_summaries
                else "No recent emails."
            )

            high_priority_str = (
                "\n".join(
                    high_priority_items
                )
                if high_priority_items
                else "None."
            )

            # ----------------------------------------------------------
            # 3. Build briefing prompt
            # ----------------------------------------------------------

            prompt = build_daily_briefing_prompt(
                today_date=today_date,
                emails_summary=emails_summary,
                calendar_summary="No calendar connected.",
                outstanding_items=None,
                high_priority_messages=high_priority_str,
            )

            self.logger.info(
                "PlannerAgent: Prompt prepared. "
                "Character count = %d",
                len(prompt),
            )

            # ----------------------------------------------------------
            # 4. Call configured LLM
            # ----------------------------------------------------------

            self.logger.info(
                "PlannerAgent: Requesting daily briefing "
                "from configured LLM provider=%s model=%s",
                getattr(
                    self.llm,
                    "provider",
                    "unknown",
                ),
                getattr(
                    self.llm,
                    "_active_model",
                    lambda: "unknown",
                )(),
            )

            raw = await self._call_llm(
                prompt,
                user_id=user_id,
            )

            self.logger.info(
                "PlannerAgent: Received raw LLM response "
                "(first 250 chars): %s",
                raw[:250] if raw else "",
            )

            result = self.parse_json_response(
                raw
            )

            if (
                not isinstance(result, dict)
                or "executive_summary" not in result
            ):
                return self._fallback_briefing(
                    today_date,
                    len(messages),
                )

            return result

        except Exception as exc:

            self.logger.error(
                "Daily briefing generation failed: %s",
                exc,
                exc_info=True,
            )

            return self._fallback_briefing(
                today_date,
                0,
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fallback_briefing(
        self,
        today_date: str,
        message_count: int,
    ) -> dict:
        """Return a minimal fallback briefing when LLM parsing fails."""

        msg_word = (
            "message"
            if message_count == 1
            else "messages"
        )

        if message_count > 0:
            summary = (
                f"You have {message_count} "
                f"{msg_word} in the last 24 hours. "
                "AI briefing generation failed — "
                "please try again."
            )
        else:
            summary = (
                "No new messages in the last 24 hours. "
                "AI briefing generation failed."
            )

        return {
            "date": today_date,
            "executive_summary": summary,
            "critical_items": [],
            "pending_work": [],
            "upcoming_deadlines": [],
            "recommended_priorities": [],
            "risks": [],
            "next_actions": [
                "Review recent emails manually."
            ],
        }