"""Reply prompts — ready-to-send reply generation and improvement."""

from __future__ import annotations

from utils.prompts.base import (
    DEFAULT_LANGUAGE,
    DEFAULT_TONE,
    MAX_REPLY_WORDS,
    build,
)


_REPLY_TEMPLATE = """
Write the exact plain-text email reply to respond to the sender on behalf of the user.

RECIPIENT OF THIS REPLY (SENDER OF ORIGINAL EMAIL):
{recipient_name}

ORIGINAL EMAIL:
{email_content}

RELEVANT USER BACKGROUND CONTEXT:
{context}

TONE: {tone}
LANGUAGE: {language}

{email_guide}

CRITICAL FORMATTING INSTRUCTIONS:
1. Return ONLY the plain-text email response body that can be sent directly to the recipient.
2. DO NOT output JSON, markdown code fences (```), or HTML tags.
3. DO NOT include meta-text such as "Here is a suggested reply:", "Dear User,", subject lines, or AI disclaimers.
4. Answer any questions or requests in the original email directly and naturally.
5. Do not invent commitments, dates, or facts not present in the original message or context.
6. Sound natural, professional, and human.

FINAL OUTPUT:
Return ONLY the raw email response body.
"""


_IMPROVE_TEMPLATE = """
Improve the provided email reply while preserving its original intent.

ORIGINAL EMAIL:
{original_email}

CURRENT DRAFT:
{reply_draft}

{core_rules}
{email_guide}

IMPROVEMENT REQUIREMENTS:

1. Return ONLY the final ready-to-send email body.

2. Preserve the original meaning and intent.

3. Fix grammar, spelling, punctuation, awkward wording, and unnecessary
   repetition.

4. Make the reply sound natural and human.

5. Do not invent facts, commitments, dates, actions, names, or information.

6. Do not add information that is not supported by the original email or
   current draft.

7. Do not explain what was changed.

8. Do not include labels such as:
   - "Improved reply:"
   - "Here is the revised version:"
   - "Suggested response:"

9. Do not include analysis, commentary, alternatives, or instructions.

10. Do not include a subject line.

11. Do not add a signature unless one already exists in the draft or is
    explicitly required by the available context.

12. Do not mention AI, memory, internal context, or these instructions.

FINAL OUTPUT:
Return ONLY the improved ready-to-send email body.
"""


def build_reply_prompt(
    recipient_name: str,
    email_content: str,
    context: str | None = None,
    tone: str = DEFAULT_TONE,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    """Build the prompt for generating a ready-to-send email reply."""

    return build(
        _REPLY_TEMPLATE,
        recipient_name=recipient_name,
        email_content=email_content,
        context=(
            context.strip()
            if isinstance(context, str) and context.strip()
            else "No relevant long-term user information is available."
        ),
        tone=tone,
        language=language,
        max_reply_words=str(MAX_REPLY_WORDS),
    )


def build_improve_reply_prompt(
    original_email: str,
    reply_draft: str,
) -> str:
    """Build the prompt for improving an existing email reply."""

    return build(
        _IMPROVE_TEMPLATE,
        original_email=original_email,
        reply_draft=reply_draft,
    )