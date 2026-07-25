"""Personality / user style prompts — personalise AI behaviour per user."""

from utils.prompts.base import build

_PERSONALITY_TEMPLATE = """
Based on the user's communication history, describe their communication style
and preferences so future AI responses can be personalised.

SAMPLE MESSAGES SENT BY USER:
{sample_messages}

{core_rules}
{json_rules}

Return this exact JSON structure:
{{
  "tone": "professional|friendly|formal|casual|direct",
  "formality_level": 1-10,
  "average_email_length": "short|medium|long",
  "uses_bullet_points": true or false,
  "common_phrases": ["phrase 1", ...] or [],
  "preferred_greeting": "Hi|Dear|Hello|[Name], or null",
  "preferred_closing": "Best|Regards|Thanks|Cheers or null",
  "topics_of_interest": ["topic 1", ...] or [],
  "communication_style_summary": "one sentence summary"
}}

Return ONLY the JSON.
"""


def build_personality_context(sample_messages: str) -> str:
    return build(_PERSONALITY_TEMPLATE, sample_messages=sample_messages)
