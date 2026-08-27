"""Planner routes — daily briefing, task lifecycle, and executive planner orchestration."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models.user import User
from services.planner_service import PlannerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/planner", tags=["Planner"])


def get_briefing_cache_path(user_id: Any) -> str:
    return os.path.join(os.getcwd(), f"briefing_cache_{user_id}.json")


def load_cached_briefing(user_id: Any) -> dict | None:
    path = get_briefing_cache_path(user_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load cached briefing for user %s: %s", user_id, e)
    return None


def cache_briefing(user_id: Any, data: dict) -> None:
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


class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    description: Optional[str] = None
    source: str = Field(default="manual")
    priority: str = Field(default="medium")  # critical, high, medium, low
    status: str = Field(default="pending")    # pending, in_progress, waiting, blocked
    due_date: Optional[str] = None           # ISO format string or YYYY-MM-DD
    scheduled_time: Optional[str] = None
    duration_minutes: Optional[int] = 30
    context_reason: Optional[str] = None
    suggested_action: Optional[str] = None
    waiting_on: Optional[str] = None


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[str] = None
    scheduled_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    context_reason: Optional[str] = None
    suggested_action: Optional[str] = None
    waiting_on: Optional[str] = None


class TaskSnoozeRequest(BaseModel):
    days: int = Field(default=1, ge=1, le=30)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/dashboard")
async def get_planner_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get consolidated Executive Planner Dashboard:
    - today_plan
    - upcoming_deadlines
    - overdue_tasks
    - waiting_tasks
    - next_best_action
    - conflicts
    - time_blocks
    - weekly_overview
    - stats
    """
    try:
        # Also ensure AI task extraction runs on recent messages & briefing
        PlannerService.extract_tasks_from_messages(db=db, user_id=current_user.id)
        
        cached_briefing = load_cached_briefing(current_user.id)
        if cached_briefing:
            PlannerService.extract_tasks_from_briefing(db=db, user_id=current_user.id, briefing_data=cached_briefing)

        dashboard_data = PlannerService.get_planner_dashboard_data(db=db, user_id=current_user.id)
        return dashboard_data

    except Exception as exc:
        logger.error("Failed to compile planner dashboard for user %s: %s", current_user.id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load planner dashboard.",
        )


@router.get("/briefing", response_model=BriefingResponse)
async def daily_briefing(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the cached daily briefing or return a fallback when no briefing is generated yet."""
    today_date = datetime.utcnow().strftime("%Y-%m-%d")

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


@router.get("/tasks")
async def get_planner_tasks(
    status: Optional[str] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    timeframe: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Query list of tasks with optional filters."""
    tasks = PlannerService.get_user_tasks(
        db=db,
        user_id=current_user.id,
        status_filter=status,
        priority_filter=priority,
        timeframe=timeframe,
        source_filter=source,
    )
    return [t.to_dict() for t in tasks]


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
async def create_planner_task(
    req: TaskCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually create a new task."""
    due_dt = None
    if req.due_date:
        try:
            due_dt = datetime.fromisoformat(req.due_date.replace("Z", "+00:00"))
        except ValueError:
            try:
                due_dt = datetime.strptime(req.due_date, "%Y-%m-%d")
            except ValueError:
                pass

    task = PlannerService.create_task(
        db=db,
        user_id=current_user.id,
        title=req.title,
        description=req.description,
        source=req.source,
        priority=req.priority,
        status=req.status,
        origin="user_created",
        due_date=due_dt,
        scheduled_time=req.scheduled_time,
        duration_minutes=req.duration_minutes,
        context_reason=req.context_reason,
        suggested_action=req.suggested_action,
        waiting_on=req.waiting_on,
    )
    return task.to_dict()


@router.patch("/tasks/{task_id}")
async def update_planner_task(
    task_id: int,
    req: TaskUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update task properties."""
    updates = req.dict(exclude_unset=True)
    if "due_date" in updates and updates["due_date"]:
        try:
            updates["due_date"] = datetime.fromisoformat(updates["due_date"].replace("Z", "+00:00"))
        except ValueError:
            try:
                updates["due_date"] = datetime.strptime(updates["due_date"], "%Y-%m-%d")
            except ValueError:
                updates["due_date"] = None

    task = PlannerService.update_task(
        db=db,
        task_id=task_id,
        user_id=current_user.id,
        **updates,
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return task.to_dict()


@router.delete("/tasks/{task_id}")
async def delete_planner_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a task by ID."""
    success = PlannerService.delete_task(db=db, task_id=task_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return {"status": "success", "deleted_id": task_id}


@router.post("/tasks/{task_id}/complete")
async def complete_planner_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a task as completed."""
    task = PlannerService.update_task(
        db=db,
        task_id=task_id,
        user_id=current_user.id,
        status="completed",
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return task.to_dict()


@router.post("/tasks/{task_id}/snooze")
async def snooze_planner_task(
    task_id: int,
    req: TaskSnoozeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Snooze a task by N days."""
    new_due = datetime.utcnow() + timedelta(days=req.days)
    task = PlannerService.update_task(
        db=db,
        task_id=task_id,
        user_id=current_user.id,
        status="snoozed",
        due_date=new_due,
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return task.to_dict()


@router.post("/plan-my-day")
async def plan_my_day(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Trigger AI Plan My Day extraction & optimization from recent communications, briefing, and memory.
    """
    try:
        # Extract from messages
        msg_tasks = PlannerService.extract_tasks_from_messages(db=db, user_id=current_user.id)
        
        # Extract from briefing
        cached_briefing = load_cached_briefing(current_user.id)
        briefing_tasks = []
        if cached_briefing:
            briefing_tasks = PlannerService.extract_tasks_from_briefing(db=db, user_id=current_user.id, briefing_data=cached_briefing)

        dashboard_data = PlannerService.get_planner_dashboard_data(db=db, user_id=current_user.id)
        return {
            "status": "success",
            "message": f"Successfully planned your day. Extracted {len(msg_tasks) + len(briefing_tasks)} actionable items.",
            "dashboard": dashboard_data,
        }
    except Exception as exc:
        logger.error("Plan My Day failed for user %s: %s", current_user.id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to optimize daily plan: {str(exc)}",
        )
