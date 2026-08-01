"""Planner routes — daily briefing and task orchestration."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models.user import User
from services.oauth import get_credentials

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/planner", tags=["Planner"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class BriefingResponse(BaseModel):
    date: Optional[str] = None
    executive_summary: Optional[str] = None
    critical_items: list = []
    pending_work: list = []
    upcoming_deadlines: list = []
    recommended_priorities: list = []
    risks: list = []
    next_actions: list = []


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/briefing", response_model=BriefingResponse)
async def daily_briefing(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a daily executive briefing for the current user."""
    from agents.planner_agent import PlannerAgent
    from datetime import datetime

    today_date = datetime.utcnow().strftime("%Y-%m-%d")

    try:
        # Google credentials are optional — briefing works without them
        creds = get_credentials(current_user.id, db)
        result = await PlannerAgent().generate_daily_briefing(
            user_id=current_user.id,
            db=db,
            creds=creds,
        )
        if not isinstance(result, dict):
            result = {}
            
        return BriefingResponse(
            date=result.get("date") or today_date,
            executive_summary=result.get("executive_summary") or "Your daily executive briefing is ready.",
            critical_items=result.get("critical_items", []),
            pending_work=result.get("pending_work", []),
            upcoming_deadlines=result.get("upcoming_deadlines", []),
            recommended_priorities=result.get("recommended_priorities", []),
            risks=result.get("risks", []),
            next_actions=result.get("next_actions", []),
        )
    except Exception as exc:
        logger.error("Daily briefing failed or validated incorrectly for user %d: %s", current_user.id, exc, exc_info=True)
        return BriefingResponse(
            date=today_date,
            executive_summary="AI briefing generation encountered an error. Showing offline fallback summary.",
            critical_items=[],
            pending_work=[],
            upcoming_deadlines=[],
            recommended_priorities=[],
            risks=[],
            next_actions=["Review communications manually in the Inbox tab."],
        )
