"""Summary prompts — email and thread summarisation."""

from utils.prompts.base import build, DEFAULT_LANGUAGE

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

_SUMMARY_TEMPLATE = """
Analyse this email and return a structured JSON summary.

EMAIL:
{email_content}

CONTEXT:
{context}

{core_rules}
{json_rules}

Return this exact JSON structure:
{{
  "summary": "2-3 sentence overview of the main topic",
  "key_points": ["point 1", "point 2"],
  "action_items": ["action 1", "action 2"],
  "deadlines": ["deadline description with date", ...] or [],
  "mentioned_people": ["name 1", ...] or [],
  "sentiment": "{sentiment_enum}",
  "reply_required": true or false,
  "confidence_score": 0-100
}}

Return ONLY the JSON. No explanation.
"""

_THREAD_SUMMARY_TEMPLATE = """
Summarise this entire email thread.

EMAIL THREAD:
{thread_content}

{core_rules}
{json_rules}

Return this exact JSON structure:
{{
  "thread_title": "subject of conversation",
  "participants": ["person 1", "person 2"],
  "message_count": number,
  "current_status": "where the conversation stands now",
  "key_decisions": ["decision 1", ...] or [],
  "open_questions": ["question 1", ...] or [],
  "action_items": ["action 1", ...] or [],
  "next_steps": "recommended next action",
  "sentiment_trend": "improving|stable|declining"
}}

Return ONLY the JSON. No explanation.
"""

_ACTION_ITEMS_TEMPLATE = """
Extract all action items from this email.

EMAIL:
{email_content}

{core_rules}
{json_rules}

An action item is a specific task the recipient needs to complete.
Include only tasks explicitly stated or strongly implied.

Return this exact JSON structure:
{{
  "action_items": [
    {{
      "item": "specific action",
      "assigned_to": "user|other|unknown",
      "due_date": "ISO 8601 date or null",
      "priority": "{priority_enum}"
    }}
  ],
  "total_count": number
}}

Return ONLY the JSON. No explanation.
"""

# ---------------------------------------------------------------------------
# Builder functions
# ---------------------------------------------------------------------------


def build_summary_prompt(email_content: str, context: str | None = None) -> str:
    return build(
        _SUMMARY_TEMPLATE,
        email_content=email_content,
        context=context or "No additional context.",
    )


def build_thread_summary_prompt(thread_content: str) -> str:
    return build(_THREAD_SUMMARY_TEMPLATE, thread_content=thread_content)


def build_action_items_prompt(email_content: str) -> str:
    return build(_ACTION_ITEMS_TEMPLATE, email_content=email_content)
