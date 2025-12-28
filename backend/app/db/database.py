"""
Database Configuration - SQLite with SQLAlchemy.

Uses SQLite for simplicity (no external DB required).
Can migrate to PostgreSQL/Supabase later by changing the URL.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLite database file location
SQLITE_URL = "sqlite:///./jobhunter.db"

# Create engine with SQLite-specific settings
engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},  # Needed for SQLite with FastAPI
    echo=False  # Set to True for SQL debugging
)

# SessionLocal class for database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for ORM models
Base = declarative_base()


def get_db():
    """
    Dependency that provides a database session.
    Use with FastAPI's Depends().
    
    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize the database by creating all tables.
    Call this on application startup.
    """
    from app.db import models  # Import models to register them
    Base.metadata.create_all(bind=engine)
    print("[DB] Database tables created successfully")
