"""Message model — unified across all platforms."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class MessageSource(str, Enum):
    GMAIL = "gmail"
    WHATSAPP = "whatsapp"
    TWITTER = "twitter"
    SLACK = "slack"
    CALENDAR = "calendar"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    OTHER = "other"


class MessagePriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MessageStatus(str, Enum):
    UNREAD = "unread"
    READ = "read"
    REPLIED = "replied"
    ARCHIVED = "archived"


class Message(Base):
    """Normalised message from any connected platform."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Platform identifiers
    message_id: Mapped[str] = mapped_column(
        String(512), nullable=False, index=True
    )
    thread_id: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)

    source: Mapped[MessageSource] = mapped_column(
        SQLEnum(MessageSource), nullable=False, default=MessageSource.GMAIL
    )

    # Content
    sender: Mapped[str] = mapped_column(String(512), nullable=False)
    recipient: Mapped[str | None] = mapped_column(String(512), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # AI-generated fields
    priority: Mapped[MessagePriority] = mapped_column(
        SQLEnum(MessagePriority), nullable=False, default=MessagePriority.MEDIUM
    )
    status: Mapped[MessageStatus] = mapped_column(
        SQLEnum(MessageStatus), nullable=False, default=MessageStatus.UNREAD
    )
    requires_reply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action_items: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="messages")  # noqa: F821

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def mark_as_read(self) -> None:
        self.status = MessageStatus.READ

    def mark_as_replied(self) -> None:
        self.status = MessageStatus.REPLIED

    def mark_as_archived(self) -> None:
        self.status = MessageStatus.ARCHIVED

    def update_from_ai(
        self,
        *,
        summary: str | None = None,
        priority: MessagePriority | None = None,
        sentiment: str | None = None,
        category: str | None = None,
        action_items: str | None = None,
        suggested_reply: str | None = None,
        confidence_score: int | None = None,
        requires_reply: bool | None = None,
    ) -> None:
        if summary is not None:
            self.summary = summary
        if priority is not None:
            self.priority = priority
        if sentiment is not None:
            self.sentiment = sentiment
        if category is not None:
            self.category = category
        if action_items is not None:
            self.action_items = action_items
        if suggested_reply is not None:
            self.suggested_reply = suggested_reply
        if confidence_score is not None:
            self.confidence_score = confidence_score
        if requires_reply is not None:
            self.requires_reply = requires_reply
        self.is_processed = True

    def to_context_string(self) -> str:
        return (
            f"From: {self.sender}\n"
            f"Subject: {self.subject or '(no subject)'}\n"
            f"Body:\n{self.body}"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "message_id": self.message_id,
            "thread_id": self.thread_id,
            "source": self.source.value,
            "sender": self.sender,
            "recipient": self.recipient,
            "subject": self.subject,
            "body": self.body,
            "priority": self.priority.value,
            "status": self.status.value,
            "requires_reply": self.requires_reply,
            "summary": self.summary,
            "sentiment": self.sentiment,
            "category": self.category,
            "action_items": self.action_items,
            "suggested_reply": self.suggested_reply,
            "confidence_score": self.confidence_score,
            "is_processed": self.is_processed,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @property
    def is_high_priority(self) -> bool:
        return self.priority in (MessagePriority.HIGH, MessagePriority.CRITICAL)

    def __repr__(self) -> str:
        return (
            f"<Message(id={self.id}, source='{self.source.value}', "
            f"sender='{self.sender}', subject='{self.subject}')>"
        )
