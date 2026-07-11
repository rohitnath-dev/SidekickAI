"""
Database configuration for Sidekick AI.

Responsibilities:
- Create SQLAlchemy Engine
- Create Database Session
- Provide Base class for ORM models
- Dependency for FastAPI routes
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session

from config import settings


# ==========================================================
# Database Engine
# ==========================================================

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True
)


# ==========================================================
# Session Factory
# ==========================================================

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


# ==========================================================
# Base Model
# ==========================================================

class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    """
    pass


# ==========================================================
# Database Dependency
# ==========================================================

def get_db():
    """
    Provides a database session.

    Automatically closes the session
    after the request is completed.
    """

    db: Session = SessionLocal()

    try:
        yield db

    finally:
        db.close()
