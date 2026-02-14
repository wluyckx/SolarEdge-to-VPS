"""
Aggregation service for time-bucketed historical series data.

Queries TimescaleDB continuous aggregate views (sungrow_hourly, sungrow_daily,
sungrow_monthly) to return historical rollups at different resolutions. The
FRAME_CONFIG dict maps frame names to their source view and time filter.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-012)

TODO:
- None
"""

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FrameConfig:
    """Configuration for a time-series frame resolution.

    Attributes:
        source_view: Name of the continuous aggregate view to query.
        bucket_interval: Time bucket interval for fallback queries.
        time_filter: SQL WHERE clause for time range filtering, or None for all-time.
    """

    source_view: str
    bucket_interval: str
    time_filter: str | None


FRAME_CONFIG: dict[str, FrameConfig] = {
    "day": FrameConfig(
        source_view="sungrow_hourly",
        bucket_interval="1 hour",
        time_filter="bucket >= date_trunc('day', now())",
    ),
    "month": FrameConfig(
        source_view="sungrow_daily",
        bucket_interval="1 day",
        time_filter="bucket >= date_trunc('month', now())",
    ),
    "year": FrameConfig(
        source_view="sungrow_monthly",
        bucket_interval="1 month",
        time_filter="bucket >= date_trunc('year', now())",
    ),
    "all": FrameConfig(
        source_view="sungrow_monthly",
        bucket_interval="1 month",
        time_filter=None,
    ),
}


async def query_series(
    db: AsyncSession,
    device_id: str,
    frame: str,
) -> list[dict]:
    """Query historical time-bucketed series data for a device.

    Selects aggregated metrics from the appropriate continuous aggregate view
    based on the requested frame. Results are ordered by bucket timestamp ASC.

    Args:
        db: Async database session.
        device_id: Identifier of the device to query.
        frame: Time frame resolution (day, month, year, all).

    Returns:
        list[dict]: List of bucket dicts with aggregated metrics.

    Raises:
        KeyError: If frame is not a valid FRAME_CONFIG key.
    """
    config = FRAME_CONFIG[frame]

    sql = (
        f"SELECT bucket, avg_pv_power_w, max_pv_power_w, avg_battery_power_w, "
        f"avg_battery_soc_pct, avg_load_power_w, avg_export_power_w, sample_count "
        f"FROM {config.source_view} "
        f"WHERE device_id = :device_id"
    )

    if config.time_filter:
        sql += f" AND {config.time_filter}"

    sql += " ORDER BY bucket ASC"

    logger.debug(
        "Querying series: frame=%s view=%s device_id=%s",
        frame,
        config.source_view,
        device_id,
    )

    result = await db.execute(text(sql), {"device_id": device_id})
    rows = result.mappings().all()
    return [dict(row) for row in rows]
