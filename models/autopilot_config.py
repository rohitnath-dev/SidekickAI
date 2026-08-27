"""AutoPilotConfig model — persists user Auto Pilot toggle and configuration."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class AutoPilotConfig(Base):
    """User-specific Auto Pilot configuration and background status."""

    __tablename__ = "autopilot_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auto_archive_newsletters: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auto_draft_replies: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auto_extract_memory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auto_extract_tasks: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)  # active, idle, processing, paused, waiting_for_connection, error
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    processed_today_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    actions_taken_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationship
    user: Mapped["User"] = relationship("User", backref="autopilot_config")  # noqa: F821

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "is_enabled": self.is_enabled,
            "auto_archive_newsletters": self.auto_archive_newsletters,
            "auto_draft_replies": self.auto_draft_replies,
            "auto_extract_memory": self.auto_extract_memory,
            "auto_extract_tasks": self.auto_extract_tasks,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_status": self.last_status,
            "last_error": self.last_error,
            "processed_today_count": self.processed_today_count,
            "actions_taken_count": self.actions_taken_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<AutoPilotConfig(user_id={self.user_id}, is_enabled={self.is_enabled}, status='{self.last_status}')>"
