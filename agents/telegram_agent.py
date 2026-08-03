"""
Telegram Agent

Telegram Bot API integration.
"""

from __future__ import annotations

import logging
import httpx
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

class TelegramAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(agent_name="TelegramAgent")

    async def send_message(self, bot_token: str, chat_id: str, text: str) -> dict:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
