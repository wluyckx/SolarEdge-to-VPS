"""
POST /v1/ingest endpoint for batch ingestion of Sungrow telemetry samples.

Accepts a JSON payload with a list of samples, validates device_id ownership,
enforces batch size and request body limits, inserts with idempotent conflict
handling, and returns the count of actually inserted rows.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-010)

TODO:
- None
"""

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.services.ingestion import ingest_samples

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["ingest"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SampleIn(BaseModel):
    """Single telemetry sample from a Sungrow inverter."""

    device_id: str
    ts: datetime
    pv_power_w: float
    pv_daily_kwh: float | None = None
    battery_power_w: float
    battery_soc_pct: float
    battery_temp_c: float | None = None
    load_power_w: float
    export_power_w: float
    sample_count: int = 1


class IngestPayload(BaseModel):
    """Batch payload for the ingest endpoint."""

    samples: list[SampleIn]


class IngestResponse(BaseModel):
    """Response from the ingest endpoint."""

    inserted: int


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


async def _get_device_id(request: Request) -> str:
    """Extract authenticated device_id via BearerAuth on app.state.

    This thin wrapper exists so that FastAPI's Depends() mechanism
    can call the BearerAuth.verify method stored on app.state.auth.

    Args:
        request: The incoming FastAPI request.

    Returns:
        str: The authenticated device_id.
    """
    return await request.app.state.auth.verify(request)


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    request: Request,
    device_id: Annotated[str, Depends(_get_device_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> IngestResponse:
    """Ingest a batch of Sungrow telemetry samples.

    Validates that all sample device_ids match the authenticated device,
    inserts with ON CONFLICT DO NOTHING for idempotency, and invalidates
    the Redis realtime cache on success.

    Args:
        request: The incoming FastAPI request.
        device_id: Authenticated device_id from bearer token.
        db: Async database session.

    Returns:
        IngestResponse: Count of actually inserted rows.

    Raises:
        HTTPException: 413 if body exceeds MAX_REQUEST_BYTES or batch
            exceeds MAX_SAMPLES_PER_REQUEST.
        HTTPException: 403 if any sample device_id does not match.
    """
    config = request.app.state.config

    # AC9: Check request body size — pre-check Content-Length before buffering
    max_request_bytes = int(config.get("MAX_REQUEST_BYTES", "1048576"))
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            content_length_int = int(content_length)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid Content-Length header.",
            ) from None
        if content_length_int > max_request_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Request body exceeds limit of {max_request_bytes} bytes.",
            )

    body = await request.body()
    if len(body) > max_request_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Request body exceeds limit of {max_request_bytes} bytes.",
        )

    # Parse payload — convert Pydantic ValidationError to 422
    try:
        payload = IngestPayload.model_validate_json(body)
    except ValidationError as exc:
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
        )

    # AC6: Empty batch fast path
    if not payload.samples:
        return IngestResponse(inserted=0)

    # AC8: Check batch size
    max_samples = int(config.get("MAX_SAMPLES_PER_REQUEST", "1000"))
    if len(payload.samples) > max_samples:
        raise HTTPException(
            status_code=413,
            detail=f"Batch size {len(payload.samples)} exceeds limit of "
            f"{max_samples}. Split into smaller batches.",
        )

    # AC2: Validate all sample device_ids match authenticated device
    for sample in payload.samples:
        if sample.device_id != device_id:
            raise HTTPException(
                status_code=403,
                detail=f"Sample device_id '{sample.device_id}' does not match "
                f"authenticated device_id '{device_id}'.",
            )

    # Convert to dicts for bulk insert
    sample_dicts = [sample.model_dump() for sample in payload.samples]

    # AC3/AC4: Insert with ON CONFLICT DO NOTHING
    inserted = await ingest_samples(db, device_id, sample_dicts)

    return IngestResponse(inserted=inserted)
