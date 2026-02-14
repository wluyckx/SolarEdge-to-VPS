"""
Health check endpoint for the VPS API.

Provides a simple GET /health endpoint that returns {"status": "ok"} with
HTTP 200. No authentication is required -- this is intended for Docker
HEALTHCHECK and internal monitoring only.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-015)

TODO:
- None
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Return a simple health status.

    Returns:
        dict: ``{"status": "ok"}`` indicating the service is alive.
    """
    return {"status": "ok"}
