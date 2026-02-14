"""
FastAPI application entry point for the Sungrow-to-VPS API.

Provides the root health endpoint and serves as the application factory.
Environment variables are loaded at startup for validation.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-007)
"""

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

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
    logger.info("Environment validated, Sungrow VPS API ready")
    yield
    logger.info("Sungrow VPS API shutting down")


app = FastAPI(
    title="Sungrow-to-VPS API",
    description="Solar telemetry API for Sungrow inverter data.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root() -> dict:
    """Root health check endpoint.

    Returns:
        dict: JSON object with application status.
    """
    return {"status": "ok"}
