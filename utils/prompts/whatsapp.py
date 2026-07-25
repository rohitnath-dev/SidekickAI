"""WhatsApp prompts."""

from utils.prompts.base import build, DEFAULT_TONE

_WHATSAPP_REPLY_TEMPLATE = """
Generate a WhatsApp reply to this message.

FROM: {sender_name}
MESSAGE: {message_content}
CONTEXT: {context}
TONE: {tone}

{core_rules}

Requirements:
- WhatsApp messages are typically shorter and more conversational than emails.
- Match the tone and register of the original message.
- Stay under 200 words.
- Return ONLY the message text. No labels, no metadata.
"""


def build_whatsapp_reply_prompt(
    sender_name: str,
    message_content: str,
    context: str | None = None,
    tone: str = DEFAULT_TONE,
) -> str:
    return build(
        _WHATSAPP_REPLY_TEMPLATE,
        sender_name=sender_name,
        message_content=message_content,
        context=context or "No additional context.",
        tone=tone,
    )
