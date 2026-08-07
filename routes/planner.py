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
    from routes.gmail import get_active_providers
    active_providers = get_active_providers(current_user.id, db)
    if not active_providers:
        logger.warning("User %d requested briefing but has no active integrations.", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No connected integration accounts found. Connect an integration in Settings.",
        )

    logger.info("Generating daily briefing for user %d with active integrations: %s", current_user.id, active_providers)
    creds = get_credentials(current_user.id, db)

    try:
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
        err_msg = str(exc)
        if "429" in err_msg or "rate limit" in err_msg.lower():
            friendly_summary = (
                "AI analysis temporarily unavailable. Please check your LLM API key in settings or "
                "wait a short while, as the OpenRouter API rate limit has been exceeded (429)."
            )
        elif "401" in err_msg or "auth" in err_msg.lower():
            friendly_summary = (
                "AI analysis temporarily unavailable. Please check your LLM API key in settings, "
                "as OpenRouter returned an authentication error (401)."
            )
        else:
            friendly_summary = (
                f"AI daily briefing generation failed. Please verify your LLM API connection in Settings. "
                f"Details: {err_msg}"
            )
            
        return BriefingResponse(
            date=today_date,
            executive_summary=friendly_summary,
            critical_items=[],
            pending_work=[],
            upcoming_deadlines=[],
            recommended_priorities=[],
            risks=[],
            next_actions=["Review incoming messages manually inside Inbox tab."],
        )
