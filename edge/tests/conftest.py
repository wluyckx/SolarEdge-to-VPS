"""
Shared test fixtures for edge daemon tests.

Provides environment variable fixtures for EdgeSettings configuration tests.
All edge env vars are cleaned before each test to ensure isolation.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-001)

TODO:
- None
"""

from __future__ import annotations

import pytest

# All EdgeSettings environment variable names, used for cleanup.
_ALL_EDGE_ENV_VARS = (
    "SUNGROW_HOST",
    "SUNGROW_PORT",
    "SUNGROW_SLAVE_ID",
    "POLL_INTERVAL_S",
    "INTER_REGISTER_DELAY_MS",
    "VPS_BASE_URL",
    "VPS_DEVICE_TOKEN",
    "DEVICE_ID",
    "BATCH_SIZE",
    "UPLOAD_INTERVAL_S",
    "SPOOL_PATH",
)


@pytest.fixture(autouse=True)
def _clean_edge_env(monkeypatch: pytest.MonkeyPatch, tmp_path: str) -> None:
    """Remove all edge env vars and isolate from .env files before each test.

    This runs automatically for every test in the edge test suite.
    Individual tests or fixtures then set only the vars they need.
    Changes working directory to tmp_path so no .env file is accidentally
    loaded by Pydantic BaseSettings.
    """
    for var in _ALL_EDGE_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)


@pytest.fixture()
def env_vars_full(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Set all required and optional environment variables for EdgeSettings.

    Returns the dict of env var names to values for assertion convenience.
    """
    env = {
        "SUNGROW_HOST": "192.168.1.100",
        "SUNGROW_PORT": "502",
        "SUNGROW_SLAVE_ID": "1",
        "POLL_INTERVAL_S": "5",
        "INTER_REGISTER_DELAY_MS": "20",
        "VPS_BASE_URL": "https://solar.example.com",
        "VPS_DEVICE_TOKEN": "test-device-token",
        "DEVICE_ID": "sungrow-test",
        "BATCH_SIZE": "30",
        "UPLOAD_INTERVAL_S": "10",
        "SPOOL_PATH": "/tmp/test-spool.db",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return env


@pytest.fixture()
def env_vars_required_only(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Set only the required environment variables (no optional ones).

    Optional variables should fall back to their defaults.
    """
    env = {
        "SUNGROW_HOST": "10.0.0.50",
        "VPS_BASE_URL": "https://ingest.example.com",
        "VPS_DEVICE_TOKEN": "device-token-xyz",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return env
