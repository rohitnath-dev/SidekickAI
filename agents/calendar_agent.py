"""
Calendar Agent

Google Calendar integration using google-api-python-client.
All API calls are run in a thread executor since the google client is synchronous.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class CalendarAgent(BaseAgent):
    """Google Calendar integration agent."""

    def __init__(self) -> None:
        super().__init__(agent_name="CalendarAgent")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_service(self, creds: Credentials):
        """Build a Google Calendar API service object."""
        return build("calendar", "v3", credentials=creds)

    def _parse_event(self, event: dict) -> dict:
        """Normalise a Google Calendar event dict."""
        start = event.get("start", {})
        end = event.get("end", {})
        attendees = event.get("attendees", [])
        return {
            "id": event.get("id", ""),
            "title": event.get("summary", "(no title)"),
            "start": start.get("dateTime") or start.get("date", ""),
            "end": end.get("dateTime") or end.get("date", ""),
            "attendees": [a.get("email", "") for a in attendees],
            "location": event.get("location"),
            "description": event.get("description"),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_todays_events(self, creds: Credentials) -> list[dict]:
        """
        List events for today (UTC boundaries).

        Returns:
            List of normalised event dicts.
        """
        now = datetime.now(timezone.utc)
        time_min = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        time_max = now.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()

        loop = asyncio.get_event_loop()
        try:
            service = self._build_service(creds)
            result = await loop.run_in_executor(
                None,
                lambda: service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute(),
            )
            events = result.get("items", [])
            return [self._parse_event(e) for e in events]
        except HttpError as exc:
            self.logger.error("CalendarAgent.get_todays_events failed: %s", exc)
            return []

    async def get_upcoming_events(
        self,
        creds: Credentials,
        days: int = 7,
    ) -> list[dict]:
        """
        List events for the next N days.

        Returns:
            List of normalised event dicts.
        """
        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        time_max = (now + timedelta(days=days)).isoformat()

        loop = asyncio.get_event_loop()
        try:
            service = self._build_service(creds)
            result = await loop.run_in_executor(
                None,
                lambda: service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute(),
            )
            events = result.get("items", [])
            return [self._parse_event(e) for e in events]
        except HttpError as exc:
            self.logger.error("CalendarAgent.get_upcoming_events failed: %s", exc)
            return []

    async def create_event(
        self,
        creds: Credentials,
        title: str,
        start: str,
        end: str,
        description: str = "",
        attendees: list[str] = [],
    ) -> dict:
        """
        Create a Google Calendar event.

        Args:
            creds: Google OAuth credentials.
            title: Event summary/title.
            start: ISO 8601 datetime string for the start time.
            end: ISO 8601 datetime string for the end time.
            description: Optional event description.
            attendees: List of attendee email addresses.

        Returns:
            The created event dict (normalised), or {} on failure.
        """
        attendee_list = [{"email": email} for email in attendees]
        event_body: dict = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start, "timeZone": "UTC"},
            "end": {"dateTime": end, "timeZone": "UTC"},
            "attendees": attendee_list,
        }

        loop = asyncio.get_event_loop()
        try:
            service = self._build_service(creds)
            created = await loop.run_in_executor(
                None,
                lambda: service.events()
                .insert(calendarId="primary", body=event_body)
                .execute(),
            )
            return self._parse_event(created)
        except HttpError as exc:
            self.logger.error("CalendarAgent.create_event failed: %s", exc)
            return {}
