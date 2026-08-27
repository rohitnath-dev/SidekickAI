"""
Sidekick AI — Executive Planner & Task Service

Core backend engine responsible for:
- Task extraction from messages, briefings, calendar events, and long-term memory
- Strict deduplication per user and source_item_id
- Algorithmic Next Best Action calculation
- Conflict detection (overlapping events, deadline overload)
- Smart Time-Blocking schedule calculation
- Task lifecycle management (complete, snooze, status, priority)
"""

from __future__ import annotations

from datetime import datetime, timedelta, date
import logging
from typing import Any, Dict, List, Optional
import json

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from database import SessionLocal
from models.planner_task import PlannerTask
from models.message import Message, MessagePriority
from models.user import User
from services.llm import LLMClient

logger = logging.getLogger(__name__)


class PlannerService:
    """Service layer handling Planner tasks, extraction, and schedule intelligence."""

    @staticmethod
    def get_user_tasks(
        db: Session,
        user_id: str,
        status_filter: Optional[str] = None,
        priority_filter: Optional[str] = None,
        timeframe: Optional[str] = None,
        source_filter: Optional[str] = None,
    ) -> List[PlannerTask]:
        """Fetch tasks for a user with optional status, priority, timeframe, and source filters."""
        query = db.query(PlannerTask).filter(PlannerTask.user_id == str(user_id))

        if status_filter and status_filter != "all":
            query = query.filter(PlannerTask.status == status_filter)
        elif not status_filter or status_filter == "active":
            query = query.filter(PlannerTask.status.in_(["pending", "in_progress", "waiting", "blocked", "snoozed"]))

        if priority_filter and priority_filter != "all":
            query = query.filter(PlannerTask.priority == priority_filter)

        if source_filter and source_filter != "all":
            query = query.filter(PlannerTask.source == source_filter)

        now = datetime.utcnow()
        today_start = datetime(now.year, now.month, now.day)
        today_end = today_start + timedelta(days=1)

        if timeframe == "today":
            query = query.filter(
                or_(
                    PlannerTask.due_date == None,
                    and_(PlannerTask.due_date >= today_start, PlannerTask.due_date < today_end),
                    PlannerTask.status == "in_progress"
                )
            )
        elif timeframe == "week":
            week_end = today_start + timedelta(days=7)
            query = query.filter(
                or_(
                    PlannerTask.due_date == None,
                    and_(PlannerTask.due_date >= today_start, PlannerTask.due_date < week_end)
                )
            )
        elif timeframe == "overdue":
            query = query.filter(
                PlannerTask.due_date < today_start,
                PlannerTask.status.notin_(["completed", "cancelled"])
            )
        elif timeframe == "waiting":
            query = query.filter(PlannerTask.status.in_(["waiting", "blocked"]))

        # Sort order: priority (critical first), then due_date
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        tasks = query.all()
        tasks.sort(key=lambda t: (priority_order.get(t.priority, 2), t.due_date or datetime.max))
        return tasks

    @staticmethod
    def create_task(
        db: Session,
        user_id: str,
        title: str,
        description: Optional[str] = None,
        source: str = "manual",
        source_item_id: Optional[str] = None,
        priority: str = "medium",
        status: str = "pending",
        origin: str = "user_created",
        due_date: Optional[datetime] = None,
        scheduled_time: Optional[str] = None,
        duration_minutes: Optional[int] = 30,
        context_reason: Optional[str] = None,
        suggested_action: Optional[str] = None,
        waiting_on: Optional[str] = None,
        confidence_score: int = 100,
    ) -> PlannerTask:
        """Create and persist a task with strict deduplication check."""
        user_id_str = str(user_id)

        # Deduplication check
        if source_item_id:
            existing = (
                db.query(PlannerTask)
                .filter(
                    PlannerTask.user_id == user_id_str,
                    PlannerTask.source_item_id == str(source_item_id),
                )
                .first()
            )
            if existing:
                # Update existing task instead of creating duplicate
                existing.title = title
                if description:
                    existing.description = description
                existing.priority = priority
                if due_date:
                    existing.due_date = due_date
                if scheduled_time:
                    existing.scheduled_time = scheduled_time
                if context_reason:
                    existing.context_reason = context_reason
                existing.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(existing)
                return existing

        task = PlannerTask(
            user_id=user_id_str,
            title=title.strip(),
            description=description.strip() if description else None,
            source=source,
            source_item_id=str(source_item_id) if source_item_id else None,
            origin=origin,
            priority=priority.lower() if priority.lower() in ("critical", "high", "medium", "low") else "medium",
            status=status.lower() if status.lower() in ("pending", "in_progress", "completed", "snoozed", "cancelled", "waiting", "blocked") else "pending",
            due_date=due_date,
            scheduled_time=scheduled_time,
            duration_minutes=duration_minutes or 30,
            context_reason=context_reason,
            suggested_action=suggested_action,
            waiting_on=waiting_on,
            confidence_score=confidence_score,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    @staticmethod
    def update_task(
        db: Session,
        task_id: int,
        user_id: str,
        **updates,
    ) -> Optional[PlannerTask]:
        """Update an existing task."""
        task = db.query(PlannerTask).filter(PlannerTask.id == task_id, PlannerTask.user_id == str(user_id)).first()
        if not task:
            return None

        for field, val in updates.items():
            if val is not None and hasattr(task, field):
                setattr(task, field, val)
                if field == "status" and val == "completed":
                    task.completed_at = datetime.utcnow()

        task.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(task)
        return task

    @staticmethod
    def delete_task(db: Session, task_id: int, user_id: str) -> bool:
        """Delete a task by ID."""
        task = db.query(PlannerTask).filter(PlannerTask.id == task_id, PlannerTask.user_id == str(user_id)).first()
        if not task:
            return False
        db.delete(task)
        db.commit()
        return True

    @staticmethod
    def extract_tasks_from_messages(db: Session, user_id: str) -> List[PlannerTask]:
        """Extract actionable tasks from processed messages with explicit action_items or reply_needed."""
        user_id_str = str(user_id)
        cutoff_24h = datetime.utcnow() - timedelta(hours=48)
        
        messages = (
            db.query(Message)
            .filter(
                Message.user_id == user_id_str,
                Message.is_processed == True,
                Message.received_at >= cutoff_24h,
            )
            .all()
        )

        extracted_tasks = []
        for msg in messages:
            source_id = f"msg_{msg.id}"
            
            # Check 1: Action items string from AI analysis
            if msg.action_items:
                items = [item.strip().lstrip("-* ").strip() for item in msg.action_items.split("\n") if item.strip()]
                for idx, item in enumerate(items):
                    item_source_id = f"msg_{msg.id}_item_{idx}"
                    prio = "high" if msg.priority.value in ("high", "critical") else "medium"
                    task = PlannerService.create_task(
                        db=db,
                        user_id=user_id_str,
                        title=item,
                        description=f"From {msg.sender}: {msg.subject or '(no subject)'}",
                        source=msg.source.value if hasattr(msg.source, "value") else str(msg.source),
                        source_item_id=item_source_id,
                        priority=prio,
                        status="pending",
                        origin="ai_extracted",
                        due_date=msg.received_at + timedelta(days=1),
                        context_reason=f"Extracted from message subject: {msg.subject or 'Direct Message'}",
                        suggested_action="Review → Draft Response" if msg.requires_reply else "Review Document",
                        confidence_score=int(msg.confidence_score or 85),
                    )
                    extracted_tasks.append(task)

            # Check 2: Unreplied message requiring response
            elif msg.requires_reply and msg.status.value == "unread":
                prio = "high" if msg.priority.value in ("high", "critical") else "medium"
                sender_name = msg.sender.split("<")[0].strip() if msg.sender else "Sender"
                task = PlannerService.create_task(
                    db=db,
                    user_id=user_id_str,
                    title=f"Reply to {sender_name}: {msg.subject or '(no subject)'}",
                    description=msg.summary or (msg.body or "")[:200],
                    source=msg.source.value if hasattr(msg.source, "value") else str(msg.source),
                    source_item_id=source_id,
                    priority=prio,
                    status="pending",
                    origin="ai_extracted",
                    due_date=msg.received_at + timedelta(hours=24),
                    context_reason="Direct question or action request requiring response",
                    suggested_action="Draft Reply",
                    confidence_score=int(msg.confidence_score or 90),
                )
                extracted_tasks.append(task)

        return extracted_tasks

    @staticmethod
    def extract_tasks_from_briefing(db: Session, user_id: str, briefing_data: Dict[str, Any]) -> List[PlannerTask]:
        """Convert Executive Daily Briefing items into structured persistent tasks."""
        if not briefing_data:
            return []

        user_id_str = str(user_id)
        created_tasks = []
        today_date = datetime.utcnow()

        # 1. Critical items -> Critical Priority Tasks
        critical_items = briefing_data.get("critical_items", [])
        for idx, item in enumerate(critical_items):
            title = item.get("item") or item.get("action") if isinstance(item, dict) else str(item)
            if not title:
                continue
            task = PlannerService.create_task(
                db=db,
                user_id=user_id_str,
                title=title,
                description=item.get("action") if isinstance(item, dict) else None,
                source="briefing",
                source_item_id=f"briefing_critical_{idx}_{hash(title) % 100000}",
                priority="critical",
                status="pending",
                origin="ai_extracted",
                due_date=today_date + timedelta(hours=12),
                context_reason="Identified as critical risk/bottleneck in Executive Daily Briefing",
                suggested_action="Immediate Execution",
                confidence_score=95,
            )
            created_tasks.append(task)

        # 2. Recommended Priorities -> High Priority Tasks
        priorities = briefing_data.get("recommended_priorities", [])
        for idx, item in enumerate(priorities):
            title = item.get("what") or item.get("item") if isinstance(item, dict) else str(item)
            if not title:
                continue
            task = PlannerService.create_task(
                db=db,
                user_id=user_id_str,
                title=title,
                source="briefing",
                source_item_id=f"briefing_priority_{idx}_{hash(title) % 100000}",
                priority="high",
                status="pending",
                origin="ai_extracted",
                due_date=today_date + timedelta(days=1),
                context_reason="Recommended focus area in Executive Daily Briefing",
                suggested_action="Plan Focus Time",
                confidence_score=90,
            )
            created_tasks.append(task)

        # 3. Next Actions -> Medium Priority Tasks
        next_actions = briefing_data.get("next_actions", [])
        for idx, item in enumerate(next_actions):
            title = str(item).strip()
            if not title or "Click 'Sync & Run AI'" in title:
                continue
            task = PlannerService.create_task(
                db=db,
                user_id=user_id_str,
                title=title,
                source="briefing",
                source_item_id=f"briefing_action_{idx}_{hash(title) % 100000}",
                priority="medium",
                status="pending",
                origin="ai_extracted",
                due_date=today_date + timedelta(days=2),
                suggested_action="Execute",
                confidence_score=85,
            )
            created_tasks.append(task)

        return created_tasks

    @staticmethod
    def calculate_next_best_action(tasks: List[PlannerTask]) -> Optional[Dict[str, Any]]:
        """Algorithmic selection of top 1 Next Best Action based on urgency, priority, and block status."""
        active_tasks = [t for t in tasks if t.status in ("pending", "in_progress")]
        if not active_tasks:
            return None

        # Sorting score: priority (critical 100, high 75, medium 50, low 25) + urgency bonus if due soon
        now = datetime.utcnow()
        priority_weights = {"critical": 100, "high": 75, "medium": 50, "low": 25}

        scored = []
        for t in active_tasks:
            score = priority_weights.get(t.priority, 50)
            if t.due_date:
                hours_left = (t.due_date - now).total_seconds() / 3600.0
                if hours_left < 0:
                    score += 40  # Overdue bonus
                elif hours_left <= 24:
                    score += 20  # Due today bonus

            if t.status == "in_progress":
                score += 15

            scored.append((score, t))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_task = scored[0][1]

        return {
            "task": top_task.to_dict(),
            "reason": top_task.context_reason or f"Highest priority ({top_task.priority.upper()}) action item pending review.",
            "suggested_action": top_task.suggested_action or "Review & Execute",
        }

    @staticmethod
    def detect_planning_conflicts(tasks: List[PlannerTask], calendar_events: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Detect schedule & workload conflicts."""
        conflicts = []
        now = datetime.utcnow()
        today_start = datetime(now.year, now.month, now.day)
        today_end = today_start + timedelta(days=1)

        # Conflict 1: Overdue work accumulation
        overdue_count = sum(1 for t in tasks if t.due_date and t.due_date < today_start and t.status not in ("completed", "cancelled"))
        if overdue_count > 0:
            conflicts.append({
                "type": "overdue_accumulation",
                "severity": "high" if overdue_count > 2 else "medium",
                "title": f"{overdue_count} Overdue Task{'s' if overdue_count > 1 else ''}",
                "description": f"You have {overdue_count} task{'s' if overdue_count > 1 else ''} past due. Reschedule or execute them to clear backlog.",
                "action": "Review Overdue Tasks",
            })

        # Conflict 2: Critical / High Priority overload today
        high_prio_today = [t for t in tasks if t.priority in ("critical", "high") and t.status in ("pending", "in_progress")]
        if len(high_prio_today) >= 4:
            conflicts.append({
                "type": "workload_overload",
                "severity": "high",
                "title": "High Priority Workload Density",
                "description": f"{len(high_prio_today)} high/critical priority tasks are active today. Consider delegating or postponing non-essential items.",
                "action": "Re-prioritize Schedule",
            })

        # Conflict 3: Calendar overlap (if events provided)
        if calendar_events and len(calendar_events) >= 2:
            # Sort calendar events by start time and check overlaps
            try:
                sorted_events = sorted(calendar_events, key=lambda e: e.get("start", {}).get("dateTime") or e.get("start", {}).get("date") or "")
                for i in range(len(sorted_events) - 1):
                    e1_start = sorted_events[i].get("start", {}).get("dateTime")
                    e1_end = sorted_events[i].get("end", {}).get("dateTime")
                    e2_start = sorted_events[i+1].get("start", {}).get("dateTime")

                    if e1_start and e1_end and e2_start and e1_end > e2_start:
                        conflicts.append({
                            "type": "calendar_overlap",
                            "severity": "critical",
                            "title": "Calendar Meeting Overlap",
                            "description": f"Event '{sorted_events[i].get('summary')}' overlaps with '{sorted_events[i+1].get('summary')}'.",
                            "action": "Reschedule Event",
                        })
            except Exception as cal_err:
                logger.warning("Error computing calendar overlap: %s", cal_err)

        return conflicts

    @staticmethod
    def generate_smart_time_blocks(tasks: List[PlannerTask], calendar_events: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Generate structured time-blocking schedule combining meetings & task allocations."""
        blocks = []
        
        # Standard work day slots: 09:00, 10:30, 12:00, 14:00, 15:30, 17:00
        time_slots = [
            ("09:00", "09:30"),
            ("09:30", "10:30"),
            ("10:30", "11:30"),
            ("11:30", "12:00"),
            ("12:00", "13:00"),
            ("13:00", "14:30"),
            ("14:30", "15:30"),
            ("15:30", "17:00"),
        ]

        active_tasks = [t for t in tasks if t.status in ("pending", "in_progress")]
        task_idx = 0

        for slot_start, slot_end in time_slots:
            if slot_start == "12:00":
                blocks.append({
                    "time_slot": f"{slot_start} - {slot_end}",
                    "title": "Lunch & Personal Break",
                    "category": "break",
                    "priority": "low",
                    "status": "scheduled",
                    "task_id": None,
                })
                continue

            if task_idx < len(active_tasks):
                task = active_tasks[task_idx]
                blocks.append({
                    "time_slot": f"{slot_start} - {slot_end}",
                    "title": task.title,
                    "category": task.source,
                    "priority": task.priority,
                    "status": task.status,
                    "task_id": task.id,
                    "suggested_action": task.suggested_action or "Execute Task",
                })
                task_idx += 1
            else:
                blocks.append({
                    "time_slot": f"{slot_start} - {slot_end}",
                    "title": "Open Focus / Buffer Slot",
                    "category": "focus",
                    "priority": "low",
                    "status": "available",
                    "task_id": None,
                })

        return blocks

    @staticmethod
    def get_planner_dashboard_data(db: Session, user_id: str) -> Dict[str, Any]:
        """Consolidate complete Planner dashboard data for response."""
        user_id_str = str(user_id)
        all_tasks = db.query(PlannerTask).filter(PlannerTask.user_id == user_id_str).all()

        now = datetime.utcnow()
        today_start = datetime(now.year, now.month, now.day)
        today_end = today_start + timedelta(days=1)
        week_end = today_start + timedelta(days=7)

        # Categorize tasks
        today_tasks = [t.to_dict() for t in all_tasks if (t.due_date and today_start <= t.due_date < today_end) or t.status == "in_progress" or (not t.due_date and t.status == "pending")]
        overdue_tasks = [t.to_dict() for t in all_tasks if t.due_date and t.due_date < today_start and t.status not in ("completed", "cancelled")]
        waiting_tasks = [t.to_dict() for t in all_tasks if t.status in ("waiting", "blocked")]

        # Group deadlines
        deadlines = {
            "today": [t.to_dict() for t in all_tasks if t.due_date and today_start <= t.due_date < today_end and t.status != "completed"],
            "tomorrow": [t.to_dict() for t in all_tasks if t.due_date and (today_start + timedelta(days=1)) <= t.due_date < (today_start + timedelta(days=2)) and t.status != "completed"],
            "this_week": [t.to_dict() for t in all_tasks if t.due_date and (today_start + timedelta(days=2)) <= t.due_date < week_end and t.status != "completed"],
            "later": [t.to_dict() for t in all_tasks if t.due_date and t.due_date >= week_end and t.status != "completed"],
        }

        # Weekly overview (Mon to Sun counts)
        current_weekday = now.weekday()  # Mon=0, Sun=6
        monday_start = today_start - timedelta(days=current_weekday)
        
        weekly_overview = []
        days_names = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        for i in range(7):
            d_start = monday_start + timedelta(days=i)
            d_end = d_start + timedelta(days=1)
            d_tasks = [t for t in all_tasks if t.due_date and d_start <= t.due_date < d_end]
            weekly_overview.append({
                "day": days_names[i],
                "date": d_start.strftime("%Y-%m-%d"),
                "task_count": len(d_tasks),
                "has_critical": any(t.priority == "critical" for t in d_tasks),
            })

        active_task_objects = [t for t in all_tasks if t.status in ("pending", "in_progress", "waiting", "blocked")]
        next_best = PlannerService.calculate_next_best_action(active_task_objects)
        conflicts = PlannerService.detect_planning_conflicts(all_tasks)
        time_blocks = PlannerService.generate_smart_time_blocks(active_task_objects)

        stats = {
            "total": len(all_tasks),
            "pending": sum(1 for t in all_tasks if t.status == "pending"),
            "in_progress": sum(1 for t in all_tasks if t.status == "in_progress"),
            "completed": sum(1 for t in all_tasks if t.status == "completed"),
            "overdue": len(overdue_tasks),
            "waiting": len(waiting_tasks),
        }

        return {
            "current_date": now.strftime("%Y-%m-%d"),
            "formatted_date": now.strftime("%A, %B %d, %Y"),
            "stats": stats,
            "next_best_action": next_best,
            "conflicts": conflicts,
            "today_plan": today_tasks,
            "deadlines": deadlines,
            "overdue_tasks": overdue_tasks,
            "waiting_tasks": waiting_tasks,
            "time_blocks": time_blocks,
            "weekly_overview": weekly_overview,
            "all_tasks": [t.to_dict() for t in all_tasks],
        }
