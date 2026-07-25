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
from utils.prompts.planner import build_daily_briefing_prompt

logger = logging.getLogger(__name__)


class PlannerAgent(BaseAgent):
    """Creates daily briefing summaries for the user."""

    def __init__(self) -> None:
        super().__init__(agent_name="PlannerAgent")

    async def generate_daily_briefing(
        self,
        user_id: int,
        db: Session,
        creds=None,
    ) -> dict:
        """
        Generate an executive daily briefing.

        - Fetches recent messages from DB (last 24 h, limit 50).
        - Analyses high-priority ones using PriorityAgent.
        - Builds email summary string from top messages.
        - Calls the LLM with the daily briefing prompt.
        - Returns parsed JSON dict.

        Args:
            user_id: The user's ID.
            db: SQLAlchemy session.
            creds: Optional Google credentials (unused here; reserved for
                   calendar integration).

        Returns:
            Parsed briefing dict or a fallback dict on failure.
        """
        # Lazy import to avoid circular dependencies
        from agents.priority_agent import PriorityAgent

        priority_agent = PriorityAgent()

        # ---- 1. Fetch recent messages --------------------------------
        cutoff = datetime.utcnow() - timedelta(hours=24)
        messages: list[Message] = (
            db.query(Message)
            .filter(
                Message.user_id == user_id,
                Message.received_at >= cutoff,
            )
            .order_by(Message.received_at.desc())
            .limit(50)
            .all()
        )

        # ---- 2. Prioritise messages ----------------------------------
        high_priority_items: list[dict] = []
        email_summaries: list[str] = []

        if messages:
            priority_results = await priority_agent.analyze_batch(messages)

            # Build summary strings for the top 10 messages
            for i, (msg, pri) in enumerate(zip(messages, priority_results)):
                if i >= 10:
                    break
                subject = msg.subject or "(no subject)"
                sender = msg.sender or "unknown"
                score = pri.get("score", 0)
                snippet = msg.body[:200].replace("\n", " ") if msg.body else ""
                email_summaries.append(
                    f"- [{score}/100] From: {sender} | Subject: {subject} | {snippet}"
                )

            # Collect high-priority ones (score >= 70)
            for msg, pri in zip(messages, priority_results):
                if pri.get("score", 0) >= 70:
                    high_priority_items.append(
                        f"- {msg.subject or '(no subject)'} from {msg.sender} "
                        f"[score={pri.get('score', 0)}, "
                        f"reason={pri.get('reason', '')}]"
                    )

        emails_summary = "\n".join(email_summaries) if email_summaries else "No recent emails."
        high_priority_str = (
            "\n".join(high_priority_items) if high_priority_items else "None."
        )

        # ---- 3. Build prompt ----------------------------------------
        today_date = datetime.utcnow().strftime("%Y-%m-%d")
        prompt = build_daily_briefing_prompt(
            today_date=today_date,
            emails_summary=emails_summary,
            calendar_summary="No calendar connected.",
            outstanding_items=None,
            high_priority_messages=high_priority_str,
        )

        # ---- 4. Call LLM --------------------------------------------
        raw = await self._call_llm(prompt)
        result = self.parse_json_response(raw)

        if not isinstance(result, dict) or "executive_summary" not in result:
            self.logger.warning("PlannerAgent.generate_daily_briefing: parse failure")
            return self._fallback_briefing(today_date, len(messages))

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fallback_briefing(self, today_date: str, message_count: int) -> dict:
        """Return a minimal fallback briefing when LLM parsing fails."""
        return {
            "date": today_date,
            "executive_summary": (
                f"You have {message_count} messages in the last 24 hours. "
                "AI briefing generation failed — please try again."
            ),
            "critical_items": [],
            "pending_work": [],
            "upcoming_deadlines": [],
            "recommended_priorities": [],
            "risks": [],
            "next_actions": ["Review recent emails manually."],
        }
