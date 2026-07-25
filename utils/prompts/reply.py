"""Reply prompts — draft generation and improvement."""

from utils.prompts.base import build, DEFAULT_TONE, DEFAULT_LANGUAGE, MAX_REPLY_WORDS

_REPLY_TEMPLATE = """
Generate a professional email reply.

RECIPIENT: {recipient_name}

ORIGINAL EMAIL:
{email_content}

CONTEXT:
{context}

TONE: {tone}
LANGUAGE: {language}

{core_rules}
{email_guide}

Requirements:
- Answer every question in the original email.
- Sound like a human wrote it, not an AI.
- Stay under {max_reply_words} words unless the topic requires more.
- Return ONLY the email body text (no subject line, no "Subject:", no signature).
"""

_IMPROVE_TEMPLATE = """
Review and improve this draft email reply.

ORIGINAL EMAIL:
{original_email}

DRAFT REPLY:
{reply_draft}

{core_rules}
{email_guide}

Improvements to make:
1. Fix grammar, spelling, and punctuation errors.
2. Remove redundancy and filler phrases.
3. Ensure all questions from the original email are answered.
4. Make it sound more natural and human.
5. Preserve the original intent and meaning.

Return ONLY the improved email body text. No explanation.
"""


def build_reply_prompt(
    recipient_name: str,
    email_content: str,
    context: str | None = None,
    tone: str = DEFAULT_TONE,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    return build(
        _REPLY_TEMPLATE,
        recipient_name=recipient_name,
        email_content=email_content,
        context=context or "No additional context.",
        tone=tone,
        language=language,
        max_reply_words=str(MAX_REPLY_WORDS),
    )


def build_improve_reply_prompt(original_email: str, reply_draft: str) -> str:
    return build(
        _IMPROVE_TEMPLATE,
        original_email=original_email,
        reply_draft=reply_draft,
    )
