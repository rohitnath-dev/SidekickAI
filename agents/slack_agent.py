"""
Slack Ingestion Agent
Fetches direct messages and channel mentions from Slack and stores them in the unified communications database.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from sqlalchemy.orm import Session

from agents.base_agent import BaseAgent
from models.message import Message, MessagePriority, MessageSource, MessageStatus

logger = logging.getLogger(__name__)


class SlackAgent(BaseAgent):
    """Slack integration agent — fetches, parses, and stores Slack direct messages and mentions."""

    def __init__(self) -> None:
        super().__init__(agent_name="SlackAgent")
        self.cached_users: dict[str, str] = {}

    async def _get_user_name(self, user_id: str, access_token: str) -> str:
        """Helper to resolve Slack User ID to a human-readable name."""
        if not user_id:
            return "Unknown User"
        if user_id in self.cached_users:
            return self.cached_users[user_id]

        url = "https://slack.com/api/users.info"
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"user": user_id}
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, headers=headers, params=params)
                res.raise_for_status()
                data = res.json()
                if data.get("ok"):
                    user_data = data.get("user") or {}
                    name = user_data.get("real_name") or user_data.get("name") or user_id
                    self.cached_users[user_id] = name
                    return name
        except Exception as exc:
            self.logger.warning("Failed to resolve Slack user ID %s: %s", user_id, exc)
        
        return user_id

    async def sync_slack(
        self,
        access_token: str,
        db: Session,
        user_id: int,
        limit: int = 50,
    ) -> dict[str, Any]:
        """
        Synchronize user's Slack direct messages and mentions.
        """
        self.logger.info("Starting Slack sync for user_id=%d", user_id)
        synced_count = 0
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            # 1. Fetch user's own details from Slack
            async with httpx.AsyncClient(timeout=20.0) as client:
                auth_res = await client.post("https://slack.com/api/auth.test", headers=headers)
                auth_res.raise_for_status()
                auth_data = auth_res.json()
                if not auth_data.get("ok"):
                    self.logger.error("Slack auth.test failed: %s", auth_data.get("error"))
                    return {"synced": 0, "status": "auth_failure"}

                slack_user_id = auth_data.get("user_id")
                slack_user_name = auth_data.get("user")
                self.logger.info("Resolved Slack identity: user_id=%s, username=%s", slack_user_id, slack_user_name)

            # 2. Ingest Direct Messages (IM)
            # Fetch IM channel conversations
            async with httpx.AsyncClient(timeout=20.0) as client:
                im_res = await client.get(
                    "https://slack.com/api/conversations.list",
                    headers=headers,
                    params={"types": "im", "limit": 100}
                )
                im_res.raise_for_status()
                im_data = im_res.json()
                im_channels = im_data.get("channels", []) if im_data.get("ok") else []

            self.logger.info("Found %d Slack IM channels for sync", len(im_channels))

            for channel in im_channels:
                channel_id = channel.get("id")
                dm_partner_id = channel.get("user")
                if not channel_id:
                    continue

                dm_partner_name = await self._get_user_name(dm_partner_id, access_token)

                # Fetch history for this IM channel
                async with httpx.AsyncClient(timeout=20.0) as client:
                    history_res = await client.get(
                        "https://slack.com/api/conversations.history",
                        headers=headers,
                        params={"channel": channel_id, "limit": limit}
                    )
                    history_res.raise_for_status()
                    history_data = history_res.json()
                    messages = history_data.get("messages", []) if history_data.get("ok") else []

                for msg_data in messages:
                    ts = msg_data.get("ts")
                    text = msg_data.get("text", "")
                    sender_id = msg_data.get("user")
                    if not ts or not text:
                        continue

                    # Don't ingest messages sent by the user themselves
                    if sender_id == slack_user_id:
                        continue

                    # Unique message identifier
                    db_message_id = f"slack_dm_{channel_id}_{ts}"

                    # Check if already exists
                    existing = db.query(Message).filter_by(user_id=user_id, message_id=db_message_id).first()
                    if existing:
                        continue

                    sender_name = await self._get_user_name(sender_id, access_token)
                    dt_received = datetime.fromtimestamp(float(ts), tz=timezone.utc).replace(tzinfo=None)

                    # Create and store Message
                    msg = Message(
                        user_id=user_id,
                        message_id=db_message_id,
                        thread_id=msg_data.get("thread_ts"),
                        source=MessageSource.SLACK,
                        sender=sender_name,
                        recipient=slack_user_name,
                        subject="Slack Direct Message",
                        body=text,
                        html_body=None,
                        channel_info=f"Direct Message with {dm_partner_name}",
                        category="work",
                        priority=MessagePriority.MEDIUM,
                        status=MessageStatus.UNREAD,
                        received_at=dt_received,
                    )
                    db.add(msg)
                    db.commit()
                    synced_count += 1
                    self.logger.info("Ingested Slack DM from %s: %s", sender_name, text[:40])

            # 3. Ingest Mentions in Public & Private Channels
            # Fetch channels the user is in
            async with httpx.AsyncClient(timeout=20.0) as client:
                channels_res = await client.get(
                    "https://slack.com/api/conversations.list",
                    headers=headers,
                    params={"types": "public_channel,private_channel", "limit": 100}
                )
                channels_res.raise_for_status()
                channels_data = channels_res.json()
                conversations = channels_data.get("channels", []) if channels_data.get("ok") else []

            self.logger.info("Scanning %d Slack channels for mentions", len(conversations))

            for conv in conversations:
                conv_id = conv.get("id")
                conv_name = conv.get("name", conv_id)
                is_member = conv.get("is_member", False)
                if not conv_id or not is_member:
                    continue

                # Fetch recent messages from this channel
                async with httpx.AsyncClient(timeout=20.0) as client:
                    history_res = await client.get(
                        "https://slack.com/api/conversations.history",
                        headers=headers,
                        params={"channel": conv_id, "limit": limit}
                    )
                    history_res.raise_for_status()
                    history_data = history_res.json()
                    messages = history_data.get("messages", []) if history_data.get("ok") else []

                for msg_data in messages:
                    ts = msg_data.get("ts")
                    text = msg_data.get("text", "")
                    sender_id = msg_data.get("user")
                    if not ts or not text:
                        continue

                    # Don't ingest messages sent by the user themselves
                    if sender_id == slack_user_id:
                        continue

                    # Check if the message contains user ID mention (e.g. <@U12345>)
                    if f"<@{slack_user_id}>" not in text:
                        continue

                    # Unique message identifier
                    db_message_id = f"slack_mention_{conv_id}_{ts}"

                    # Check if already exists
                    existing = db.query(Message).filter_by(user_id=user_id, message_id=db_message_id).first()
                    if existing:
                        continue

                    sender_name = await self._get_user_name(sender_id, access_token)
                    dt_received = datetime.fromtimestamp(float(ts), tz=timezone.utc).replace(tzinfo=None)

                    # Create and store Message
                    msg = Message(
                        user_id=user_id,
                        message_id=db_message_id,
                        thread_id=msg_data.get("thread_ts"),
                        source=MessageSource.SLACK,
                        sender=sender_name,
                        recipient=slack_user_name,
                        subject=f"Slack Mention in #{conv_name}",
                        body=text,
                        html_body=None,
                        channel_info=f"#{conv_name}",
                        category="work",
                        priority=MessagePriority.MEDIUM,
                        status=MessageStatus.UNREAD,
                        received_at=dt_received,
                    )
                    db.add(msg)
                    db.commit()
                    synced_count += 1
                    self.logger.info("Ingested Slack mention in #%s from %s: %s", conv_name, sender_name, text[:40])

            return {"synced": synced_count, "status": "success"}

        except Exception as exc:
            self.logger.error("Slack sync failed: %s", exc, exc_info=True)
            return {"synced": synced_count, "status": f"error: {str(exc)}"}
