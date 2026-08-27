"""PlannerTask model — structured, persistent tasks for Sidekick AI Planner."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class PlannerTask(Base):
    """Authoritative persistent record of a planned task or commitment."""

    __tablename__ = "planner_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Source & deduplication
    source: Mapped[str] = mapped_column(String(50), default="manual", nullable=False, index=True)
    source_item_id: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, index=True)
    origin: Mapped[str] = mapped_column(String(50), default="user_created", nullable=False)  # ai_extracted, user_created, calendar_event

    # Task attributes
    priority: Mapped[str] = mapped_column(String(20), default="medium", nullable=False, index=True)  # critical, high, medium, low
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)  # pending, in_progress, completed, snoozed, cancelled, waiting, blocked

    # Dates & Timing
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    scheduled_time: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Reasoning & Context
    context_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_action: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    waiting_on: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    confidence_score: Mapped[Optional[int]] = mapped_column(Integer, default=100, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationship
    user: Mapped["User"] = relationship("User", backref="planner_tasks")  # noqa: F821

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "source_item_id": self.source_item_id,
            "origin": self.origin,
            "priority": self.priority,
            "status": self.status,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "scheduled_time": self.scheduled_time,
            "duration_minutes": self.duration_minutes,
            "context_reason": self.context_reason,
            "suggested_action": self.suggested_action,
            "waiting_on": self.waiting_on,
            "confidence_score": self.confidence_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "is_overdue": bool(self.due_date and self.due_date < datetime.utcnow() and self.status not in ("completed", "cancelled")),
        }

    def __repr__(self) -> str:
        return f"<PlannerTask(id={self.id}, title='{self.title}', priority='{self.priority}', status='{self.status}')>"
