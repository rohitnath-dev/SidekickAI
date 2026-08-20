"""Memory item repository."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from models.memory_item import MemoryItem


class MemoryRepository:
    """Database operations for long-term memory items."""

    @staticmethod
    def create(
        db: Session,
        user_id: str | int,
        **kwargs,
    ) -> MemoryItem:
        """Create and persist a new memory item."""

        item = MemoryItem(
            user_id=user_id,
            **kwargs,
        )

        db.add(item)
        db.commit()
        db.refresh(item)

        return item

    @staticmethod
    def find_by_content(
        db: Session,
        user_id: str | int,
        content: str,
    ) -> Optional[MemoryItem]:
        """
        Find an existing memory with the same normalized content.

        Matching is intentionally scoped to the current user so that
        memories can never be considered duplicates across users.
        """

        if not isinstance(content, str) or not content.strip():
            return None

        normalized_content = " ".join(
            content.strip().lower().split()
        )

        memories = (
            db.query(MemoryItem)
            .filter(
                MemoryItem.user_id == user_id,
            )
            .all()
        )

        for memory in memories:
            existing_content = memory.content or ""

            normalized_existing = " ".join(
                existing_content.strip().lower().split()
            )

            if normalized_existing == normalized_content:
                return memory

        return None

    @staticmethod
    def list_by_user(
        db: Session,
        user_id: str | int,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> list[MemoryItem]:
        """List memories belonging to a user."""

        query = (
            db.query(MemoryItem)
            .filter(
                MemoryItem.user_id == user_id,
            )
        )

        if category:
            query = query.filter(
                MemoryItem.category == category,
            )

        return (
            query
            .order_by(
                MemoryItem.confidence.desc(),
                MemoryItem.created_at.desc(),
            )
            .limit(limit)
            .all()
        )

    @staticmethod
    def find_relevant(
        db: Session,
        user_id: str | int,
        query: str,
        limit: int = 10,
    ) -> list[MemoryItem]:
        """
        Find memories relevant to the supplied text.

        Uses lightweight keyword matching across memory content and
        associated context. This provides relevant user information
        to downstream agents without requiring a vector database.
        """

        if not isinstance(query, str) or not query.strip():
            return []

        query_terms = {
            word.strip().lower()
            for word in query.split()
            if len(word.strip()) >= 3
        }

        if not query_terms:
            return []

        memories = (
            db.query(MemoryItem)
            .filter(
                MemoryItem.user_id == user_id,
            )
            .order_by(
                MemoryItem.confidence.desc(),
                MemoryItem.created_at.desc(),
            )
            .limit(200)
            .all()
        )

        scored: list[tuple[int, MemoryItem]] = []

        for memory in memories:
            searchable_text = " ".join(
                [
                    memory.content or "",
                    memory.context or "",
                    memory.related_person or "",
                    memory.related_project or "",
                ]
            ).lower()

            score = sum(
                1
                for term in query_terms
                if term in searchable_text
            )

            if score > 0:
                scored.append(
                    (score, memory)
                )

        scored.sort(
            key=lambda item: (
                item[0],
                item[1].confidence,
            ),
            reverse=True,
        )

        return [
            memory
            for _, memory in scored[:limit]
        ]

    @staticmethod
    def search(
        db: Session,
        user_id: str | int,
        query: str,
        limit: int = 20,
    ) -> list[MemoryItem]:
        """Search memories by their content."""

        if not isinstance(query, str) or not query.strip():
            return []

        return (
            db.query(MemoryItem)
            .filter(
                MemoryItem.user_id == user_id,
                MemoryItem.content.ilike(
                    f"%{query.strip()}%"
                ),
            )
            .order_by(
                MemoryItem.confidence.desc(),
                MemoryItem.created_at.desc(),
            )
            .limit(limit)
            .all()
        )

    @staticmethod
    def delete(
        db: Session,
        memory_id: int,
        user_id: str | int,
    ) -> bool:
        """Delete a memory only if it belongs to the specified user."""

        item = (
            db.query(MemoryItem)
            .filter(
                MemoryItem.id == memory_id,
                MemoryItem.user_id == user_id,
            )
            .first()
        )

        if item is None:
            return False

        db.delete(item)
        db.commit()

        return True