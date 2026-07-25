"""Planner prompts — daily briefing and task prioritisation."""

from utils.prompts.base import build, MAX_BRIEFING_WORDS

_DAILY_BRIEFING_TEMPLATE = """
Generate an executive daily briefing.

DATE: {today_date}

EMAILS SUMMARY:
{emails_summary}

CALENDAR:
{calendar_summary}

OUTSTANDING ITEMS:
{outstanding_items}

HIGH PRIORITY MESSAGES:
{high_priority_messages}

{core_rules}

Create a concise, actionable briefing under {max_briefing_words} words.
Use bullet points. Prioritise by urgency and business impact.

Return this exact JSON structure:
{{
  "date": "{today_date}",
  "executive_summary": "1-2 sentence overview of the day",
  "critical_items": [
    {{"item": "description", "action": "what to do", "deadline": "when or null"}}
  ],
  "pending_work": ["item 1", "item 2"],
  "upcoming_deadlines": [
    {{"what": "description", "when": "ISO 8601 date or time"}}
  ],
  "recommended_priorities": ["priority 1", "priority 2", "priority 3"],
  "risks": ["risk 1", ...] or [],
  "next_actions": ["immediate action 1", "immediate action 2"]
}}

Return ONLY the JSON. No explanation.
"""


def build_daily_briefing_prompt(
    today_date: str,
    emails_summary: str,
    calendar_summary: str,
    outstanding_items: str | None = None,
    high_priority_messages: str | None = None,
) -> str:
    return build(
        _DAILY_BRIEFING_TEMPLATE,
        today_date=today_date,
        emails_summary=emails_summary,
        calendar_summary=calendar_summary,
        outstanding_items=outstanding_items or "None.",
        high_priority_messages=high_priority_messages or "None.",
        max_briefing_words=str(MAX_BRIEFING_WORDS),
    )
