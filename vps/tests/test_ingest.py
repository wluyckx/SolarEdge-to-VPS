"""
Tests for the POST /v1/ingest endpoint (STORY-010).

Validates payload acceptance, device_id authorisation, idempotent insertion
with ON CONFLICT DO NOTHING, Redis cache invalidation, batch size limits,
request body size limits, and error responses.

TDD: These tests are written FIRST, before the endpoint implementation.

CHANGELOG:
- 2026-02-14: Initial creation with TDD tests (STORY-010)

TODO:
- None
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"
AUTH_HEADER = {"Authorization": "Bearer test-token-abc"}
DEVICE_ID = "device-001"
INGEST_URL = "/v1/ingest"


def _load_fixture() -> dict:
    """Load sample_data.json fixture."""
    return json.loads((FIXTURES_DIR / "sample_data.json").read_text())


def _make_sample(
    device_id: str = DEVICE_ID,
    ts: str = "2026-02-14T12:00:00Z",
    **overrides: object,
) -> dict:
    """Build a single sample dict with sensible defaults."""
    sample = {
        "device_id": device_id,
        "ts": ts,
        "pv_power_w": 3500.0,
        "battery_power_w": -1500.0,
        "battery_soc_pct": 75.0,
        "load_power_w": 2000.0,
        "export_power_w": 0.0,
    }
    sample.update(overrides)
    return sample


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _mock_execute_result(rowcount: int) -> MagicMock:
    """Create a mock CursorResult with a given rowcount."""
    result = MagicMock()
    result.rowcount = rowcount
    return result


def _override_db_factory(mock_session: AsyncMock):
    """Create a dependency override for get_db that yields mock_session."""

    async def _override():
        yield mock_session

    return _override


# ---------------------------------------------------------------------------
# Tests for AC1: POST /v1/ingest accepts {"samples": [...]} payload
# ---------------------------------------------------------------------------


class TestIngestValidBatch:
    """Tests for valid batch ingestion (AC1, AC3, AC4)."""

    @patch("src.services.ingestion.invalidate_device_cache", new_callable=AsyncMock)
    def test_valid_batch_returns_200_with_inserted_count(
        self,
        mock_cache: AsyncMock,
        client: TestClient,
    ) -> None:
        """AC1/AC4: Valid batch returns 200 with {"inserted": N}."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(3),
        )
        mock_session.commit = AsyncMock()

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_session)
        try:
            payload = _load_fixture()
            response = client.post(INGEST_URL, json=payload, headers=AUTH_HEADER)

            assert response.status_code == 200
            data = response.json()
            assert "inserted" in data
            assert data["inserted"] == 3
        finally:
            app.dependency_overrides.clear()

    @patch("src.services.ingestion.invalidate_device_cache", new_callable=AsyncMock)
    def test_fixture_samples_have_correct_device_id(
        self,
        mock_cache: AsyncMock,
        client: TestClient,
    ) -> None:
        """All fixture samples have device_id matching the auth token."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(3),
        )
        mock_session.commit = AsyncMock()

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_session)
        try:
            payload = _load_fixture()
            for sample in payload["samples"]:
                assert sample["device_id"] == DEVICE_ID

            response = client.post(INGEST_URL, json=payload, headers=AUTH_HEADER)
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests for AC2: device_id mismatch returns 403
# ---------------------------------------------------------------------------


class TestIngestDeviceIdMismatch:
    """Tests for device_id validation (AC2)."""

    def test_device_id_mismatch_returns_403(self, client: TestClient) -> None:
        """AC2: Sample with non-matching device_id returns 403."""
        payload = {
            "samples": [_make_sample(device_id="wrong-device")],
        }
        response = client.post(INGEST_URL, json=payload, headers=AUTH_HEADER)
        assert response.status_code == 403
        assert "device_id" in response.json()["detail"].lower()

    def test_mixed_device_ids_returns_403(self, client: TestClient) -> None:
        """AC2: Mix of matching and non-matching device_ids returns 403."""
        payload = {
            "samples": [
                _make_sample(device_id=DEVICE_ID, ts="2026-02-14T12:00:00Z"),
                _make_sample(device_id="wrong-device", ts="2026-02-14T12:05:00Z"),
            ],
        }
        response = client.post(INGEST_URL, json=payload, headers=AUTH_HEADER)
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tests for AC3: ON CONFLICT DO NOTHING (idempotency)
# ---------------------------------------------------------------------------


class TestIngestIdempotency:
    """Tests for idempotent insertion (AC3)."""

    @patch("src.services.ingestion.invalidate_device_cache", new_callable=AsyncMock)
    def test_duplicate_samples_not_reinserted(
        self,
        mock_cache: AsyncMock,
        client: TestClient,
    ) -> None:
        """AC3: Duplicate samples result in lower inserted count."""
        mock_session = AsyncMock()
        # Simulate that only 1 out of 3 rows was actually inserted
        # (2 were duplicates, ON CONFLICT DO NOTHING)
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(1),
        )
        mock_session.commit = AsyncMock()

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_session)
        try:
            payload = _load_fixture()
            response = client.post(INGEST_URL, json=payload, headers=AUTH_HEADER)

            assert response.status_code == 200
            assert response.json()["inserted"] == 1
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests for AC5: Redis cache invalidation
# ---------------------------------------------------------------------------


class TestIngestCacheInvalidation:
    """Tests for Redis cache invalidation on success (AC5)."""

    @patch("src.services.ingestion.invalidate_device_cache", new_callable=AsyncMock)
    def test_redis_cache_key_deleted_on_success(
        self,
        mock_cache: AsyncMock,
        client: TestClient,
    ) -> None:
        """AC5: Redis realtime:{device_id} key is invalidated after insert."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(3),
        )
        mock_session.commit = AsyncMock()

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_session)
        try:
            payload = _load_fixture()
            response = client.post(INGEST_URL, json=payload, headers=AUTH_HEADER)

            assert response.status_code == 200
            mock_cache.assert_awaited_once_with(DEVICE_ID)
        finally:
            app.dependency_overrides.clear()

    @patch("src.services.ingestion.invalidate_device_cache", new_callable=AsyncMock)
    def test_cache_not_invalidated_on_empty_batch(
        self,
        mock_cache: AsyncMock,
        client: TestClient,
    ) -> None:
        """AC6: Empty batch does not trigger cache invalidation."""
        payload = {"samples": []}
        response = client.post(INGEST_URL, json=payload, headers=AUTH_HEADER)

        assert response.status_code == 200
        mock_cache.assert_not_awaited()


