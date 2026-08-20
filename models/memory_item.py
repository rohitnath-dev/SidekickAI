"""Memory item model — stores extracted long-term facts per user."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class MemoryItem(Base):
    """A single extracted memory fact for a user."""

    __tablename__ = "memory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    related_project: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retention_value: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium"
    )  # "high" | "medium" | "low"
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    source_message_id: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="memory_items")  # noqa: F821

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "category": self.category,
            "content": self.content,
            "context": self.context,
            "related_person": self.related_person,
            "related_project": self.related_project,
            "retention_value": self.retention_value,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return (
            f"<MemoryItem(id={self.id}, user_id={self.user_id}, "
            f"category='{self.category}')>"
        )
