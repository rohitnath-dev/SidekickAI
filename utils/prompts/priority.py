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

REPLY DECISION POLICY:

Determine whether the user should actually reply to this message.

A reply is REQUIRED when:
- A real person is communicating with the user and expects an answer.
- The sender asks a question.
- The sender requests information, confirmation, a decision, approval, action, or response.
- The message is part of an ongoing human conversation where a response is reasonably expected.
- A company/support/customer/service representative is directly communicating with the user and clearly expects a response or action from the user.

A reply is NOT REQUIRED when:
- The message is an automated notification.
- The sender is a no-reply/automated address.
- The message is a security alert, account notification, login alert, OAuth notification, system notification, receipt, confirmation, status update, or similar automated message that does not ask for a response.
- The message is a newsletter, marketing email, advertisement, promotion, campaign, or bulk communication.
- The message is a product update, service announcement, GitHub/Google/YouTube/platform notification, or other informational update with no request for a response.
- The message merely informs the user about something and does not reasonably expect a reply.

IMPORTANT:
Do NOT infer that a reply is required merely because the message is important, urgent, or high priority.

Priority and reply requirement are separate decisions.

Examples:
- GitHub security/OAuth notification -> low priority, requires_reply=false.
- Google account/security notification -> low priority, requires_reply=false.
- YouTube notification/newsletter -> low priority, requires_reply=false.
- Marketing/promotional email -> low priority, requires_reply=false.
- Human colleague asking "Can you send this by Friday?" -> requires_reply=true.
- Human friend sending a conversational message -> requires_reply=true.
- Customer asking a question -> requires_reply=true.
- Company support representative asking for confirmation -> requires_reply=true.
- Automated receipt/confirmation -> requires_reply=false.

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
