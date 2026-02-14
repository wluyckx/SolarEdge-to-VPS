"""
GET /v1/series endpoint for historical time-bucketed rollup data.

Returns aggregated PV, battery, load, and export metrics at different time
resolutions (hourly, daily, monthly) depending on the requested frame.
Queries TimescaleDB continuous aggregate views via the aggregation service.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-012)

TODO:
- None
"""

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.services.aggregation import FRAME_CONFIG, query_series

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["series"])

# ---------------------------------------------------------------------------
# Valid frame values for documentation and validation
# ---------------------------------------------------------------------------

VALID_FRAMES = frozenset(FRAME_CONFIG.keys())


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class BucketOut(BaseModel):
    """Single time-bucketed aggregation result.

    Attributes:
        bucket: Start timestamp of the time bucket (UTC).
        avg_pv_power_w: Average PV production power in watts.
        max_pv_power_w: Maximum PV production power in watts.
        avg_battery_power_w: Average battery power in watts.
        avg_battery_soc_pct: Average battery state of charge in percent.
        avg_load_power_w: Average household load power in watts.
        avg_export_power_w: Average grid export power in watts.
        sample_count: Number of raw samples in the bucket.
    """

    bucket: datetime
    avg_pv_power_w: float
    max_pv_power_w: float
    avg_battery_power_w: float
    avg_battery_soc_pct: float
    avg_load_power_w: float
    avg_export_power_w: float
    sample_count: int


class SeriesResponse(BaseModel):
    """Response model for the series endpoint.

    Attributes:
        device_id: Identifier of the queried device.
        frame: Time frame resolution used for the query.
        series: List of time-bucketed aggregation results.
    """

    device_id: str
    frame: str
    series: list[BucketOut]


# ---------------------------------------------------------------------------
# Auth dependency
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
# Route
# ---------------------------------------------------------------------------


@router.get("/series", response_model=SeriesResponse)
async def get_series(
    request: Request,
    auth_device_id: Annotated[str, Depends(_get_device_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    device_id: Annotated[str, Query(description="Device identifier to query.")],
    frame: Annotated[
        str,
        Query(description="Time frame: day, month, year, or all."),
    ],
) -> SeriesResponse:
    """Return time-bucketed historical rollup data for a device.

    Queries the appropriate continuous aggregate view based on the requested
    frame and returns aggregated metrics ordered by bucket timestamp.

    Args:
        request: The incoming FastAPI request.
        auth_device_id: Authenticated device_id from bearer token.
        db: Async database session.
        device_id: Device identifier from query parameter.
        frame: Time frame resolution (day, month, year, all).

    Returns:
        SeriesResponse: Device ID, frame, and list of bucketed metrics.

    Raises:
        HTTPException: 403 if device_id does not match authenticated device.
        HTTPException: 422 if frame is not a valid value.
    """
    # AC7: Validate frame parameter
    if frame not in VALID_FRAMES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid frame '{frame}'. Must be one of: {sorted(VALID_FRAMES)}.",
        )

    # AC6: Validate device_id matches authenticated device
    if device_id != auth_device_id:
        raise HTTPException(
            status_code=403,
            detail="Device ID does not match authenticated device.",
        )

    # Query the aggregation service
    rows = await query_series(db, device_id, frame)

    logger.debug(
        "Series query: device_id=%s frame=%s rows=%d",
        device_id,
        frame,
        len(rows),
    )

    return SeriesResponse(
        device_id=device_id,
        frame=frame,
        series=[BucketOut(**row) for row in rows],
    )
