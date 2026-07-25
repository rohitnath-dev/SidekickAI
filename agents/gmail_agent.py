"""
Gmail Agent

Full Gmail integration using google-api-python-client.
Credentials come from services/oauth.py — no token files.
"""

from __future__ import annotations

import base64
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from agents.base_agent import BaseAgent
from models.message import Message, MessagePriority, MessageSource, MessageStatus

logger = logging.getLogger(__name__)


class GmailAgent(BaseAgent):
    """Gmail integration agent — fetches, parses, and stores Gmail messages."""

    def __init__(self) -> None:
        super().__init__(agent_name="GmailAgent")

    # ------------------------------------------------------------------
    # Internal service builder
    # ------------------------------------------------------------------

    def _build_service(self, creds: Credentials):
        """Build a Gmail API service object from credentials."""
        return build("gmail", "v1", credentials=creds)

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    def get_profile(self, creds: Credentials) -> dict:
        """Fetch the Gmail account profile."""
        try:
            service = self._build_service(creds)
            return service.users().getProfile(userId="me").execute()
        except HttpError as exc:
            self.logger.error("GmailAgent.get_profile failed: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # Message listing
    # ------------------------------------------------------------------

    def get_messages(
        self,
        creds: Credentials,
        limit: int = 20,
        unread_only: bool = False,
    ) -> list[dict]:
        """
        List Gmail messages.

        Returns:
            List of dicts with 'id' and 'threadId' keys.
        """
        try:
            service = self._build_service(creds)
            query = "is:unread" if unread_only else ""
            result = (
                service.users()
                .messages()
                .list(userId="me", maxResults=limit, q=query)
                .execute()
            )
            return result.get("messages", [])
        except HttpError as exc:
            self.logger.error("GmailAgent.get_messages failed: %s", exc)
            return []

    def get_message(self, creds: Credentials, message_id: str) -> dict:
        """Fetch a full Gmail message by ID."""
        try:
            service = self._build_service(creds)
            return (
                service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
        except HttpError as exc:
            self.logger.error("GmailAgent.get_message(%s) failed: %s", message_id, exc)
            return {}

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def parse_message(self, gmail_raw: dict) -> dict:
        """
        Parse a raw Gmail API message into a normalised dict.

        Returns dict with keys:
            message_id, thread_id, sender, recipient, subject,
            received_at (datetime), body (str)
        """
        if not gmail_raw:
            return {}

        payload = gmail_raw.get("payload", {})
        headers = self._extract_headers(payload)
        body = self._extract_body(payload)

        return {
            "message_id": gmail_raw.get("id", ""),
            "thread_id": gmail_raw.get("threadId", ""),
            "sender": headers.get("From", ""),
            "recipient": headers.get("To", ""),
            "subject": headers.get("Subject", ""),
            "received_at": self._parse_date(headers.get("Date", "")),
            "body": body,
        }

    def _extract_headers(self, payload: dict) -> dict:
        """Extract From, To, Subject, Date from a Gmail payload."""
        headers: dict[str, str] = {}
        for header in payload.get("headers", []):
            name = header.get("name", "")
            value = header.get("value", "")
            if name in ("From", "To", "Subject", "Date"):
                headers[name] = value
        return headers

    def _extract_body(self, payload: dict) -> str:
        """
        Recursively extract the text body from a Gmail MIME payload.

        Prefers text/plain; falls back to text/html (stripped of tags).
        """
        mime_type = payload.get("mimeType", "")

        # Leaf node — check for body data
        if "body" in payload and "data" in payload["body"]:
            data = payload["body"]["data"]
            text = self._decode_base64(data)
            if mime_type == "text/plain":
                return text
            if mime_type == "text/html":
                return self._strip_html(text)
            return text

        # Multipart — recurse into parts
        parts = payload.get("parts", [])
        if not parts:
            return ""

        # For multipart/alternative prefer text/plain
        plain_parts: list[str] = []
        html_parts: list[str] = []
        other_parts: list[str] = []

        for part in parts:
            part_mime = part.get("mimeType", "")
            if part_mime == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    plain_parts.append(self._decode_base64(data))
                else:
                    # May be nested multipart
                    nested = self._extract_body(part)
                    if nested:
                        plain_parts.append(nested)
            elif part_mime == "text/html":
                data = part.get("body", {}).get("data", "")
                if data:
                    html_parts.append(self._strip_html(self._decode_base64(data)))
                else:
                    nested = self._extract_body(part)
                    if nested:
                        html_parts.append(nested)
            elif part_mime.startswith("multipart/"):
                nested = self._extract_body(part)
                if nested:
                    other_parts.append(nested)
            else:
                # Recurse just in case
                nested = self._extract_body(part)
                if nested:
                    other_parts.append(nested)

        if plain_parts:
            return "\n".join(plain_parts)
        if html_parts:
            return "\n".join(html_parts)
        return "\n".join(other_parts)

    def _decode_base64(self, data: str) -> str:
        """Decode a Gmail base64url-encoded string to UTF-8 text."""
        try:
            padded = data + "=" * (4 - len(data) % 4)
            decoded_bytes = base64.urlsafe_b64decode(padded)
            return decoded_bytes.decode("utf-8", errors="replace")
        except Exception as exc:
            self.logger.warning("GmailAgent._decode_base64 failed: %s", exc)
            return ""

    def _strip_html(self, html: str) -> str:
        """Remove HTML tags from a string using a simple regex."""
        # Remove script/style blocks
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
        # Remove all tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _parse_date(self, date_str: str) -> datetime:
        """
        Parse an RFC 2822 email date string into a UTC-naive datetime.
        Falls back to datetime.utcnow() on failure.
        """
        if not date_str:
            return datetime.utcnow()
        try:
            dt = parsedate_to_datetime(date_str)
            # Convert to UTC naive
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:
            self.logger.warning("GmailAgent._parse_date: cannot parse '%s'", date_str)
            return datetime.utcnow()

    # ------------------------------------------------------------------
    # Sync to DB
    # ------------------------------------------------------------------

    def sync_messages(
        self,
        creds: Credentials,
        db: Session,
        user_id: int,
        limit: int = 20,
    ) -> dict:
        """
        Fetch messages from Gmail and store new ones in DB.

        Skips duplicates (by message_id). Returns a summary dict.
        """
        raw_list = self.get_messages(creds, limit=limit)
        synced = 0

        for item in raw_list:
            message_id = item.get("id", "")
            if not message_id:
                continue

            # Skip if already stored
            existing = (
                db.query(Message)
                .filter_by(user_id=user_id, message_id=message_id)
                .first()
            )
            if existing:
                continue

            raw = self.get_message(creds, message_id)
            if not raw:
                continue

            parsed = self.parse_message(raw)
            if not parsed:
                continue

            msg = Message(
                user_id=user_id,
                message_id=parsed["message_id"],
                thread_id=parsed.get("thread_id"),
                source=MessageSource.GMAIL,
                sender=parsed.get("sender", ""),
                recipient=parsed.get("recipient"),
                subject=parsed.get("subject"),
                body=parsed.get("body", ""),
                priority=MessagePriority.MEDIUM,
                status=MessageStatus.UNREAD,
                received_at=parsed.get("received_at") or datetime.utcnow(),
            )
            db.add(msg)
            synced += 1

        db.commit()

        total_stored = (
            db.query(Message)
            .filter_by(user_id=user_id, source=MessageSource.GMAIL)
            .count()
        )

        self.logger.info(
            "GmailAgent.sync_messages: synced=%d total_stored=%d for user_id=%d",
            synced,
            total_stored,
            user_id,
        )

        return {"synced": synced, "total_stored": total_stored}

    def list_stored_messages(
        self,
        db: Session,
        user_id: int,
        limit: int = 20,
        unread_only: bool = False,
    ) -> list[Message]:
        """
        List stored Gmail messages from DB for a user.

        Returns:
            List of Message objects.
        """
        query = db.query(Message).filter_by(
            user_id=user_id,
            source=MessageSource.GMAIL,
        )
        if unread_only:
            query = query.filter(Message.status == MessageStatus.UNREAD)

        return (
            query.order_by(Message.received_at.desc())
            .limit(limit)
            .all()
        )
