"""Priority prompts — message urgency and importance classification."""

from utils.prompts.base import build

_PRIORITY_TEMPLATE = """
Classify the priority and urgency of this message.

MESSAGE:
{message_content}

ADDITIONAL CONTEXT:
{context}

{core_rules}
{json_rules}

Return this exact JSON structure:
{{
  "score": 0-100,
  "priority_level": "{priority_enum}",
  "urgency_score": 0-100,
  "importance_score": 0-100,
  "category": "{categories}",
  "business_impact": "high|medium|low|minimal",
  "requires_reply": true or false,
  "requires_immediate_reply": true or false,
  "reason": "one sentence explaining the classification",
  "risk_if_ignored": "consequence description or null",
  "recommended_action": "what the user should do",
  "estimated_response_deadline": "ISO 8601 datetime or null"
}}

Return ONLY the JSON. No explanation.
"""


def build_priority_prompt(message_content: str, context: str | None = None) -> str:
    return build(
        _PRIORITY_TEMPLATE,
        message_content=message_content,
        context=context or "No additional context.",
    )
