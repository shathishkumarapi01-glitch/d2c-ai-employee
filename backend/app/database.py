"""
Async SQLAlchemy engine and session management.
Uses SQLite (aiosqlite) for local dev — no external DB needed.
"""

from __future__ import annotations

from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.config import settings

Base = declarative_base()

# Ensure the data directory exists for SQLite
db_url = settings.database_url
if "sqlite" in db_url:
    db_path = db_url.split("///")[-1]
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    settings.database_url,
    echo=False,
    **(
        {"connect_args": {"check_same_thread": False, "timeout": 30}}
        if "sqlite" in settings.database_url
        else {"pool_size": 20, "max_overflow": 10, "pool_pre_ping": True}
    ),
)

# Enable WAL mode for SQLite — fixes "database is locked" errors
if "sqlite" in settings.database_url:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Import models and create database tables."""
    from app import models as _models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a scoped async session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
