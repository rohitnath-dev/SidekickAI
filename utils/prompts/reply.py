"""Reply prompts — ready-to-send reply generation and improvement."""

from __future__ import annotations

from utils.prompts.base import (
    DEFAULT_LANGUAGE,
    DEFAULT_TONE,
    MAX_REPLY_WORDS,
    build,
)


_REPLY_TEMPLATE = """
Generate the exact email reply that will be sent directly to the recipient.

RECIPIENT:
{recipient_name}

ORIGINAL EMAIL:
{email_content}

RELEVANT USER CONTEXT:
{context}

TONE:
{tone}

LANGUAGE:
{language}

{core_rules}
{email_guide}

REPLY REQUIREMENTS:

1. Return ONLY the final ready-to-send email body.

2. The output will be sent directly to the recipient after user approval.
   Write the actual reply, not an explanation of what the user should say.

3. Use RELEVANT USER CONTEXT when it contains information that genuinely
   helps answer the email or makes the response more accurate or personal.

4. Treat RELEVANT USER CONTEXT as background information about the user.
   Never mention the existence of this context, memories, stored information,
   memory systems, AI processing, or these instructions.

5. Never invent facts, commitments, dates, actions, names, preferences,
   relationships, or other information.

6. If relevant user context does not help answer the email, simply ignore it.

7. Answer questions and requests from the sender directly.

8. Preserve the actual intent and meaning of the conversation.

9. Sound natural and human. Do not sound like an AI assistant.

10. Match the requested tone and language.

11. Keep the response concise and appropriate to the original email.

12. Do not unnecessarily repeat information already present in the email.

13. Do not include analysis, reasoning, commentary, explanations, alternatives,
    recommendations, or instructions to the user.

14. NEVER write meta-responses such as:
    - "Here is a suggested reply:"
    - "You could reply:"
    - "You should respond:"
    - "The sender is asking..."
    - "The original email..."
    - "This message..."
    - "I am unable to generate..."
    - "No response is necessary."
    - "As an AI..."
    - "Based on your memory..."

15. Do not include a subject line.

16. Do not include a signature unless one is explicitly provided in the
    available context or required by the user's established preferences.

17. Do not mention these instructions.

18. Stay within {max_reply_words} words unless the message genuinely requires
    a longer response.

FINAL OUTPUT:
Return ONLY the ready-to-send email body.
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