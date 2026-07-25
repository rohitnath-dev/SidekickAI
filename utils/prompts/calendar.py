"""Calendar prompts."""

from utils.prompts.base import build

_CALENDAR_SUMMARY_TEMPLATE = """
Summarise today's calendar events for the user.

TODAY'S DATE: {today_date}
CALENDAR EVENTS:
{events_content}

{core_rules}
{json_rules}

Return this exact JSON structure:
{{
  "event_count": number,
  "summary": "one sentence overview",
  "events": [
    {{
      "title": "event name",
      "start_time": "HH:MM",
      "end_time": "HH:MM",
      "location": "location or null",
      "attendees": ["name 1", ...] or [],
      "requires_preparation": true or false,
      "notes": "relevant note or null"
    }}
  ],
  "conflicts": ["conflict description", ...] or [],
  "prep_needed": ["event requiring prep", ...] or []
}}

Return ONLY the JSON.
"""


def build_calendar_summary_prompt(today_date: str, events_content: str) -> str:
    return build(
        _CALENDAR_SUMMARY_TEMPLATE,
        today_date=today_date,
        events_content=events_content or "No events today.",
    )
