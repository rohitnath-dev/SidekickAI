"""AI Run model for persistent job tracking and authoritative dashboard state."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class AIRun(Base):
    """Authoritative persistent record of an AI Sync & Run operation."""

    __tablename__ = "ai_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    status: Mapped[str] = mapped_column(String(50), default="queued", nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(255), default="Job initialized", nullable=False)

    discovered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    synced_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    analyzed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    briefing_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    action_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    error_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    briefing_data_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    integrations_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def set_briefing_data(self, data: Optional[Dict[str, Any]]) -> None:
        if data is not None:
            self.briefing_data_json = json.dumps(data, ensure_ascii=False)
        else:
            self.briefing_data_json = None

    def get_briefing_data(self) -> Optional[Dict[str, Any]]:
        if not self.briefing_data_json:
            return None
        try:
            return json.loads(self.briefing_data_json)
        except Exception:
            return None

    def set_integrations(self, data: Optional[list]) -> None:
        if data is not None:
            self.integrations_json = json.dumps(data, ensure_ascii=False)
        else:
            self.integrations_json = None

    def get_integrations(self) -> list:
        if not self.integrations_json:
            return []
        try:
            return json.loads(self.integrations_json)
        except Exception:
            return []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "user_id": self.user_id,
            "status": self.status,
            "stage": self.stage,
            "discovered_count": self.discovered_count,
            "synced_count": self.synced_count,
            "analyzed_count": self.analyzed_count,
            "briefing_status": self.briefing_status,
            "action_count": self.action_count,
            "error_category": self.error_category,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "briefing": self.get_briefing_data(),
            "connected_integrations": self.get_integrations(),
            "has_connected_sources": len(self.get_integrations()) > 0,
        }

    def __repr__(self) -> str:
        return f"<AIRun(run_id='{self.run_id}', user_id='{self.user_id}', status='{self.status}')>"
