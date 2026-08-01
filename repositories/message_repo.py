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
    def get_by_id(db: Session, message_id: int, user_id: int) -> Optional[Message]:
        msg = db.query(Message).filter(Message.id == message_id).first()
        if msg and (msg.source == MessageSource.WHATSAPP or msg.user_id == user_id):
            return msg
        return None

    @staticmethod
    def get_by_external_id(
        db: Session, external_message_id: str, user_id: int
    ) -> Optional[Message]:
        msg = db.query(Message).filter(Message.message_id == external_message_id).first()
        if msg and (msg.source == MessageSource.WHATSAPP or msg.user_id == user_id):
            return msg
        return None

    @staticmethod
    def list_by_user(
        db: Session,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
        unread_only: bool = False,
        source: Optional[str] = None,
        high_priority_only: bool = False,
    ) -> list[Message]:
        from sqlalchemy import or_
        if source == "whatsapp":
            q = db.query(Message)
        elif not source or source == "all":
            q = db.query(Message).filter(or_(Message.user_id == user_id, Message.source == MessageSource.WHATSAPP))
        else:
            q = db.query(Message).filter(Message.user_id == user_id)

        if unread_only:
            q = q.filter(Message.status == MessageStatus.UNREAD)
        if source:
            try:
                q = q.filter(Message.source == MessageSource(source))
            except ValueError:
                pass
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
    def count_by_user(db: Session, user_id: int) -> int:
        return db.query(Message).filter(Message.user_id == user_id).count()
