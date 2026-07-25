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

    # Google credentials are optional — briefing works without them
    creds = get_credentials(current_user.id, db)

    try:
        result = await PlannerAgent().generate_daily_briefing(
            user_id=current_user.id,
            db=db,
            creds=creds,
        )
    except Exception as exc:
        logger.error("Daily briefing failed for user %d: %s", current_user.id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return BriefingResponse(
        date=result.get("date"),
        executive_summary=result.get("executive_summary"),
        critical_items=result.get("critical_items", []),
        pending_work=result.get("pending_work", []),
        upcoming_deadlines=result.get("upcoming_deadlines", []),
        recommended_priorities=result.get("recommended_priorities", []),
        risks=result.get("risks", []),
        next_actions=result.get("next_actions", []),
    )
