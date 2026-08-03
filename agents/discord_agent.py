"""
Discord Agent

Discord Bot API integration.
"""

from __future__ import annotations

import logging
import httpx
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

class DiscordAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(agent_name="DiscordAgent")

    async def send_message(self, bot_token: str, channel_id: str, text: str) -> dict:
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json",
        }
        payload = {"content": text}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
