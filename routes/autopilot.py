"""Auto Pilot routes — control toggle, dashboard overview, activities, and background run triggers."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models.user import User
from services.autopilot_service import AutoPilotService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/autopilot", tags=["Auto Pilot"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ToggleAutoPilotRequest(BaseModel):
    is_enabled: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status")
async def get_autopilot_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current Auto Pilot status and configuration."""
    try:
        summary = AutoPilotService.get_dashboard_summary(db=db, user_id=current_user.id)
        return summary
    except Exception as exc:
        logger.error("Failed to fetch autopilot status for user %s: %s", current_user.id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load Auto Pilot status.",
        )


@router.post("/toggle")
async def toggle_autopilot(
    req: ToggleAutoPilotRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enable or disable Auto Pilot with database persistence."""
    try:
        config = AutoPilotService.toggle_autopilot(db=db, user_id=current_user.id, is_enabled=req.is_enabled)
        # If enabled, trigger a background cycle run immediately
        if req.is_enabled:
            import asyncio
            asyncio.create_task(AutoPilotService.run_autopilot_cycle(db=db, user_id=current_user.id))
        
        summary = AutoPilotService.get_dashboard_summary(db=db, user_id=current_user.id)
        return {
            "status": "success",
            "message": f"Auto Pilot is now {'active' if req.is_enabled else 'disabled'}.",
            "config": config.to_dict(),
            "summary": summary,
        }
    except Exception as exc:
        logger.error("Failed to toggle Auto Pilot for user %s: %s", current_user.id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle Auto Pilot state.",
        )


@router.get("/dashboard-summary")
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get compact summary formatted specifically for Dashboard Section 2."""
    summary = AutoPilotService.get_dashboard_summary(db=db, user_id=current_user.id)
    return summary


@router.get("/activity")
async def get_activity_log(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch paginated Auto Pilot activity log entries."""
    from models.autopilot_activity import AutoPilotActivity
    activities = (
        db.query(AutoPilotActivity)
        .filter(AutoPilotActivity.user_id == str(current_user.id))
        .order_by(AutoPilotActivity.created_at.desc())
        .limit(limit)
        .all()
    )
    return [a.to_dict() for a in activities]


@router.get("/needs-attention")
async def get_needs_attention(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch items held for user review in the Proactive Action Queue."""
    summary = AutoPilotService.get_dashboard_summary(db=db, user_id=current_user.id)
    return summary.get("pending_review_items", [])


@router.post("/trigger-run")
async def trigger_autopilot_run(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger an Auto Pilot background cycle."""
    try:
        res = await AutoPilotService.run_autopilot_cycle(db=db, user_id=current_user.id)
        summary = AutoPilotService.get_dashboard_summary(db=db, user_id=current_user.id)
        return {
            "status": "success",
            "cycle_result": res,
            "summary": summary,
        }
    except Exception as exc:
        logger.error("Failed to execute Auto Pilot trigger run for user %s: %s", current_user.id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Auto Pilot execution failed: {str(exc)}",
        )
