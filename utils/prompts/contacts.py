"""Contacts prompts."""

from utils.prompts.base import build

_CONTACT_SUMMARY_TEMPLATE = """
Summarise what Sidekick knows about this contact based on stored messages and memory.

CONTACT: {contact_name}
EMAIL: {contact_email}

RECENT INTERACTIONS:
{recent_interactions}

STORED MEMORIES:
{memories}

{core_rules}
{json_rules}

Return this exact JSON structure:
{{
  "name": "{contact_name}",
  "email": "{contact_email}",
  "relationship_type": "colleague|client|vendor|friend|family|unknown",
  "communication_style": "brief description",
  "key_facts": ["fact 1", "fact 2"],
  "active_projects": ["project 1", ...] or [],
  "last_interaction_summary": "brief description or null",
  "suggested_reply_tone": "professional|friendly|formal|casual"
}}

Return ONLY the JSON.
"""


def build_contact_summary_prompt(
    contact_name: str,
    contact_email: str,
    recent_interactions: str,
    memories: str,
) -> str:
    return build(
        _CONTACT_SUMMARY_TEMPLATE,
        contact_name=contact_name,
        contact_email=contact_email,
        recent_interactions=recent_interactions or "No recent interactions.",
        memories=memories or "No stored memories.",
    )
