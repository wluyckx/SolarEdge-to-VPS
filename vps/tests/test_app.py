"""
Smoke tests for FastAPI application startup.

Verifies the app starts without errors and root endpoint responds.

CHANGELOG:
- 2026-02-14: Add test for DEVICE_TOKENS → BearerAuth wiring (STORY-009 AC1)
- 2026-02-14: Initial creation (STORY-007)
"""

from fastapi.testclient import TestClient

from src.auth.bearer import BearerAuth


def test_app_starts_and_root_returns_ok(client: TestClient) -> None:
    """App starts without errors and root returns status ok."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_device_tokens_parsed_into_auth_at_startup(client: TestClient) -> None:
    """DEVICE_TOKENS are parsed into a BearerAuth instance on app.state."""
    from src.api.main import app

    assert hasattr(app.state, "auth")
    assert isinstance(app.state.auth, BearerAuth)
    assert "test-token-abc" in app.state.auth.token_map
    assert app.state.auth.token_map["test-token-abc"] == "device-001"