# ---------------------------------------------------------------------------
# Tests for AC6: Empty samples list
# ---------------------------------------------------------------------------


class TestIngestEmptySamples:
    """Tests for empty samples list (AC6)."""

    def test_empty_samples_returns_inserted_zero(self, client: TestClient) -> None:
        """AC6: Empty samples list returns {"inserted": 0} with no error."""
        payload = {"samples": []}
        response = client.post(INGEST_URL, json=payload, headers=AUTH_HEADER)
        assert response.status_code == 200
        assert response.json() == {"inserted": 0}


# ---------------------------------------------------------------------------
# Tests for AC7: Invalid payload returns 422
# ---------------------------------------------------------------------------


class TestIngestInvalidPayload:
    """Tests for payload validation (AC7)."""

    def test_missing_samples_key_returns_422(self, client: TestClient) -> None:
        """AC7: Payload without 'samples' key returns 422."""
        response = client.post(INGEST_URL, json={}, headers=AUTH_HEADER)
        assert response.status_code == 422

    def test_samples_not_a_list_returns_422(self, client: TestClient) -> None:
        """AC7: Payload with non-list 'samples' returns 422."""
        response = client.post(
            INGEST_URL, json={"samples": "not-a-list"}, headers=AUTH_HEADER
        )
        assert response.status_code == 422

    def test_sample_missing_required_field_returns_422(
        self, client: TestClient
    ) -> None:
        """AC7: Sample missing required fields returns 422."""
        payload = {
            "samples": [
                {
                    "device_id": DEVICE_ID,
                    "ts": "2026-02-14T12:00:00Z",
                    # Missing pv_power_w, battery_power_w, etc.
                }
            ],
        }
        response = client.post(INGEST_URL, json=payload, headers=AUTH_HEADER)
        assert response.status_code == 422

    def test_sample_with_invalid_ts_returns_422(self, client: TestClient) -> None:
        """AC7: Sample with unparseable timestamp returns 422."""
        payload = {
            "samples": [_make_sample(ts="not-a-timestamp")],
        }
        response = client.post(INGEST_URL, json=payload, headers=AUTH_HEADER)
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tests for AC8: Batch size cap
# ---------------------------------------------------------------------------


