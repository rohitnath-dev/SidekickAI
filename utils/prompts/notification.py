"""Notification prompts — intelligent push notification text generation."""

from utils.prompts.base import build

_NOTIFICATION_TEMPLATE = """
Generate a smart push notification for this message.

MESSAGE TYPE: {message_type}
FROM: {sender}
SUBJECT / TOPIC: {subject}
KEY CONTENT: {key_content}
PRIORITY: {priority}

{core_rules}
{json_rules}

Generate a concise, actionable push notification.

Return this exact JSON structure:
{{
  "title": "notification title (max 50 chars)",
  "body": "notification body (max 120 chars)",
  "action_label": "reply|view|dismiss|snooze",
  "priority": "{priority}",
  "suggested_quick_reply": "one-sentence quick reply or null"
}}

Return ONLY the JSON.
"""


def build_notification_prompt(
    message_type: str,
    sender: str,
    subject: str,
    key_content: str,
    priority: str = "medium",
) -> str:
    return build(
        _NOTIFICATION_TEMPLATE,
        message_type=message_type,
        sender=sender,
        subject=subject,
        key_content=key_content,
        priority=priority,
    )
