"""Memory prompts — long-term user fact extraction."""

from utils.prompts.base import build


_MEMORY_TEMPLATE = """
Extract information from this message that is genuinely worth storing
in the user's long-term memory for use in future conversations, emails,
messages, planning, and AI-generated responses.

MESSAGE:
{message_content}

{core_rules}
{json_rules}

MEMORY PRINCIPLE:

Only store information that is useful beyond the current message.

The goal is to build a small, accurate, long-term understanding of the
user and their ongoing context — NOT to store a copy of the user's
messages or every piece of information mentioned in them.

STORE information such as:

- Stable personal preferences explicitly stated by the user.
- Long-term professional information about the user.
- The user's role, responsibilities, skills, or areas of expertise.
- Ongoing projects the user is working on.
- Important project-related facts that are likely to remain useful.
- Important relationships or recurring contacts when explicitly relevant.
- Long-term goals, plans, or commitments.
- Recurring preferences or communication preferences.
- Important facts that would meaningfully improve future AI responses.
- Information the user explicitly says should be remembered.

DO NOT STORE:

- One-time events or temporary situations.
- Today's schedule or a single meeting time.
- Temporary deadlines that have no lasting relevance.
- OTPs, verification codes, passwords, API keys, tokens, or secrets.
- Marketing emails, newsletters, advertisements, or promotions.
- Automated notifications from GitHub, Google, YouTube, or other services.
- Receipts, delivery updates, login alerts, security alerts, or system
  notifications unless they contain an explicit durable fact about the user.
- Generic information about a company, product, service, or sender.
- Facts that only describe the current email but provide no lasting value.
- Information that belongs to the sender rather than the user unless it
  is genuinely useful as long-term relationship/context information.
- Duplicate information that is merely a rewording of an already stated fact.
- Guesses, assumptions, implications, or conclusions not explicitly
  supported by the message.

IMPORTANT:

1. Extract only information supported by the message.
2. Never invent, infer, or assume facts.
3. Prefer fewer high-quality memories over many low-value memories.
4. A fact should be retained only if it is likely to remain useful after
   the current conversation/message is no longer relevant.
5. If the message contains no durable user-specific information, return
   an empty memories list.
6. Do not store the entire message as a memory.
7. Do not store sensitive credentials or secrets.
8. Do not treat importance or urgency as a reason to create a memory.
9. Information being useful for the current task does NOT automatically
   make it suitable for long-term memory.
10. When uncertain whether something deserves long-term storage, do not
    store it.

EXAMPLES:

User says:
"I am building SidekickAI and I handle the backend."

STORE:
- The user is building SidekickAI.
- The user handles the SidekickAI backend.

User says:
"I prefer concise professional emails."

STORE:
- The user prefers concise professional emails.

User says:
"Can we meet tomorrow at 5 PM?"

DO NOT STORE:
- The meeting time is tomorrow at 5 PM.

User receives:
"Your GitHub OAuth application was authorized."

DO NOT STORE:
- GitHub OAuth authorization notification.

User receives:
"Your YouTube Premium subscription renews on Friday."

DO NOT STORE:
- YouTube Premium renewal information.

User says:
"Remember that I am working with Alex on the SidekickAI backend."

STORE:
- The user is working with Alex on the SidekickAI backend.

OUTPUT:

Return this exact JSON structure:

{{
  "memories": [
    {{
      "category": "{memory_categories}",
      "content": "specific durable fact to remember",
      "context": "brief explanation of why this fact is useful in future interactions",
      "related_person": "name or null",
      "related_project": "project name or null",
      "retention_value": "high|medium|low",
      "confidence": 0.0-1.0
    }}
  ]
}}

If there is nothing genuinely worth remembering, return:

{{"memories": []}}

Return ONLY valid JSON. No explanation or preamble.
"""


def build_memory_prompt(message_content: str) -> str:
    """Build the long-term memory extraction prompt."""

    return build(
        _MEMORY_TEMPLATE,
        message_content=message_content,
    )