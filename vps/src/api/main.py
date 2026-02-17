"""
FastAPI application entry point for the Sungrow-to-VPS API.

Provides the root health endpoint and serves as the application factory.
Environment variables are loaded at startup for validation. DEVICE_TOKENS
are parsed into a BearerAuth instance stored on app.state for route handlers.

CHANGELOG:
- 2026-02-14: Register health router (STORY-015)
- 2026-02-14: Register series router (STORY-012)
- 2026-02-14: Register realtime router (STORY-011)
- 2026-02-14: Register ingest router (STORY-010)
- 2026-02-14: Wire DEVICE_TOKENS parsing into startup (STORY-009 AC1 fix)
- 2026-02-14: Initial creation (STORY-007)
"""

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.health import router as health_router
from src.api.ingest import router as ingest_router
from src.api.realtime import router as realtime_router
from src.api.series import router as series_router
from src.auth.bearer import BearerAuth, parse_device_tokens

logger = logging.getLogger(__name__)


def _load_env_config() -> dict[str, str]:
    """Load and validate required environment variables at startup.

    Returns:
        dict: Mapping of config key to value.

    Raises:
        RuntimeError: If a required environment variable is missing.
    """
    required = ["DATABASE_URL", "REDIS_URL", "DEVICE_TOKENS"]
    config: dict[str, str] = {}
    missing: list[str] = []

    for key in required:
        value = os.environ.get(key)
        if not value:
            missing.append(key)
        else:
            config[key] = value

    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    # Optional with defaults (from Architecture.md)
    config["MAX_SAMPLES_PER_REQUEST"] = os.environ.get(
        "MAX_SAMPLES_PER_REQUEST", "1000"
    )
    config["MAX_REQUEST_BYTES"] = os.environ.get("MAX_REQUEST_BYTES", "1048576")
    config["CACHE_TTL_S"] = os.environ.get("CACHE_TTL_S", "5")

    return config


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup validation and shutdown logging.

    Startup:
        - Validates required environment variables.
        - Logs that the API is ready.

    Shutdown:
        - Logs that the API is shutting down.
    """
    config = _load_env_config()
    app.state.config = config

    # AC1: Parse DEVICE_TOKENS into token->device_id map and build BearerAuth
    token_map = parse_device_tokens(config["DEVICE_TOKENS"])
    if not token_map:
        raise RuntimeError(
            "DEVICE_TOKENS parsed but contains no valid token:device_id entries"
        )
    app.state.auth = BearerAuth(token_map)
    logger.info("Parsed %d device token(s) from DEVICE_TOKENS", len(token_map))

    logger.info("Environment validated, Sungrow VPS API ready")
    yield
    logger.info("Sungrow VPS API shutting down")


app = FastAPI(
    title="Sungrow-to-VPS API",
    description="Solar telemetry API for Sungrow inverter data.",
    version="0.1.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dashboard.energy.wimluyckx.dev"],
    allow_methods=["GET"],
    allow_headers=["Authorization"],
)

app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(realtime_router)
app.include_router(series_router)


@app.get("/")
async def root() -> dict:
    """Root health check endpoint.

    Returns:
        dict: JSON object with application status.
    """
    return {"status": "ok"}
