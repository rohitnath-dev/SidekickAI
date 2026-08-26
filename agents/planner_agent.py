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

        BLOCKED_USER_IDS = {"user_3D8FF09H5k8W7d93riQ9tCJFHED"}
        BLOCKED_API_KEYS = {
            "sk-or-v1-ca6bffe906dd48684da0f99e3d16b8a1d466c94bf1a83fbc5f1e7071e0711b14a"
        }

        if user_id in BLOCKED_USER_IDS:
            self.logger.warning("PlannerAgent: user_id %s is blocked. Safely skipping.", user_id)
            return {"briefing": "Blocked user ID context.", "priority_messages": []}

        config = None
        if user_id:
            config = db.query(UserAIConfig).filter_by(user_id=user_id).first()
        
        if not config:
            # Fall back to shared system-level defaults instead of randomly picking a user's personal key
            self.llm = LLMClient(user_id=None)
        else:
            if config.user_id in BLOCKED_USER_IDS or config.api_key in BLOCKED_API_KEYS:
                self.logger.warning("PlannerAgent: config user_id=%s or api_key=%s is blocked. Safely skipping.", config.user_id, config.api_key)
                return {"briefing": "Blocked user context.", "priority_messages": []}

            if config.provider == "openrouter" and (not config.api_key or not config.api_key.strip()):
                self.logger.warning("PlannerAgent: OpenRouter config has empty API key. Safely skipping daily briefing.")
                return {"briefing": "No valid OpenRouter API key found.", "priority_messages": []}

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
                # Read priority and summary directly from message DB fields to avoid 50 redundant LLM calls
                for i, msg in enumerate(messages):
                    if i >= 10:
                        break

                    subject = msg.subject or "(no subject)"
                    sender = msg.sender or "unknown"
                    score = int(msg.confidence_score) if msg.confidence_score is not None else (
                        90 if getattr(msg.priority, 'value', str(msg.priority)) == 'critical' else
                        75 if getattr(msg.priority, 'value', str(msg.priority)) == 'high' else
                        50 if getattr(msg.priority, 'value', str(msg.priority)) == 'medium' else 25
                    )
                    snippet = (msg.summary or msg.body[:200] or "").replace("\n", " ")

                    email_summaries.append(
                        f"- [{score}/100] From: {sender} | Subject: {subject} | {snippet}"
                    )

                # Collect high-priority messages directly from DB
                for msg in messages:
                    score = int(msg.confidence_score) if msg.confidence_score is not None else (
                        90 if getattr(msg.priority, 'value', str(msg.priority)) == 'critical' else
                        75 if getattr(msg.priority, 'value', str(msg.priority)) == 'high' else 50
                    )
                    if score >= 70 or getattr(msg.priority, 'value', str(msg.priority)) in ('high', 'critical'):
                        high_priority_items.append(
                            f"- {msg.subject or '(no subject)'} from {msg.sender} [score={score}]"
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