"""
Ingestion service for batch-inserting Sungrow telemetry samples.

Handles idempotent insertion via ON CONFLICT (device_id, ts) DO NOTHING,
returning the count of actually inserted rows. Invalidates the Redis
realtime cache for the device on successful insertion.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-010)

TODO:
- None
"""

import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.cache.redis_client import invalidate_device_cache
from src.db.models import SungrowSample

logger = logging.getLogger(__name__)


async def ingest_samples(
    db: AsyncSession,
    device_id: str,
    samples: list[dict],
) -> int:
    """Insert a batch of telemetry samples with idempotent conflict handling.

    Uses PostgreSQL INSERT ... ON CONFLICT (device_id, ts) DO NOTHING so that
    duplicate samples (same device + timestamp) are silently skipped. Returns
    the number of rows actually inserted (excluding duplicates).

    After a successful insertion (inserted > 0), the Redis realtime cache key
    for the device is invalidated.

    Args:
        db: Async SQLAlchemy session.
        device_id: The authenticated device identifier.
        samples: List of sample dicts ready for insertion.

    Returns:
        int: Number of rows actually inserted.
    """
    if not samples:
        return 0

    stmt = (
        pg_insert(SungrowSample)
        .values(samples)
        .on_conflict_do_nothing(index_elements=["device_id", "ts"])
    )
    result = await db.execute(stmt)
    await db.commit()

    inserted = result.rowcount
    logger.info(
        "Ingested %d/%d samples for device %s",
        inserted,
        len(samples),
        device_id,
    )

    if inserted > 0:
        await invalidate_device_cache(device_id)

    return inserted
