"""
Shared test fixtures for VPS tests.

Provides a configured TestClient for FastAPI integration testing with
mocked database and Redis dependencies. Environment variables are set
to test values so the application can start without real services.

CHANGELOG:
- 2026-02-14: Initial creation with app fixture and mocked DB/Redis (STORY-007)
"""

import sys
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

# Ensure vps/ is on sys.path so ``from src.api.main import app`` resolves
# when pytest is invoked from the repository root (e.g. ``pytest vps/tests/``).
_VPS_ROOT = str(Path(__file__).resolve().parent.parent)
if _VPS_ROOT not in sys.path:
    sys.path.insert(0, _VPS_ROOT)


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required environment variables for testing.

    These are test-only values that allow the FastAPI app to start
    without connecting to real database or Redis services.
    """
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("DEVICE_TOKENS", "test-token-abc:device-001")


@pytest.fixture()
def mock_db_session() -> AsyncMock:
    """Create a mock async database session.

    Returns:
        AsyncMock: A mock that behaves like an SQLAlchemy AsyncSession.
    """
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture()
def mock_redis() -> AsyncMock:
    """Create a mock async Redis client.

    Returns:
        AsyncMock: A mock that behaves like a redis.asyncio.Redis client.
    """
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock()
    client.delete = AsyncMock()
    client.aclose = AsyncMock()
    return client


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    """Create a FastAPI TestClient for integration testing.

    Uses a context manager to ensure the application lifespan events
    (startup/shutdown) are properly triggered. Environment variables
    are already set by the _set_test_env autouse fixture.

    Yields:
        TestClient: Configured test client for the FastAPI app.
    """
    from src.api.main import app

    with TestClient(app) as test_client:
        yield test_client
