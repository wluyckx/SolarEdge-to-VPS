"""
Smoke tests for FastAPI application startup.

Verifies the app starts without errors and root endpoint responds.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-007)
"""

from fastapi.testclient import TestClient


def test_app_starts_and_root_returns_ok(client: TestClient) -> None:
    """App starts without errors and root returns status ok."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
