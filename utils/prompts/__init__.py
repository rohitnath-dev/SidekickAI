"""
Sidekick AI — Prompt Package

Single source of truth for all LLM prompts.
Import builder functions from the appropriate sub-module.
"""

from utils.prompts.system import SYSTEM_PROMPT, get_system_context
from utils.prompts.summary import build_summary_prompt, build_thread_summary_prompt, build_action_items_prompt
from utils.prompts.priority import build_priority_prompt
from utils.prompts.reply import build_reply_prompt, build_improve_reply_prompt
from utils.prompts.memory import build_memory_prompt
from utils.prompts.planner import build_daily_briefing_prompt
from utils.prompts.gmail import build_gmail_sync_prompt
from utils.prompts.calendar import build_calendar_summary_prompt
from utils.prompts.contacts import build_contact_summary_prompt
from utils.prompts.twitter import build_twitter_reply_prompt
from utils.prompts.notification import build_notification_prompt
from utils.prompts.personality import build_personality_context

__all__ = [
    "SYSTEM_PROMPT",
    "get_system_context",
    "build_summary_prompt",
    "build_thread_summary_prompt",
    "build_action_items_prompt",
    "build_priority_prompt",
    "build_reply_prompt",
    "build_improve_reply_prompt",
    "build_memory_prompt",
    "build_daily_briefing_prompt",
    "build_gmail_sync_prompt",
    "build_calendar_summary_prompt",
    "build_contact_summary_prompt",
    "build_twitter_reply_prompt",
    "build_notification_prompt",
    "build_personality_context",
]
