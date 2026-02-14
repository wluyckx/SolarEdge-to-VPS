"""
Redis client for cache operations.

Provides helper functions for creating Redis connections and invalidating
device-specific cache entries. Cache invalidation is best-effort: connection
failures are logged but do not propagate exceptions.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-007)
"""

import logging
import os

import redis.asyncio as redis

logger = logging.getLogger(__name__)


def _get_redis_url() -> str:
    """Read REDIS_URL from environment.

    Returns:
        str: The Redis connection URL.

    Raises:
        RuntimeError: If REDIS_URL is not set.
    """
    url = os.environ.get("REDIS_URL")
    if not url:
        raise RuntimeError("REDIS_URL environment variable is required")
    return url


async def get_redis() -> redis.Redis:
    """Create and return an async Redis client from environment settings.

    Reads REDIS_URL from the environment and returns a configured
    redis.asyncio.Redis instance.

    Returns:
        redis.Redis: Async Redis client.
    """
    return redis.from_url(_get_redis_url())


async def invalidate_device_cache(device_id: str) -> None:
    """Delete the realtime cache key for a device.

    Best-effort operation: if Redis is unavailable or the delete fails,
    the error is logged but not raised. This ensures that ingest operations
    are not blocked by cache infrastructure issues.

    Args:
        device_id: The device identifier whose cache should be cleared.
    """
    try:
        client = await get_redis()
        try:
            await client.delete(f"realtime:{device_id}")
        finally:
            await client.aclose()
    except Exception:
        logger.warning(
            "Failed to invalidate cache for device %s",
            device_id,
            exc_info=True,
        )
