"""
WhatsApp Agent

Meta WhatsApp Cloud API integration via async httpx.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from agents.base_agent import BaseAgent
from config import settings
from utils.prompts.whatsapp import build_whatsapp_reply_prompt

logger = logging.getLogger(__name__)


class WhatsAppAgent(BaseAgent):
    """Meta WhatsApp Cloud API integration agent."""

    BASE_URL: str = settings.WHATSAPP_API_BASE_URL

    def __init__(self) -> None:
        super().__init__(agent_name="WhatsAppAgent")

    # ------------------------------------------------------------------
    # Send message
    # ------------------------------------------------------------------

    async def send_message(
        self,
        api_token: str,
        phone_number_id: str,
        to: str,
        text: str,
    ) -> dict:
        """
        Send a WhatsApp text message via the Meta Cloud API.

        Args:
            api_token: Meta API access token.
            phone_number_id: Sending phone number ID.
            to: Recipient's phone number (E.164 format).
            text: Message body text.

        Returns:
            API response dict or {} on failure.
        """
        url = f"{self.BASE_URL}/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            self.logger.error("WhatsAppAgent.send_message failed: %s", exc)
            raise exc

    # ------------------------------------------------------------------
    # Webhook parsing
    # ------------------------------------------------------------------

    async def get_webhook_messages(self, webhook_data: dict) -> list[dict]:
        """
        Parse an incoming Meta webhook payload and return normalised messages.

        Meta webhook structure:
        {
          "entry": [{
            "changes": [{
              "value": {
                "messages": [{
                  "from": "...",
                  "id": "...",
                  "timestamp": "...",
                  "text": {"body": "..."},
                  "type": "text"
                }]
              }
            }]
          }]
        }

        Returns:
            List of normalised message dicts with: from, text, timestamp, message_id.
        """
        normalised: list[dict] = []

        try:
            entries = webhook_data.get("entry", [])
            for entry in entries:
                changes = entry.get("changes", [])
                for change in changes:
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    for msg in messages:
                        if msg.get("type") != "text":
                            # Only handle text messages for now
                            continue
                        normalised.append({
                            "from": msg.get("from", ""),
                            "text": msg.get("text", {}).get("body", ""),
                            "timestamp": msg.get("timestamp", ""),
                            "message_id": msg.get("id", ""),
                        })
        except Exception as exc:
            self.logger.error("WhatsAppAgent.get_webhook_messages failed: %s", exc)

        return normalised

    # ------------------------------------------------------------------
    # LLM-powered reply generation
    # ------------------------------------------------------------------

    async def generate_reply_text(
        self,
        sender_name: str,
        message_content: str,
        context: Optional[str] = None,
        tone: str = "professional",
        user_id: Optional[int] = None,
    ) -> str:
        """
        Generate a WhatsApp reply using the LLM.

        Returns:
            Reply text string.
        """
        prompt = build_whatsapp_reply_prompt(
            sender_name=sender_name,
            message_content=message_content,
            context=context,
            tone=tone,
        )
        reply = await self._call_llm(prompt, user_id=user_id)
        return reply.strip()
