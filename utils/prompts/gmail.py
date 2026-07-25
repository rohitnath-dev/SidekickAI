"""Gmail-specific prompts."""

from utils.prompts.base import build

_GMAIL_SYNC_TEMPLATE = """
You have just fetched {message_count} new Gmail messages for the user.
Provide a brief sync status summary.

MESSAGES OVERVIEW:
{messages_overview}

{core_rules}

Return this exact JSON structure:
{{
  "synced": {message_count},
  "high_priority_count": number,
  "requires_reply_count": number,
  "summary": "one sentence describing what was synced"
}}

Return ONLY the JSON.
"""


def build_gmail_sync_prompt(message_count: int, messages_overview: str) -> str:
    return build(
        _GMAIL_SYNC_TEMPLATE,
        message_count=str(message_count),
        messages_overview=messages_overview,
    )
