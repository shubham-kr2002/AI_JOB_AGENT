"""
Project JobHunter V3 - Async Database Configuration
PostgreSQL with async SQLAlchemy for V3 architecture.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.models.base import Base

settings = get_settings()

# ============================================================================
# Async Engine (PostgreSQL)
# ============================================================================
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    poolclass=NullPool,  # Recommended for async
    future=True,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ============================================================================
# Dependency Injection
# ============================================================================
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async database session dependency for FastAPI.
    
    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_async_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for async database sessions.
    
    Usage:
        async with get_async_session() as session:
            result = await session.execute(select(User))
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ============================================================================
# Database Initialization
# ============================================================================
async def init_async_db() -> None:
    """
    Initialize database tables asynchronously.
    
    Creates all tables defined in our models.
    Use this for development/testing. Use Alembic for production migrations.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[DB] Async PostgreSQL tables created successfully")


async def drop_async_db() -> None:
    """
    Drop all database tables.
    
    WARNING: This will delete all data! Only use in development/testing.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("[DB] All tables dropped")
