"""
Unit tests for the VPS health endpoint.

Tests verify:
- GET /health returns HTTP 200.
- GET /health returns {"status": "ok"}.
- GET /health does not require authentication.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-015)

TODO:
- None
"""

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Test: health returns 200
# ---------------------------------------------------------------------------


class TestHealthReturns200:
    """AC2: GET /health returns HTTP 200."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """GET /health responds with status code 200."""
        response = client.get("/health")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Test: health returns {"status": "ok"}
# ---------------------------------------------------------------------------


class TestHealthReturnsOkStatus:
    """AC2: GET /health returns JSON with status ok."""

    def test_health_returns_ok_status(self, client: TestClient) -> None:
        """GET /health responds with {"status": "ok"}."""
        response = client.get("/health")
        assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Test: health does not require auth
# ---------------------------------------------------------------------------


class TestHealthNoAuthRequired:
    """AC2: GET /health does not require authentication."""

    def test_health_no_auth_required(self, client: TestClient) -> None:
        """GET /health succeeds without any Authorization header."""
        response = client.get("/health")
        # No Authorization header sent, should still be 200
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
