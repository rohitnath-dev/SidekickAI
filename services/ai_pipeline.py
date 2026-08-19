"""
Sidekick AI — AI Processing Pipeline

Coordinates the AI agents responsible for:

- Message priority classification
- Summary generation
- Action item extraction
- Long-term memory extraction
- Relevant memory retrieval
- Suggested reply generation
- Persisting AI results

A request-specific LLMClient can be supplied so every agent in the
pipeline uses the exact same provider, API key, and model.

If no client is supplied, agents use their normal application-level
LLM configuration.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from agents.memory_agent import MemoryAgent
from agents.priority_agent import PriorityAgent
from agents.reply_agent import ReplyAgent
from agents.summary_agent import SummaryAgent
from models.message import Message, MessagePriority
from services.llm import LLMClient


logger = logging.getLogger(__name__)


def _build_memory_context(memories) -> str:
    """
    Convert relevant MemoryItem objects into concise context for the
    reply-generation prompt.

    Only useful memory fields are included. Internal database metadata
    is intentionally excluded.
    """

    if not memories:
        return "No relevant long-term user information is available."

    lines: list[str] = []

    for memory in memories:
        content = getattr(
            memory,
            "content",
            None,
        )

        if not content:
            continue

        line = f"- {content.strip()}"

        related_project = getattr(
            memory,
            "related_project",
            None,
        )

        related_person = getattr(
            memory,
            "related_person",
            None,
        )

        if related_project:
            line += f" [Project: {related_project.strip()}]"

        if related_person:
            line += f" [Person: {related_person.strip()}]"

        lines.append(line)

    if not lines:
        return "No relevant long-term user information is available."

    return (
        "RELEVANT LONG-TERM USER INFORMATION:\n"
        + "\n".join(lines)
    )


async def process_message_ai(
    db: Session,
    message: Message,
    llm_client: Optional[LLMClient] = None,
) -> None:
    """
    Run the complete AI pipeline for a message.

    Pipeline:

        1. Priority classification
        2. Summary + sentiment + category
        3. Action item extraction
        4. Memory extraction and persistence
        5. Relevant memory retrieval
        6. Conditional suggested reply generation
        7. Save AI results to the database

    Memory extraction is intentionally non-blocking for the rest of the
    AI pipeline. If memory extraction fails, the message can still be
    classified and processed normally.

    Reply generation is conditional on the priority agent deciding that
    a response is actually required.
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

        if not isinstance(
            priority_result,
            dict,
        ):
            priority_result = {}

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

        summary_result = await summary_agent.generate_summary(
            email_content=message.body,
            user_id=message.user_id,
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

        action_result = await summary_agent.extract_action_items(
            email_content=message.body,
            user_id=message.user_id,
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
        # 4. Extract + save long-term memories
        # --------------------------------------------------------------

        memory_agent = MemoryAgent(
            llm_client=llm_client,
        )

        try:
            saved_memories = (
                await memory_agent.extract_and_save_memory(
                    message=message,
                    user_id=message.user_id,
                    db=db,
                )
            )

            logger.info(
                "Memory processing completed for message %d: "
                "saved=%d",
                message.id,
                len(saved_memories),
            )

        except Exception as memory_exc:
            # Memory is an enrichment layer. A failure here must not
            # prevent the main AI pipeline from completing.
            logger.error(
                "Memory extraction failed for message %d: %s",
                message.id,
                memory_exc,
                exc_info=True,
            )

        # --------------------------------------------------------------
        # 5. Retrieve relevant existing memories
        # --------------------------------------------------------------

        memory_context = (
            "No relevant long-term user information is available."
        )

        try:
            relevant_memories = (
                await memory_agent.get_relevant_memories(
                    user_id=message.user_id,
                    query=message.body,
                    db=db,
                    limit=10,
                )
            )

            memory_context = _build_memory_context(
                relevant_memories
            )

            logger.debug(
                "Retrieved %d relevant memories for message %d",
                len(relevant_memories),
                message.id,
            )

        except Exception as memory_exc:
            logger.error(
                "Relevant memory retrieval failed for message %d: %s",
                message.id,
                memory_exc,
                exc_info=True,
            )

        # --------------------------------------------------------------
        # 6. Suggested reply
        # --------------------------------------------------------------

        suggested_reply = ""

        if requires_reply:
            reply_agent = ReplyAgent(
                llm_client=llm_client,
            )

            sender_name = (
                message.sender.split("<")[0].strip()
                if message.sender
                else "User"
            )

            reply_result = await reply_agent.generate_reply(
                recipient_name=sender_name,
                email_content=message.body,
                context=memory_context,
                user_id=message.user_id,
            )

            if isinstance(
                reply_result,
                dict,
            ):
                suggested_reply = reply_result.get(
                    "reply",
                    "",
                )

        else:
            logger.debug(
                "Skipping reply generation for message %d "
                "because requires_reply=False",
                message.id,
            )

        # --------------------------------------------------------------
        # 7. Persist AI results
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

        # Re-raise so the API route knows this message actually failed.
        raise