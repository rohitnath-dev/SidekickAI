"""Message repository."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from models.message import Message, MessageStatus, MessageSource


class MessageRepository:

    @staticmethod
    def create(db: Session, **kwargs) -> Message:
        message = Message(**kwargs)
        db.add(message)
        db.commit()
        db.refresh(message)
        return message

    @staticmethod
    def get_by_id(db: Session, message_id: int, user_id: str | int) -> Optional[Message]:
        return (
            db.query(Message)
            .filter(Message.id == message_id, Message.user_id == str(user_id))
            .first()
        )

    @staticmethod
    def get_by_external_id(
        db: Session, external_message_id: str, user_id: str | int
    ) -> Optional[Message]:
        return (
            db.query(Message)
            .filter(
                Message.message_id == external_message_id,
                Message.user_id == str(user_id),
            )
            .first()
        )

    @staticmethod
    def list_by_user(
        db: Session,
        user_id: str | int,
        limit: int = 20,
        offset: int = 0,
        unread_only: bool = False,
        source: Optional[str] = None,
        high_priority_only: bool = False,
        category: Optional[str] = None,
    ) -> list[Message]:
        q = db.query(Message).filter(Message.user_id == str(user_id))

        if unread_only:
            q = q.filter(Message.status == MessageStatus.UNREAD)
        if source:
            try:
                q = q.filter(Message.source == MessageSource(source))
            except ValueError:
                pass
        if category and category.lower() not in ("all", "all gmail"):
            q = q.filter(Message.category == category.lower())

        if high_priority_only:
            from models.message import MessagePriority
            q = q.filter(Message.priority.in_([MessagePriority.HIGH, MessagePriority.CRITICAL]))
        return (
            q.order_by(Message.received_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    @staticmethod
    def update(db: Session, message: Message, **fields) -> Message:
        for key, value in fields.items():
            if hasattr(message, key):
                setattr(message, key, value)
        db.commit()
        db.refresh(message)
        return message

    @staticmethod
    def delete(db: Session, message: Message) -> None:
        db.delete(message)
        db.commit()

    @staticmethod
    def count_by_user(db: Session, user_id: str | int) -> int:
        return db.query(Message).filter(Message.user_id == user_id).count()
