"""
Notification Service Database — owns its own PostgreSQL database.

Provides both sync engine (for RabbitMQ consumer) and async engine (for HTTP API).
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, Session

from config import settings

_sync_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")

sync_engine = create_engine(_sync_url, pool_pre_ping=True)
async_engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)

SyncSessionLocal = sessionmaker(bind=sync_engine, class_=Session)
AsyncSessionLocal = sessionmaker(
    bind=async_engine, class_=AsyncSession, expire_on_commit=False
)


def init_db():
    """Create tables if they don't exist (called on startup)."""
    from models.notification import Base

    Base.metadata.create_all(sync_engine)


async def get_db():
    """FastAPI dependency for async sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
