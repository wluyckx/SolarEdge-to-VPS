"""
Async database engine and session factory.

Uses SQLAlchemy 2.x async engine with asyncpg driver for PostgreSQL.
Provides module-level engine and session factory singletons, plus an
async generator for FastAPI dependency injection.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-007)
"""

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Module-level singletons, initialized lazily via init_engine().
async_engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_database_url() -> str:
    """Read DATABASE_URL from environment.

    Returns:
        str: The database connection URL.

    Raises:
        RuntimeError: If DATABASE_URL is not set.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is required")
    return url


def create_engine() -> AsyncEngine:
    """Create an async SQLAlchemy engine from configuration.

    Returns:
        AsyncEngine: Configured async engine for PostgreSQL via asyncpg.
    """
    return create_async_engine(_get_database_url(), echo=False)


def create_session_factory(
    engine: AsyncEngine | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory.

    Args:
        engine: Optional async engine. If not provided, creates one from config.

    Returns:
        async_sessionmaker: Factory for creating AsyncSession instances.
    """
    if engine is None:
        engine = create_engine()
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def init_engine() -> None:
    """Initialize the module-level async engine and session factory.

    Call this at application startup (e.g., in a FastAPI lifespan event).
    Safe to call multiple times; subsequent calls are no-ops.
    """
    global async_engine, async_session_factory  # noqa: PLW0603
    if async_engine is None:
        async_engine = create_engine()
        async_session_factory = create_session_factory(async_engine)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for FastAPI dependency injection.

    Initializes the engine on first call if not already done.
    The session is automatically closed after the request completes.

    Yields:
        AsyncSession: An async SQLAlchemy session.
    """
    init_engine()
    assert async_session_factory is not None, "Session factory not initialized"
    async with async_session_factory() as session:
        yield session
