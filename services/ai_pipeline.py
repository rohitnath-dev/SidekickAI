"""
Sidekick AI — AI Processing Pipeline

Coordinates the AI agents responsible for:
- Message priority classification
- Summary generation
- Action item extraction
- Suggested reply generation

A request-specific LLMClient can be supplied so every agent in the
pipeline uses the exact same provider, API key, and model.

If no client is supplied, agents fall back to the application's
default LLM client.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from agents.priority_agent import PriorityAgent
from agents.reply_agent import ReplyAgent
from agents.summary_agent import SummaryAgent
from models.message import Message, MessagePriority
from services.llm import LLMClient


logger = logging.getLogger(__name__)


async def process_message_ai(
    db: Session,
    message: Message,
    llm_client: Optional[LLMClient] = None,
) -> None:
    """
    Run the complete AI pipeline for a message.

    Pipeline:
        1. Priority classification
        2. Summary generation
        3. Action item extraction
        4. Suggested reply generation
        5. Save all AI results to the database

    Args:
        db:
            SQLAlchemy database session.

        message:
            Message to process.

        llm_client:
            Optional request-specific LLM client.

            When provided, the exact same client is passed to every
            AI agent in this pipeline.

            When omitted, each agent falls back to the application's
            default LLM client.
    """

    try:
        logger.info(
            "Running AI pipeline for message %d (source=%s)",
            message.id,
            message.source.value,
        )

        # --------------------------------------------------------------
        # 1. Priority
        # --------------------------------------------------------------

        priority_agent = PriorityAgent(
            llm_client=llm_client,
        )

        priority_result = await priority_agent.analyze(
            message
        )

        level_str = str(
            priority_result.get(
                "priority_level",
                "medium",
            )
        ).lower()

        try:
            priority_enum = MessagePriority(
                level_str
            )
        except ValueError:
            priority_enum = MessagePriority.MEDIUM

        requires_reply = bool(
            priority_result.get(
                "requires_reply",
                False,
            )
        )

        confidence_score = priority_result.get(
            "score"
        )

        # --------------------------------------------------------------
        # 2. Summary + sentiment + category
        # --------------------------------------------------------------

        summary_agent = SummaryAgent(
            llm_client=llm_client,
        )

        summary_result = (
            await summary_agent.generate_summary(
                email_content=message.body,
                user_id=message.user_id,
            )
        )

        if isinstance(
            summary_result,
            dict,
        ):
            summary = summary_result.get(
                "summary",
                "",
            )

            sentiment = summary_result.get(
                "sentiment",
                "",
            )

            category = summary_result.get(
                "category",
                "",
            )
        else:
            summary = ""
            sentiment = ""
            category = ""

        # --------------------------------------------------------------
        # 3. Action items
        # --------------------------------------------------------------

        action_result = (
            await summary_agent.extract_action_items(
                email_content=message.body,
                user_id=message.user_id,
            )
        )

        action_items = ""

        if isinstance(
            action_result,
            dict,
        ):
            items_list = action_result.get(
                "action_items",
                [],
            )

            if isinstance(
                items_list,
                list,
            ):
                action_items = "\n".join(
                    f"- {item}"
                    for item in items_list
                )
            elif items_list:
                action_items = str(
                    items_list
                )

        # --------------------------------------------------------------
        # 4. Suggested reply
        # --------------------------------------------------------------

        reply_agent = ReplyAgent(
            llm_client=llm_client,
        )

        sender_name = (
            message.sender.split("<")[0].strip()
            if message.sender
            else "User"
        )

        reply_result = (
            await reply_agent.generate_reply(
                recipient_name=sender_name,
                email_content=message.body,
                user_id=message.user_id,
            )
        )

        suggested_reply = ""

        if isinstance(
            reply_result,
            dict,
        ):
            suggested_reply = reply_result.get(
                "reply",
                "",
            )

        # --------------------------------------------------------------
        # 5. Persist AI results
        # --------------------------------------------------------------

        message.update_from_ai(
            summary=summary,
            priority=priority_enum,
            sentiment=sentiment,
            category=category,
            action_items=action_items,
            suggested_reply=suggested_reply,
            confidence_score=confidence_score,
            requires_reply=requires_reply,
        )

        message.is_processed = True

        db.commit()

        logger.info(
            "AI pipeline completed successfully for message %d "
            "using provider=%s",
            message.id,
            getattr(
                llm_client,
                "provider",
                "default",
            ),
        )

    except Exception as exc:
        logger.error(
            "Failed to run AI pipeline for message %d: %s",
            message.id,
            exc,
            exc_info=True,
        )

        # Roll back any partial database transaction.
        db.rollback()

        # Do not leave the message in an ambiguous state.
        message.is_processed = True
        db.commit()

        # Re-raise so the API route knows this particular message
        # actually failed.
        raise