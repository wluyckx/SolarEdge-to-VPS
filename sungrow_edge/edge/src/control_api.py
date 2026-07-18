"""
HTTP API for the battery control module.

Small FastAPI app exposing the SungrowController to LAN/Tailscale clients
(HA automations, the planner, Telegram glue). Bearer-token auth on every
endpoint; validation failures surface as 422 without touching Modbus.

Endpoints:
    GET  /                -- built-in operator page (public shell, no data)
    GET  /control/status  -- controller state, active command, limits
    POST /control/force   -- charge / discharge / hold (TTL mandatory)
    POST /control/auto    -- revert to inverter self-consumption
    GET  /control/audit   -- tail of the JSONL audit trail

CHANGELOG:
- 2026-07-18: Serve the built-in operator page at / (public static shell)
- 2026-07-18: Initial creation -- battery-control Phase 1 (AC6)

TODO:
- None
"""

from __future__ import annotations

import asyncio
import logging
import secrets

from edge.src.control import CommandRequest, ControlError, SungrowController
from edge.src.control_ui import PAGE_HTML
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AutoRequest(BaseModel):
    """Body for POST /control/auto."""

    issuer: str = Field(min_length=1)


def build_app(controller: SungrowController, *, token: str) -> FastAPI:
    """Build the control API app bound to one controller instance.

    Args:
        controller: The single-writer battery controller.
        token: Bearer token required on every request (must be non-empty).
    """
    if not token:
        raise ValueError("control API token must be non-empty")

    app = FastAPI(title="Sungrow Battery Control", docs_url=None, redoc_url=None)

    async def require_auth(request: Request) -> None:
        header = request.headers.get("Authorization", "")
        expected = f"Bearer {token}"
        if not secrets.compare_digest(header, expected):
            raise HTTPException(status_code=401, detail="invalid or missing token")

    @app.get("/", include_in_schema=False)
    async def index() -> HTMLResponse:
        # Public static shell: contains no data or secrets; every data call
        # the page makes goes through the bearer-token endpoints below.
        return HTMLResponse(PAGE_HTML)

    @app.get("/control/status", dependencies=[Depends(require_auth)])
    async def get_status() -> dict:
        return controller.status()

    @app.post("/control/force", dependencies=[Depends(require_auth)])
    async def post_force(req: CommandRequest) -> dict:
        if req.mode == "auto":
            raise HTTPException(
                status_code=422, detail="use POST /control/auto for mode=auto"
            )
        try:
            return await controller.apply(req)
        except ControlError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/control/auto", dependencies=[Depends(require_auth)])
    async def post_auto(req: AutoRequest) -> dict:
        try:
            return await controller.apply(
                CommandRequest(mode="auto", issuer=req.issuer)
            )
        except ControlError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/control/audit", dependencies=[Depends(require_auth)])
    async def get_audit(limit: int = Query(default=50, ge=1, le=1000)) -> dict:
        return {"events": controller.audit_tail(limit)}

    return app


async def serve_api(
    app: FastAPI,
    *,
    port: int,
    shutdown_event: asyncio.Event,
    host: str = "0.0.0.0",
) -> None:
    """Serve the app with uvicorn until shutdown_event is set."""
    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)

    async def _watch_shutdown() -> None:
        await shutdown_event.wait()
        server.should_exit = True

    watcher = asyncio.get_running_loop().create_task(_watch_shutdown())
    logger.info("Control API listening on %s:%d", host, port)
    try:
        await server.serve()
    finally:
        watcher.cancel()