class TestIngestBatchSizeCap:
    """Tests for MAX_SAMPLES_PER_REQUEST limit (AC8)."""

    def test_batch_exceeding_max_samples_returns_413(self, client: TestClient) -> None:
        """AC8: Batch exceeding MAX_SAMPLES_PER_REQUEST (1000) returns 413."""
        samples = [
            _make_sample(
                ts=f"2026-02-14T{i // 3600:02d}:{(i % 3600) // 60:02d}:{i % 60:02d}Z"
            )
            for i in range(1001)
        ]
        payload = {"samples": samples}
        response = client.post(INGEST_URL, json=payload, headers=AUTH_HEADER)
        assert response.status_code == 413
        assert "batch" in response.json()["detail"].lower()

    def test_batch_at_max_samples_is_accepted(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC8: Batch at exactly MAX_SAMPLES_PER_REQUEST is accepted (not 413)."""
        # Set a small limit to avoid generating 1000 samples
        monkeypatch.setenv("MAX_SAMPLES_PER_REQUEST", "5")

        from src.api.deps import get_db
        from src.api.main import app

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=_mock_execute_result(5))
        mock_session.commit = AsyncMock()

        app.dependency_overrides[get_db] = _override_db_factory(mock_session)
        try:
            with TestClient(app) as new_client:
                samples = [
                    _make_sample(ts=f"2026-02-14T12:{i:02d}:00Z") for i in range(5)
                ]
                payload = {"samples": samples}
                with patch(
                    "src.services.ingestion.invalidate_device_cache",
                    new_callable=AsyncMock,
                ):
                    response = new_client.post(
                        INGEST_URL, json=payload, headers=AUTH_HEADER
                    )
                assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests for AC9: Request body size cap
# ---------------------------------------------------------------------------


class TestIngestRequestBodyCap:
    """Tests for MAX_REQUEST_BYTES limit (AC9)."""

    def test_malformed_content_length_returns_400(self, client: TestClient) -> None:
        """Non-numeric Content-Length returns 400, not 500."""
        response = client.post(
            INGEST_URL,
            content=b'{"samples": []}',
            headers={
                **AUTH_HEADER,
                "Content-Type": "application/json",
                "Content-Length": "not-a-number",
            },
        )
        assert response.status_code == 400
        assert "content-length" in response.json()["detail"].lower()

    def test_request_body_exceeding_max_bytes_returns_413(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC9: Request body exceeding MAX_REQUEST_BYTES returns 413."""
        # Set a very small body limit
        monkeypatch.setenv("MAX_REQUEST_BYTES", "100")

        from src.api.main import app

        with TestClient(app) as new_client:
            # Create a payload that is definitely > 100 bytes
            samples = [_make_sample(ts=f"2026-02-14T12:{i:02d}:00Z") for i in range(10)]
            payload = {"samples": samples}
            response = new_client.post(INGEST_URL, json=payload, headers=AUTH_HEADER)
            assert response.status_code == 413
            assert "body" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Tests for authentication
# ---------------------------------------------------------------------------


class TestIngestAuth:
    """Tests for authentication on the ingest endpoint."""

    def test_no_auth_returns_401(self, client: TestClient) -> None:
        """Missing Authorization header returns 401."""
        payload = {"samples": [_make_sample()]}
        response = client.post(INGEST_URL, json=payload)
        assert response.status_code == 401

    def test_invalid_token_returns_401(self, client: TestClient) -> None:
        """Invalid Bearer token returns 401."""
        payload = {"samples": [_make_sample()]}
        response = client.post(
            INGEST_URL,
            json=payload,
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Tests for optional fields
# ---------------------------------------------------------------------------


class TestIngestOptionalFields:
    """Tests that optional fields (pv_daily_kwh, battery_temp_c) are accepted."""

    @patch("src.services.ingestion.invalidate_device_cache", new_callable=AsyncMock)
    def test_optional_fields_as_null(
        self,
        mock_cache: AsyncMock,
        client: TestClient,
    ) -> None:
        """Samples with optional fields set to null are accepted."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=_mock_execute_result(1),
        )
        mock_session.commit = AsyncMock()

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_session)
        try:
            payload = {
                "samples": [
                    _make_sample(
                        pv_daily_kwh=None,
                        battery_temp_c=None,
                    )
                ],
            }
            response = client.post(INGEST_URL, json=payload, headers=AUTH_HEADER)
            assert response.status_code == 200
            assert response.json()["inserted"] == 1
        finally:
            app.dependency_overrides.clear()
