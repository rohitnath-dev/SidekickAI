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
import os
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/planner", tags=["Planner"])

def get_briefing_cache_path(user_id: int) -> str:
    return os.path.join(os.getcwd(), f"briefing_cache_{user_id}.json")

def load_cached_briefing(user_id: int) -> dict | None:
    path = get_briefing_cache_path(user_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load cached briefing for user %s: %s", user_id, e)
    return None

def cache_briefing(user_id: int, data: dict) -> None:
    path = get_briefing_cache_path(user_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Failed to cache briefing for user %s: %s", user_id, e)


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
    """Get the cached daily briefing or return a fallback when no briefing is generated yet."""
    from datetime import datetime
    today_date = datetime.utcnow().strftime("%Y-%m-%d")
    
    # Check if there are active integrations first
    from routes.gmail import get_active_providers
    active_providers = get_active_providers(current_user.id, db)
    if not active_providers:
        logger.warning("User %s requested briefing but has no active integrations.", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No connected integration accounts found. Connect an integration in Settings.",
        )

    # 1. Load from file cache or DB AIRun model
    cached = load_cached_briefing(current_user.id)
    if not cached:
        try:
            from models.ai_run import AIRun
            run = db.query(AIRun).filter(
                AIRun.user_id == str(current_user.id),
                AIRun.briefing_data_json != None
            ).order_by(AIRun.started_at.desc()).first()
            if run:
                cached = run.get_briefing_data()
        except Exception as e:
            logger.warning("Failed to load briefing from DB for user %s: %s", current_user.id, e)

    if cached:
        logger.info("Serving daily briefing from cache/DB for user %s", current_user.id)
        return BriefingResponse(
            date=cached.get("date") or today_date,
            executive_summary=cached.get("executive_summary") or "Your daily executive briefing.",
            critical_items=cached.get("critical_items", []),
            pending_work=cached.get("pending_work", []),
            upcoming_deadlines=cached.get("upcoming_deadlines", []),
            recommended_priorities=cached.get("recommended_priorities", []),
            risks=cached.get("risks", []),
            next_actions=cached.get("next_actions", []),
        )
        
    # 2. If no briefing exists, return fallback with accurate 'Sync & Run AI' copy.
    logger.info("No cached briefing found for user %s, returning up-to-date fallback state", current_user.id)
    return BriefingResponse(
        date=today_date,
        executive_summary="No executive briefing has been generated yet. Please click 'Sync & Run AI' to analyze your data.",
        critical_items=[],
        pending_work=[],
        upcoming_deadlines=[],
        recommended_priorities=[],
        risks=[],
        next_actions=["Click 'Sync & Run AI' to generate a daily briefing."],
    )
