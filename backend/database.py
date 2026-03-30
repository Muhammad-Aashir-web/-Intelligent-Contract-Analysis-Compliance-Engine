from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from config import settings

# Create the SQLAlchemy engine using the database URL from application settings.
# The engine manages the core connection pool to the database.
engine = create_engine(settings.DATABASE_URL)

# Create a configured "SessionLocal" class.
# Each request should use an instance of this session class.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for SQLAlchemy ORM models.
# All model classes should inherit from this Base.
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        # Yield the session so route handlers can use it.
        yield db
    finally:
        # Always close the session to release connection resources.
        db.close()