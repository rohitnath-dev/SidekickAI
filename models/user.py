"""User model."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


import uuid

class User(Base):
    """Registered Sidekick user."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))

    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    messages: Mapped[list["Message"]] = relationship(  # noqa: F821
        "Message", back_populates="user", cascade="all, delete-orphan"
    )
    oauth_tokens: Mapped[list["OAuthToken"]] = relationship(  # noqa: F821
        "OAuthToken", back_populates="user", cascade="all, delete-orphan"
    )
    memory_items: Mapped[list["MemoryItem"]] = relationship(  # noqa: F821
        "MemoryItem", back_populates="user", cascade="all, delete-orphan"
    )
    ai_config: Mapped[Optional["UserAIConfig"]] = relationship(  # noqa: F821
        "UserAIConfig", back_populates="user", cascade="all, delete-orphan", uselist=False
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"
