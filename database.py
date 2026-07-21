from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session

from config import settings

# Create the main engine that connects the application to the database.
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True
)


# Create a factory that creates a new database session whenever it is needed. A session is a temporary connection used to interact with the database.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

# Create a common base class that all database models will inherit from.
class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    """
    pass


# Create and provide a database session for each request, then automatically close it when the request is finished.

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