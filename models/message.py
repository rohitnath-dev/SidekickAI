from __future__ import annotations  
  
from datetime import datetime  
from enum import Enum  
  
from sqlalchemy import (  
    Boolean,  
    DateTime,  
    Enum as SQLEnum,  
    Integer,  
    String,  
    Text,  
)  
  
from sqlalchemy.orm import Mapped, mapped_column  
  
from database import Base  
  
  
# ==========================================================  
# ENUMS  
# ==========================================================  
  
class MessageSource(str, Enum):  
    """Supported communication platforms."""  
  
    GMAIL = "gmail"  
    SLACK = "slack"  
    DISCORD = "discord"  
    TEAMS = "teams"  
    LINKEDIN = "linkedin"  
    TWITTER = "twitter"  
    OTHER = "other"  
  
  
class MessagePriority(str, Enum):  
    """Priority assigned by AI."""  
  
    LOW = "low"  
    MEDIUM = "medium"  
    HIGH = "high"  
    CRITICAL = "critical"  
  
  
class MessageStatus(str, Enum):  
    """Lifecycle status."""  
  
    UNREAD = "unread"  
    READ = "read"  
    REPLIED = "replied"  
    ARCHIVED = "archived"  
  
  
# ==========================================================  
# DATABASE MODEL  
# ==========================================================  
  
class Message(Base):  
    """  
    Database model representing a normalized message.  
  
    Every communication imported into Sidekick AI is converted  
    into this schema regardless of its source platform.  
    """  
  
    __tablename__ = "messages"  
  
    __table_args__ = (  
        {"sqlite_autoincrement": True},  
    )  
  
    id: Mapped[int] = mapped_column(  
        Integer,  
        primary_key=True,  
        autoincrement=True,  
    )  
  
    message_id: Mapped[str] = mapped_column(  
        String(255),  
        unique=True,  
        nullable=False,  
        index=True,  
    )  
  
    thread_id: Mapped[str | None] = mapped_column(  
        String(255),  
        nullable=True,  
        index=True,  
    )  
  
    source: Mapped[MessageSource] = mapped_column(  
        SQLEnum(MessageSource),  
        nullable=False,  
        default=MessageSource.GMAIL,  
    )  
  
    sender: Mapped[str] = mapped_column(  
        String(255),  
        nullable=False,  
    )  
  
    recipient: Mapped[str | None] = mapped_column(  
        String(255),  
        nullable=True,  
    )  
  
    subject: Mapped[str | None] = mapped_column(  
        String(500),  
        nullable=True,  
    )  
  
    body: Mapped[str] = mapped_column(  
        Text,  
        nullable=False,  
    )  
  
    priority: Mapped[MessagePriority] = mapped_column(  
        SQLEnum(MessagePriority),  
        nullable=False,  
        default=MessagePriority.MEDIUM,  
    )  
  
    status: Mapped[MessageStatus] = mapped_column(  
        SQLEnum(MessageStatus),  
        nullable=False,  
        default=MessageStatus.UNREAD,  
    )  
  
    requires_reply: Mapped[bool] = mapped_column(  
        Boolean,  
        default=False,  
        nullable=False,  
    )  
  
    received_at: Mapped[datetime] = mapped_column(  
        DateTime,  
        nullable=False,  
    )  
  
    created_at: Mapped[datetime] = mapped_column(  
        DateTime,  
        default=datetime.utcnow,  
        nullable=False,  
    )  
  
    updated_at: Mapped[datetime] = mapped_column(  
        DateTime,  
        default=datetime.utcnow,  
        onupdate=datetime.utcnow,  
        nullable=False,  
    )  
  
    summary: Mapped[str | None] = mapped_column(  
        Text,  
        nullable=True,  
    )  
  
    sentiment: Mapped[str | None] = mapped_column(  
        String(50),  
        nullable=True,  
    )  
  
    category: Mapped[str | None] = mapped_column(  
        String(100),  
        nullable=True,  
    )  
  
    action_items: Mapped[str | None] = mapped_column(  
        Text,  
        nullable=True,  
    )  
  
    suggested_reply: Mapped[str | None] = mapped_column(  
        Text,  
        nullable=True,  
    )  
  
    confidence_score: Mapped[int | None] = mapped_column(  
        Integer,  
        nullable=True,  
    )  
  
    is_processed: Mapped[bool] = mapped_column(  
        Boolean,  
        default=False,  
        nullable=False,  
    )  
  
    def __repr__(self) -> str:  
        """  
        Developer-friendly representation of the message.  
        """  
  
        return (  
            f"<Message("  
            f"id={self.id}, "  
            f"source='{self.source.value}', "  
            f"sender='{self.sender}', "  
            f"subject='{self.subject}', "  
            f"priority='{self.priority.value}'"  
            f")>"  
        )  
  
    def mark_as_read(self) -> None:  
        """  
        Mark the message as read.  
        """  
  
        self.status = MessageStatus.READ  
  
    def mark_as_replied(self) -> None:  
        """  
        Mark the message as replied.  
        """  
  
        self.status = MessageStatus.REPLIED  
  
    def mark_as_archived(self) -> None:  
        """  
        Mark the message as archived.  
        """  
  
        self.status = MessageStatus.ARCHIVED  
  
    def update_priority(  
        self,  
        priority: MessagePriority,  
    ) -> None:  
        """  
        Update AI-generated priority.  
        """  
  
        self.priority = priority  
  
    def set_reply_required(  
        self,  
        value: bool,  
    ) -> None:  
        """  
        Update reply requirement.  
        """  
  
        self.requires_reply = value  
  
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
        """  
        Update AI-generated fields without affecting original message data.  
        """  
  
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
  
    def to_summary_context(self) -> str:  
        """  
        Build a context string for the Summary Agent.  
        """  
  
        return (  
            f"Subject: {self.subject}\n"  
            f"From: {self.sender}\n"  
            f"Body:\n{self.body}"  
        )  
  
    def to_priority_context(self) -> str:  
        """  
        Build a context string for the Priority Agent.  
        """  
  
        return (  
            f"Sender: {self.sender}\n"  
            f"Subject: {self.subject}\n"  
            f"Body:\n{self.body}"  
        )  
  
    def to_reply_context(self) -> str:  
        """  
        Build a context string for the Reply Agent.  
        """  
  
        return (  
            f"From: {self.sender}\n"  
            f"Subject: {self.subject}\n"  
            f"Message:\n{self.body}"  
        )  
  
    def to_memory_context(self) -> str:  
        """  
        Build a context string for the Memory Agent.  
        """  
  
        return (  
            f"Sender: {self.sender}\n"  
            f"Subject: {self.subject}\n"  
            f"Body:\n{self.body}"  
        )  
  
    def to_dict(self) -> dict:  
        """  
        Convert the model into a JSON-serializable dictionary.  
        """  
  
        return {  
            "id": self.id,  
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
            "received_at": (  
                self.received_at.isoformat()  
                if self.received_at  
                else None  
            ),  
            "created_at": (  
                self.created_at.isoformat()  
                if self.created_at  
                else None  
            ),  
            "updated_at": (  
                self.updated_at.isoformat()  
                if self.updated_at  
                else None  
            ),  
        }  
  
    @property  
    def is_high_priority(self) -> bool:  
        """  
        Returns True if message priority is High or Critical.  
        """  
  
        return self.priority in (  
            MessagePriority.HIGH,  
            MessagePriority.CRITICAL,  
        )  
  
    @property  
    def is_completed(self) -> bool:  
        """  
        Returns whether the message has already been processed by AI.  
        """  
  
        return self.is_processed  