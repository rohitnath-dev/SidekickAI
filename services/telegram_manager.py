import os
import json
import logging
import asyncio
from datetime import datetime
from telethon import TelegramClient, events
from telethon.sessions import StringSession

from database import SessionLocal
from models.user import User
from models.message import Message, MessageSource, MessagePriority, MessageStatus
from repositories.token_repo import TokenRepository
from routes.telegram import decrypt_session, encrypt_session
from services.ai_pipeline import process_message_ai
from config import settings

logger = logging.getLogger(__name__)

class TelegramManager:
    def __init__(self):
        self._clients: dict[int, TelegramClient] = {}

    async def start_all_clients(self) -> None:
        """Start persistent Telethon clients for all users with saved sessions."""
        db = SessionLocal()
        try:
            users = db.query(User).all()
            for user in users:
                token = TokenRepository.get(db, user_id=user.id, provider="telegram")
                if token and token.access_token != "disabled":
                    await self.start_client(user.id, token.access_token, token.token_uri)
        except Exception as e:
            logger.error("Failed to start persistent Telegram clients on startup: %s", e)
        finally:
            db.close()

    async def start_client(self, user_id: int, access_token: str, token_uri: str) -> None:
        """Start a single Telethon client and attach event listeners."""
        # Clean up existing client if running
        await self.stop_client(user_id)

        session_str = decrypt_session(access_token)
        if not session_str or session_str.startswith("disabled"):
            return

        try:
            creds = json.loads(token_uri)
            api_id = int(creds["api_id"])
            api_hash = creds["api_hash"]
        except Exception:
            api_id = settings.TELEGRAM_API_ID
            api_hash = settings.TELEGRAM_API_HASH

        if session_str.startswith("MOCK_SESSION"):
            logger.info("TelegramManager: Started persistent client (MOCK) for user_id=%d", user_id)
            return

        logger.info("TelegramManager: Starting persistent Telethon client for user_id=%d", user_id)
        
        try:
            client = TelegramClient(StringSession(session_str), api_id, api_hash)
            
            @client.on(events.NewMessage(incoming=True))
            async def handler(event):
                await self._handle_new_message(event, user_id)

            await client.connect()
            if await client.is_user_authorized():
                # Store client session reference
                self._clients[user_id] = client
                # Tell Telethon loop to listen to updates
                asyncio.create_task(client.run_until_disconnected())
                logger.info("TelegramManager: Persistent client successfully connected and authorized for user_id=%d", user_id)
            else:
                logger.warning("TelegramManager: Client connected but unauthorized for user_id=%d", user_id)
                await client.disconnect()
        except Exception as e:
            logger.error("TelegramManager: Failed to start client for user_id=%d: %s", user_id, e)

    async def stop_client(self, user_id: int) -> None:
        """Stop and disconnect a persistent Telethon client."""
        client = self._clients.pop(user_id, None)
        if client:
            try:
                await client.disconnect()
                logger.info("TelegramManager: Disconnected client for user_id=%d", user_id)
            except Exception as e:
                logger.error("TelegramManager: Error disconnecting client for user_id=%d: %s", user_id, e)

    async def _handle_new_message(self, event, user_id: int) -> None:
        """Process incoming Telethon message events, write to DB, and run AI pipeline."""
        if not event.text:
            return

        db = SessionLocal()
        try:
            sender_entity = await event.get_sender()
            sender_name = "Telegram User"
            username = str(event.sender_id)
            
            if sender_entity:
                username = getattr(sender_entity, "username", None) or str(event.sender_id)
                first_name = getattr(sender_entity, "first_name", "") or ""
                last_name = getattr(sender_entity, "last_name", "") or ""
                sender_name = f"{first_name} {last_name}".strip() or "Telegram User"

            msg_id = f"tg-user-{event.id}"
            
            existing = db.query(Message).filter_by(message_id=str(msg_id), source=MessageSource.TELEGRAM).first()
            if existing:
                return

            logger.info("TelegramManager: Ingested new real-time Telegram message (ID: %s) for user_id=%d", msg_id, user_id)
            db_msg = Message(
                user_id=user_id,
                message_id=str(msg_id),
                source=MessageSource.TELEGRAM,
                sender=username,
                recipient=sender_name,
                subject=f"Telegram Chat with {sender_name}",
                body=event.text,
                priority=MessagePriority.MEDIUM,
                status=MessageStatus.UNREAD,
                received_at=event.date or datetime.utcnow(),
            )
            db.add(db_msg)
            db.commit()
            db.refresh(db_msg)

            try:
                await process_message_ai(db, db_msg)
            except Exception as e:
                logger.error("TelegramManager: AI pipeline error on real-time message %s: %s", msg_id, e)

        except Exception as e:
            logger.error("TelegramManager: Error handling incoming event: %s", e)
        finally:
            db.close()

telegram_manager = TelegramManager()
