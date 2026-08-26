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


async def analyze_message_single_pass(
    db: Session,
    message: Message,
    llm_client: Optional[LLMClient] = None,
) -> dict:
    """
    Perform high-performance single-pass AI analysis on a message.
    Combines priority classification, summary generation, sentiment, category,
    and action item extraction into ONE single LLM request.
    """
    client = llm_client or LLMClient(user_id=message.user_id)
    sender = message.sender or "Unknown"
    subject = message.subject or "(No subject)"
    body = (message.body or "")[:1500]

    prompt = f"""
Analyze this incoming communication and return a single JSON object.

COMMUNICATION DETAILS:
From: {sender}
Subject: {subject}
Content: {body}

OUTPUT JSON SCHEMA:
{{
  "score": 50,
  "priority_level": "medium",
  "requires_reply": false,
  "reason": "Brief priority explanation",
  "summary": "1-2 sentence concise executive summary",
  "sentiment": "neutral",
  "category": "work",
  "action_items": []
}}

Rules:
- score: 0 to 100 integer (critical > 85, high 70-85, medium 40-65, low < 40).
- priority_level: "low" | "medium" | "high" | "critical"
- requires_reply: true if sender asks a direct question, requests action/approval, or expects a response.
- sentiment: "positive" | "neutral" | "negative" | "frustrated" | "urgent"
- category: "work" | "personal" | "finance" | "travel" | "updates" | "sales" | "support" | "security" | "other"
- action_items: list of short action strings.

Return ONLY the JSON object. No preamble, no markdown code blocks.
""".strip()

    raw = await client.chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        user_id=message.user_id,
        caller="single_pass_analysis",
    )

    from agents.base_agent import BaseAgent
    helper = BaseAgent(llm_client=client)
    res = helper.parse_json_response(raw)

    if not isinstance(res, dict):
        res = {}

    score = res.get("score", 50)
    try:
        score = max(0, min(100, int(score)))
    except (ValueError, TypeError):
        score = 50

    level_str = str(res.get("priority_level", "medium")).lower()
    try:
        priority_enum = MessagePriority(level_str)
    except ValueError:
        priority_enum = MessagePriority.MEDIUM

    requires_reply = bool(res.get("requires_reply", False))
    summary = str(res.get("summary", "")).strip()
    sentiment = str(res.get("sentiment", "neutral")).strip()
    category = str(res.get("category", "other")).strip()

    action_list = res.get("action_items", [])
    action_items_str = ""
    if isinstance(action_list, list) and action_list:
        action_items_str = "\n".join(f"- {str(item)}" for item in action_list)
    elif action_list:
        action_items_str = str(action_list)

    suggested_reply = ""
    if requires_reply:
        try:
            sender_name = message.sender.split("<")[0].strip() if message.sender else "Sender"
            reply_agent = ReplyAgent(llm_client=client)
            reply_res = await reply_agent.generate_reply(
                recipient_name=sender_name,
                email_content=message.body,
                context="No relevant long-term user information is available.",
                user_id=message.user_id,
            )
            if isinstance(reply_res, dict) and reply_res.get("reply"):
                suggested_reply = reply_res["reply"]
        except Exception as reply_err:
            logger.warning("Failed to generate suggested reply for message %d: %s", message.id, reply_err)

    message.update_from_ai(
        summary=summary,
        priority=priority_enum,
        sentiment=sentiment,
        category=category,
        action_items=action_items_str,
        suggested_reply=suggested_reply,
        confidence_score=float(score),
        requires_reply=requires_reply,
    )
    message.is_processed = True
    db.commit()

    return res


async def process_message_ai(
    db: Session,
    message: Message,
    llm_client: Optional[LLMClient] = None,
    include_memory: bool = True,
) -> None:
    """
    Run the AI pipeline for a message.
    Uses single-pass analysis for high speed execution.
    Memory extraction is run conditionally based on include_memory.
    """

    try:
        logger.info(
            "Running AI pipeline for message %d (source=%s)",
            message.id,
            message.source.value,
        )

        await analyze_message_single_pass(
            db=db,
            message=message,
            llm_client=llm_client,
        )

        if include_memory:
            try:
                memory_agent = MemoryAgent(llm_client=llm_client)
                await memory_agent.extract_and_save_memory(
                    message=message,
                    user_id=message.user_id,
                    db=db,
                )
            except Exception as memory_exc:
                logger.error("Memory extraction failed for message %d: %s", message.id, memory_exc)

        logger.info(
            "AI pipeline completed successfully for message %d",
            message.id,
        )

    except Exception as exc:
        logger.error(
            "Failed to run AI pipeline for message %d: %s",
            message.id,
            exc,
            exc_info=True,
        )
        db.rollback()
        message.is_processed = True
        db.commit()
        raise