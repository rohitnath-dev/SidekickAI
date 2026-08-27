"""AutoPilotActivity model — stores traceable log of automated actions."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class AutoPilotActivity(Base):
    """Traceable activity log entry for Auto Pilot decisions and actions."""

    __tablename__ = "autopilot_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    source: Mapped[str] = mapped_column(String(50), default="system", nullable=False)  # gmail, slack, telegram, twitter, system
    source_item_id: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)  # classified_newsletter, generated_reply_draft, extracted_memory, extracted_planner_task, updated_briefing

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="auto_executed", nullable=False)  # auto_executed, pending_user_review, skipped, failed
    confidence_score: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), default="low", nullable=False)  # low, medium, high

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationship
    user: Mapped["User"] = relationship("User", backref="autopilot_activities")  # noqa: F821

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "source": self.source,
            "source_item_id": self.source_item_id,
            "action_type": self.action_type,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "confidence_score": self.confidence_score,
            "risk_level": self.risk_level,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<AutoPilotActivity(id={self.id}, action_type='{self.action_type}', status='{self.status}')>"
