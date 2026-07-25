"""Twitter / X prompts."""

from utils.prompts.base import build

_TWITTER_REPLY_TEMPLATE = """
Draft a reply to this tweet/X post.

ORIGINAL POST by @{author_handle}:
{post_content}

USER'S CONTEXT / STANCE: {context}

{core_rules}

Requirements:
- Maximum 280 characters (Twitter limit).
- Match the tone of the conversation (professional, witty, informative, etc.).
- Do NOT use hashtags unless explicitly requested.
- Return ONLY the reply text. No metadata.
"""


def build_twitter_reply_prompt(
    author_handle: str,
    post_content: str,
    context: str | None = None,
) -> str:
    return build(
        _TWITTER_REPLY_TEMPLATE,
        author_handle=author_handle,
        post_content=post_content,
        context=context or "Respond professionally.",
    )
