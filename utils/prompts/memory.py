"""Memory prompts — long-term fact extraction."""

from utils.prompts.base import build

_MEMORY_TEMPLATE = """
Extract information worth storing in long-term memory from this message.

MESSAGE:
{message_content}

{core_rules}
{json_rules}

Only extract factual, durable information. Ignore transient or one-time details.
Never invent or infer information not explicitly stated.

Return this exact JSON structure:
{{
  "memories": [
    {{
      "category": "{memory_categories}",
      "content": "specific fact to remember",
      "context": "why this is useful",
      "related_person": "name or null",
      "related_project": "project name or null",
      "retention_value": "high|medium|low",
      "confidence": 0.0-1.0
    }}
  ]
}}

If there is nothing worth remembering, return: {{"memories": []}}

Return ONLY the JSON. No explanation.
"""


def build_memory_prompt(message_content: str) -> str:
    return build(_MEMORY_TEMPLATE, message_content=message_content)
