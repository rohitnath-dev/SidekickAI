"""Calendar routes — Google Calendar integration."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models.user import User
from services.oauth import get_credentials

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calendar", tags=["Calendar"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class EventResponse(BaseModel):
    id: str
    title: str
    start: str
    end: str
    attendees: list[str] = []
    location: Optional[str] = None
    description: Optional[str] = None


class CreateEventRequest(BaseModel):
    title: str
    start: str  # ISO 8601
    end: str    # ISO 8601
    description: str = ""
    attendees: list[str] = []


# ---------------------------------------------------------------------------
# Helper — ensure Google is connected
# ---------------------------------------------------------------------------

def _require_google(user_id: int, db: Session):
    creds = get_credentials(user_id, db)
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Google account not connected. Call /gmail/authorize first.",
        )
    return creds


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/today", response_model=list[EventResponse])
async def get_today(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return today's Google Calendar events."""
    from agents.calendar_agent import CalendarAgent

    creds = _require_google(current_user.id, db)
    try:
        events = await CalendarAgent().get_todays_events(creds)
    except Exception as exc:
        logger.error("Calendar today failed for user %d: %s", current_user.id, exc)
        from services.oauth import handle_google_error
        handle_google_error(exc)

    return [
        EventResponse(
            id=e.get("id", ""),
            title=e.get("title", ""),
            start=e.get("start", ""),
            end=e.get("end", ""),
            attendees=e.get("attendees", []),
            location=e.get("location"),
            description=e.get("description"),
        )
        for e in events
    ]


@router.get("/upcoming", response_model=list[EventResponse])
async def get_upcoming(
    days: int = Query(default=7, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return upcoming Google Calendar events."""
    from agents.calendar_agent import CalendarAgent

    creds = _require_google(current_user.id, db)
    try:
        events = await CalendarAgent().get_upcoming_events(creds, days=days)
    except Exception as exc:
        logger.error("Calendar upcoming failed for user %d: %s", current_user.id, exc)
        from services.oauth import handle_google_error
        handle_google_error(exc)

    return [
        EventResponse(
            id=e.get("id", ""),
            title=e.get("title", ""),
            start=e.get("start", ""),
            end=e.get("end", ""),
            attendees=e.get("attendees", []),
            location=e.get("location"),
            description=e.get("description"),
        )
        for e in events
    ]


@router.post("/events", response_model=EventResponse)
async def create_event(
    request: CreateEventRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new Google Calendar event."""
    from agents.calendar_agent import CalendarAgent

    creds = _require_google(current_user.id, db)
    try:
        event = await CalendarAgent().create_event(
            creds=creds,
            title=request.title,
            start=request.start,
            end=request.end,
            description=request.description,
            attendees=request.attendees,
        )
    except Exception as exc:
        logger.error("Calendar create event failed for user %d: %s", current_user.id, exc)
        from services.oauth import handle_google_error
        handle_google_error(exc)

    return EventResponse(
        id=event.get("id", ""),
        title=event.get("summary", request.title),
        start=event.get("start", {}).get("dateTime", request.start),
        end=event.get("end", {}).get("dateTime", request.end),
        attendees=[a.get("email", "") for a in event.get("attendees", [])],
        location=event.get("location"),
        description=event.get("description"),
    )
