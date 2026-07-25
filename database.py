"""
Sidekick AI — Database engine, session factory and dependency.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from config import settings


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

connect_args: dict = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    connect_args=connect_args,
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Common base for all SQLAlchemy models."""
    pass


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

def get_db():
    """FastAPI dependency that provides and closes a database session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
