"""
GET /v1/realtime endpoint for retrieving the most recent SungrowSample.

Returns the latest telemetry sample for a device, using a Redis cache with
configurable TTL to minimise database queries. Requires Bearer token auth
with device_id validation.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-011)

TODO:
- None
"""

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.cache.redis_client import get_redis
from src.db.models import SungrowSample

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["realtime"])


# ---------------------------------------------------------------------------
# Auth dependency (same pattern as ingest.py)
# ---------------------------------------------------------------------------


async def _get_device_id(request: Request) -> str:
    """Extract authenticated device_id via BearerAuth on app.state.

    Args:
        request: The incoming FastAPI request.

    Returns:
        str: The authenticated device_id.
    """
    return await request.app.state.auth.verify(request)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_to_dict(sample: SungrowSample) -> dict:
    """Serialise a SungrowSample ORM instance to a JSON-compatible dict.

    Converts the datetime ``ts`` field to ISO 8601 format for JSON
    serialisation and Redis caching.

    Args:
        sample: The ORM model instance to serialise.

    Returns:
        dict: JSON-serialisable dictionary of all sample fields.
    """
    return {
        "device_id": sample.device_id,
        "ts": sample.ts.isoformat(),
        "pv_power_w": sample.pv_power_w,
        "pv_daily_kwh": sample.pv_daily_kwh,
        "battery_power_w": sample.battery_power_w,
        "battery_soc_pct": sample.battery_soc_pct,
        "battery_temp_c": sample.battery_temp_c,
        "load_power_w": sample.load_power_w,
        "export_power_w": sample.export_power_w,
        "sample_count": sample.sample_count,
    }


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.get("/realtime")
async def realtime(
    request: Request,
    device_id: Annotated[str, Query()],
    auth_device_id: Annotated[str, Depends(_get_device_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Return the most recent SungrowSample for a device.

    Uses a Redis cache (key ``realtime:{device_id}``) with configurable TTL
    to avoid unnecessary database queries. Falls back to a direct DB query
    on cache miss or Redis failure.

    Args:
        request: The incoming FastAPI request.
        device_id: The device to query (query parameter).
        auth_device_id: The authenticated device_id from the bearer token.
        db: Async database session.

    Returns:
        dict: JSON object with all SungrowSample fields.

    Raises:
        HTTPException: 403 if query device_id does not match auth token.
        HTTPException: 404 if no data exists for the device.
    """
    # AC2: Validate device_id ownership
    if device_id != auth_device_id:
        raise HTTPException(
            status_code=403,
            detail="Device ID does not match authenticated device.",
        )

    config = request.app.state.config
    try:
        cache_ttl = int(config.get("CACHE_TTL_S", "5"))
    except ValueError:
        logger.warning("Invalid CACHE_TTL_S value, using default 5s")
        cache_ttl = 5
    cache_key = f"realtime:{device_id}"

    # AC4: Try Redis cache first (best-effort)
    try:
        redis_client = await get_redis()
        try:
            cached = await redis_client.get(cache_key)
            if cached is not None:
                return json.loads(cached)
        finally:
            await redis_client.aclose()
    except Exception:
        logger.warning(
            "Redis read failed for key %s, falling back to DB",
            cache_key,
            exc_info=True,
        )

    # AC3: Query DB for latest sample
    stmt = (
        select(SungrowSample)
        .where(SungrowSample.device_id == device_id)
        .order_by(SungrowSample.ts.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    sample = result.scalar_one_or_none()

    # AC5: 404 if no data
    if sample is None:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for device_id '{device_id}'.",
        )

    # Serialise to dict
    sample_dict = _sample_to_dict(sample)
    sample_json = json.dumps(sample_dict)

    # AC4: Cache result in Redis (best-effort)
    try:
        redis_client = await get_redis()
        try:
            await redis_client.set(cache_key, sample_json, ex=cache_ttl)
        finally:
            await redis_client.aclose()
    except Exception:
        logger.warning(
            "Redis write failed for key %s",
            cache_key,
            exc_info=True,
        )

    return sample_dict
