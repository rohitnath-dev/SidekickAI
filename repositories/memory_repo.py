"""Memory item repository."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from models.memory_item import MemoryItem


class MemoryRepository:

    @staticmethod
    def create(db: Session, user_id: int, **kwargs) -> MemoryItem:
        item = MemoryItem(user_id=user_id, **kwargs)
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def list_by_user(
        db: Session,
        user_id: int,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> list[MemoryItem]:
        q = db.query(MemoryItem).filter(MemoryItem.user_id == user_id)
        if category:
            q = q.filter(MemoryItem.category == category)
        return q.order_by(MemoryItem.confidence.desc()).limit(limit).all()

    @staticmethod
    def delete(db: Session, memory_id: int, user_id: int) -> bool:
        item = (
            db.query(MemoryItem)
            .filter(MemoryItem.id == memory_id, MemoryItem.user_id == user_id)
            .first()
        )
        if item is None:
            return False
        db.delete(item)
        db.commit()
        return True

    @staticmethod
    def search(
        db: Session, user_id: int, query: str, limit: int = 20
    ) -> list[MemoryItem]:
        return (
            db.query(MemoryItem)
            .filter(
                MemoryItem.user_id == user_id,
                MemoryItem.content.ilike(f"%{query}%"),
            )
            .order_by(MemoryItem.confidence.desc())
            .limit(limit)
            .all()
        )
