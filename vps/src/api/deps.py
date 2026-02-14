"""
FastAPI dependency injection providers.

Provides database sessions, Redis clients, and authentication dependencies
for use with FastAPI's Depends() mechanism.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-007)
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_async_session

# Type alias for injecting an async DB session via FastAPI Depends().
# Usage in route handlers:
#   async def my_route(db: DbSession):
#       result = await db.execute(...)
DbSession = Annotated[AsyncSession, Depends(get_async_session)]


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session.

    Convenience wrapper around get_async_session for cases
    where a plain dependency function is preferred over the Annotated alias.

    Yields:
        AsyncSession: An async SQLAlchemy session.
    """
    async for session in get_async_session():
        yield session
