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
    def get_messages(
        self,
        creds: Credentials,
        limit: int = 100,
        unread_only: bool = False,
        query_override: Optional[str] = None,
    ) -> list[dict]:
        """
        List Gmail messages across all categories.

        Returns:
            List of dicts with 'id' and 'threadId' keys.
        """
        try:
            service = self._build_service(creds)
            if query_override:
                query = query_override
            elif unread_only:
                query = "is:unread OR newer_than:2d"
            else:
                query = "newer_than:7d"
            
            self.logger.info("GmailAgent.get_messages query: '%s'", query)
            result = (
                service.users()
                .messages()
                .list(userId="me", maxResults=limit, q=query)
                .execute()
            )
            return result.get("messages", [])
        except HttpError as exc:
            self.logger.error("GmailAgent.get_messages failed: %s", exc)
            raise exc

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

        # Extract category from labelIds
        label_ids = gmail_raw.get("labelIds", [])
        category = "primary"  # default
        if "CATEGORY_PERSONAL" in label_ids:
            category = "primary"
        elif "CATEGORY_PROMOTIONS" in label_ids:
            category = "promotions"
        elif "CATEGORY_SOCIAL" in label_ids:
            category = "social"
        elif "CATEGORY_UPDATES" in label_ids:
            category = "updates"
        elif "CATEGORY_FORUMS" in label_ids:
            category = "forums"

        return {
            "message_id": gmail_raw.get("id", ""),
            "thread_id": gmail_raw.get("threadId", ""),
            "sender": headers.get("From", ""),
            "recipient": headers.get("To", ""),
            "subject": headers.get("Subject", ""),
            "received_at": self._parse_date(headers.get("Date", "")),
            "body": body,
            "category": category,
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
        Recursively extract and combine the text/plain or text/html bodies
        from a Gmail message payload.
        """
        plain_text_parts = []
        html_text_parts = []

        def recurse(part: dict):
            mime_type = part.get("mimeType", "")
            body_data = part.get("body", {}).get("data", "")

            if body_data:
                decoded = self._decode_base64(body_data)
                if mime_type == "text/plain":
                    plain_text_parts.append(decoded)
                elif mime_type == "text/html":
                    html_text_parts.append(decoded)
            
            parts = part.get("parts", [])
            for subpart in parts:
                recurse(subpart)

        recurse(payload)

        # Prefer plain text if found, otherwise convert HTML to plain text
        if plain_text_parts:
            body = "\n".join(plain_text_parts).strip()
        elif html_text_parts:
            combined_html = "\n".join(html_text_parts).strip()
            body = self._strip_html(combined_html)
        else:
            body = ""
            
        self.logger.info("Email body length: %d chars", len(body))
        return body

    def _decode_base64(self, data: str) -> str:
        """Decode a Gmail base64url-encoded string to UTF-8 text."""
        try:
            padded = data + "=" * (4 - len(data) % 4)
            decoded_bytes = base64.urlsafe_b64decode(padded)
            return decoded_bytes.decode("utf-8", errors="replace")
        except Exception as exc:
            self.logger.warning("GmailAgent._decode_base64 failed: %s", exc)
            return ""
    def _strip_html(self, html_content: str) -> str:
        """Remove HTML tags and decode HTML entities from a string, preserving spacing."""
        import html
        from html.parser import HTMLParser

        class HTMLToTextParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text_parts = []
                self.ignore_tags = {"script", "style", "head", "title", "meta", "link"}
                self.current_tag = None
                self.ignore_depth = 0

            def handle_starttag(self, tag, attrs):
                self.current_tag = tag.lower()
                if self.current_tag in self.ignore_tags:
                    self.ignore_depth += 1
                if self.current_tag in {"p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "li"}:
                    if self.text_parts and not self.text_parts[-1].endswith("\n"):
                        self.text_parts.append("\n")

            def handle_endtag(self, tag):
                tag_lower = tag.lower()
                if tag_lower in self.ignore_tags:
                    self.ignore_depth = max(0, self.ignore_depth - 1)
                if tag_lower in {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "li"}:
                    if self.text_parts and not self.text_parts[-1].endswith("\n"):
                        self.text_parts.append("\n")

            def handle_data(self, data):
                if self.ignore_depth == 0:
                    self.text_parts.append(data)

            def get_text(self) -> str:
                raw_text = "".join(self.text_parts)
                decoded_text = html.unescape(raw_text).replace("\xa0", " ")
                lines = []
                for line in decoded_text.splitlines():
                    cleaned_line = line.strip()
                    if cleaned_line:
                        lines.append(cleaned_line)
                    elif lines and lines[-1] != "":
                        lines.append("")
                return "\n".join(lines).strip()

        try:
            parser = HTMLToTextParser()
            parser.feed(html_content)
            return parser.get_text()
        except Exception as exc:
            self.logger.warning("HTMLToTextParser parsing failed: %s. Falling back to simple regex.", exc)
            import re
            text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = html.unescape(text).replace("\xa0", " ")
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
    async def sync_messages(
        self,
        creds: Credentials,
        db: Session,
        user_id: int,
        limit: int = 20,
        unread_only: bool = False,
        category: str = "primary",
    ) -> dict:
        """
        Fetch messages from Gmail and store new ones in DB.

        Skips duplicates (by message_id). Returns a summary dict.
        """
        # Map category to Gmail API labels
        label_ids = ["INBOX"]
        if category == "primary":
            label_ids.append("CATEGORY_PERSONAL")
        elif category == "promotions":
            label_ids.append("CATEGORY_PROMOTIONS")
        elif category == "social":
            label_ids.append("CATEGORY_SOCIAL")
        elif category == "updates":
            label_ids.append("CATEGORY_UPDATES")
        elif category == "forums":
            label_ids.append("CATEGORY_FORUMS")
        else:
            label_ids.append("CATEGORY_PERSONAL")

        # Find the most recent Gmail message in the DB
        last_msg = (
            db.query(Message)
            .filter_by(user_id=user_id, source=MessageSource.GMAIL)
            .order_by(Message.received_at.desc())
            .first()
        )
        
        query_override = None
        category_title = category.capitalize()
        if last_msg:
            epoch = int(last_msg.received_at.timestamp()) + 1
            query_override = f"after:{epoch}"
            self.logger.info("Fetching Gmail %s emails since: %s", category_title, last_msg.received_at.isoformat())
        else:
            self.logger.info("Fetching Gmail %s emails since: None", category_title)

        raw_list = self.get_messages(
            creds,
            limit=limit,
            unread_only=unread_only,
            query_override=query_override,
            label_ids=label_ids,
        )
        
        self.logger.info("Found %d raw email headers in Gmail API list response.", len(raw_list))

        synced = 0
        primary_count = 0
        promotions_count = 0

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
                category=parsed.get("category", "primary"),
                priority=MessagePriority.MEDIUM,
                status=MessageStatus.UNREAD,
                received_at=parsed.get("received_at") or datetime.utcnow(),
            )
            db.add(msg)
            db.commit()
            db.refresh(msg)
            
            # Log stored email details and category counts
            self.logger.info("Stored email: %s from %s", parsed.get("subject", "(no subject)"), parsed.get("sender", "unknown"))
            self.logger.info("Stored content for: %s", parsed.get("subject", "(no subject)"))

            cat = parsed.get("category", "primary")
            if cat == "primary":
                primary_count += 1
            elif cat == "promotions":
                promotions_count += 1
            
            # Run AI pipeline
            try:
                from services.ai_pipeline import process_message_ai
                await process_message_ai(db, msg)
            except Exception as e:
                self.logger.error("Failed to run AI pipeline during sync: %s", e)
                
            synced += 1

        # Found X new emails, Y Primary, Z Promotions log
        self.logger.info("Found %d new emails, %d Primary, %d Promotions", synced, primary_count, promotions_count)

        total_stored = (
            db.query(Message)
            .filter_by(user_id=user_id, source=MessageSource.GMAIL)
            .count()
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

    def send_reply(
        self,
        creds: Credentials,
        message: Message,
        reply_body: str,
    ) -> dict:
        """
        Send a reply to a specific email message via Gmail API.
        """
        from email.mime.text import MIMEText
        import base64

        service = self._build_service(creds)

        # Build MIME message
        mime_msg = MIMEText(reply_body)
        mime_msg["to"] = message.sender
        mime_msg["from"] = "me"

        subject = message.subject or ""
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        mime_msg["subject"] = subject

        # Thread threading headers
        if message.message_id:
            mime_msg["In-Reply-To"] = message.message_id
            mime_msg["References"] = message.message_id

        raw_msg = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("utf-8")

        body = {
            "raw": raw_msg,
        }
        if message.thread_id:
            body["threadId"] = message.thread_id

        try:
            result = service.users().messages().send(userId="me", body=body).execute()
            return result
        except HttpError as exc:
            self.logger.error("GmailAgent.send_reply failed: %s", exc)
            raise exc
