"""
Tests for the GET /v1/realtime endpoint (STORY-011).

Validates Bearer auth, device_id ownership, Redis caching with TTL,
database fallback, and error responses (401, 403, 404).

TDD: These tests are written FIRST, before the endpoint implementation.

CHANGELOG:
- 2026-02-14: Initial creation with TDD tests (STORY-011)

TODO:
- None
"""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

AUTH_HEADER = {"Authorization": "Bearer test-token-abc"}
DEVICE_ID = "device-001"
REALTIME_URL = "/v1/realtime"

SAMPLE_TS = datetime(2026, 2, 14, 12, 0, 0, tzinfo=UTC)

SAMPLE_DICT = {
    "device_id": DEVICE_ID,
    "ts": SAMPLE_TS.isoformat(),
    "pv_power_w": 3500.0,
    "pv_daily_kwh": 12.5,
    "battery_power_w": -1500.0,
    "battery_soc_pct": 75.0,
    "battery_temp_c": 28.0,
    "load_power_w": 2000.0,
    "export_power_w": 500.0,
    "sample_count": 1,
}

ALL_SAMPLE_FIELDS = [
    "device_id",
    "ts",
    "pv_power_w",
    "pv_daily_kwh",
    "battery_power_w",
    "battery_soc_pct",
    "battery_temp_c",
    "load_power_w",
    "export_power_w",
    "sample_count",
]


def _make_orm_sample(**overrides: object) -> MagicMock:
    """Build a mock SungrowSample ORM object with sensible defaults."""
    sample = MagicMock()
    defaults = {
        "device_id": DEVICE_ID,
        "ts": SAMPLE_TS,
        "pv_power_w": 3500.0,
        "pv_daily_kwh": 12.5,
        "battery_power_w": -1500.0,
        "battery_soc_pct": 75.0,
        "battery_temp_c": 28.0,
        "load_power_w": 2000.0,
        "export_power_w": 500.0,
        "sample_count": 1,
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        setattr(sample, key, value)
    return sample


def _override_db_factory(mock_session: AsyncMock):
    """Create a dependency override for get_db that yields mock_session."""

    async def _override():
        yield mock_session

    return _override


def _mock_redis_client(
    cached_value: str | None = None,
    get_side_effect: Exception | None = None,
    set_side_effect: Exception | None = None,
) -> AsyncMock:
    """Create a mock Redis client with configurable behaviour.

    Args:
        cached_value: Value to return from get(), or None for cache miss.
        get_side_effect: Exception to raise on get(), simulating Redis failure.
        set_side_effect: Exception to raise on set(), simulating Redis failure.

    Returns:
        AsyncMock: Configured mock Redis client.
    """
    mock = AsyncMock()
    if get_side_effect is not None:
        mock.get = AsyncMock(side_effect=get_side_effect)
    else:
        mock.get = AsyncMock(return_value=cached_value)
    if set_side_effect is not None:
        mock.set = AsyncMock(side_effect=set_side_effect)
    else:
        mock.set = AsyncMock()
    mock.aclose = AsyncMock()
    return mock


# ---------------------------------------------------------------------------
# Tests for AC1: GET /v1/realtime requires Bearer auth
# ---------------------------------------------------------------------------


class TestRealtimeAuth:
    """Tests for authentication on the realtime endpoint."""

    def test_no_auth_returns_401(self, client: TestClient) -> None:
        """AC1: Missing Authorization header returns 401."""
        response = client.get(REALTIME_URL, params={"device_id": DEVICE_ID})
        assert response.status_code == 401

    def test_invalid_token_returns_401(self, client: TestClient) -> None:
        """AC1: Invalid Bearer token returns 401."""
        response = client.get(
            REALTIME_URL,
            params={"device_id": DEVICE_ID},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Tests for AC2: device_id mismatch returns 403
# ---------------------------------------------------------------------------


class TestRealtimeDeviceIdMismatch:
    """Tests for device_id ownership validation (AC2)."""

    def test_device_id_mismatch_returns_403(self, client: TestClient) -> None:
        """AC2: Query device_id that does not match auth token returns 403."""
        response = client.get(
            REALTIME_URL,
            params={"device_id": "wrong-device"},
            headers=AUTH_HEADER,
        )
        assert response.status_code == 403
        assert "device_id" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Tests for AC3/AC6: Returns latest sample with all fields
# ---------------------------------------------------------------------------


class TestRealtimeLatestSample:
    """Tests for returning the latest sample with all fields (AC3, AC6)."""

    @patch("src.api.realtime.get_redis")
    def test_returns_latest_sample_with_all_fields(
        self,
        mock_get_redis: AsyncMock,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """AC3/AC6: Returns latest sample from DB with all SungrowSample fields."""
        # Redis cache miss
        redis_mock = _mock_redis_client(cached_value=None)
        mock_get_redis.return_value = redis_mock

        # DB returns a sample
        orm_sample = _make_orm_sample()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = orm_sample
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_db_session)
        try:
            response = client.get(
                REALTIME_URL,
                params={"device_id": DEVICE_ID},
                headers=AUTH_HEADER,
            )
            assert response.status_code == 200
            data = response.json()

            # AC6: All SungrowSample fields are present
            for field in ALL_SAMPLE_FIELDS:
                assert field in data, f"Missing field: {field}"

            # Verify field values
            assert data["device_id"] == DEVICE_ID
            assert data["pv_power_w"] == 3500.0
            assert data["pv_daily_kwh"] == 12.5
            assert data["battery_power_w"] == -1500.0
            assert data["battery_soc_pct"] == 75.0
            assert data["battery_temp_c"] == 28.0
            assert data["load_power_w"] == 2000.0
            assert data["export_power_w"] == 500.0
            assert data["sample_count"] == 1
        finally:
            app.dependency_overrides.clear()

    @patch("src.api.realtime.get_redis")
    def test_returns_nullable_fields_as_null(
        self,
        mock_get_redis: AsyncMock,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """AC6: Nullable fields (pv_daily_kwh, battery_temp_c) can be null."""
        redis_mock = _mock_redis_client(cached_value=None)
        mock_get_redis.return_value = redis_mock

        orm_sample = _make_orm_sample(pv_daily_kwh=None, battery_temp_c=None)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = orm_sample
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_db_session)
        try:
            response = client.get(
                REALTIME_URL,
                params={"device_id": DEVICE_ID},
                headers=AUTH_HEADER,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["pv_daily_kwh"] is None
            assert data["battery_temp_c"] is None
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests for AC4: Redis cache with CACHE_TTL_S TTL
# ---------------------------------------------------------------------------


class TestRealtimeRedisCache:
    """Tests for Redis caching behaviour (AC4)."""

    @patch("src.api.realtime.get_redis")
    def test_cache_hit_returns_cached_data_no_db_query(
        self,
        mock_get_redis: AsyncMock,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """AC4: Redis cache hit returns cached JSON without querying DB."""
        # Redis returns cached data
        cached_json = json.dumps(SAMPLE_DICT)
        redis_mock = _mock_redis_client(cached_value=cached_json)
        mock_get_redis.return_value = redis_mock

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_db_session)
        try:
            response = client.get(
                REALTIME_URL,
                params={"device_id": DEVICE_ID},
                headers=AUTH_HEADER,
            )
            assert response.status_code == 200
            data = response.json()

            # Verify response matches cached data
            assert data["device_id"] == DEVICE_ID
            assert data["pv_power_w"] == 3500.0

            # DB must NOT have been queried
            mock_db_session.execute.assert_not_awaited()
        finally:
            app.dependency_overrides.clear()

    @patch("src.api.realtime.get_redis")
    def test_cache_miss_queries_db_and_caches_result(
        self,
        mock_get_redis: AsyncMock,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """AC4: Redis cache miss queries DB and caches result with TTL."""
        # Redis cache miss
        redis_mock = _mock_redis_client(cached_value=None)
        mock_get_redis.return_value = redis_mock

        # DB returns a sample
        orm_sample = _make_orm_sample()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = orm_sample
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_db_session)
        try:
            response = client.get(
                REALTIME_URL,
                params={"device_id": DEVICE_ID},
                headers=AUTH_HEADER,
            )
            assert response.status_code == 200

            # DB was queried
            mock_db_session.execute.assert_awaited_once()

            # Result was cached in Redis with TTL
            redis_mock.set.assert_awaited_once()
            call_args = redis_mock.set.call_args
            # Key is realtime:{device_id}
            assert call_args[0][0] == f"realtime:{DEVICE_ID}"
            # Value is valid JSON with expected data
            cached_value = json.loads(call_args[0][1])
            assert cached_value["device_id"] == DEVICE_ID
            # TTL (ex) is set -- default is 5
            assert call_args[1].get("ex") == 5
        finally:
            app.dependency_overrides.clear()

    @patch("src.api.realtime.get_redis")
    def test_cache_ttl_uses_config_value(
        self,
        mock_get_redis: AsyncMock,
        mock_db_session: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC4: Cache TTL uses CACHE_TTL_S from config."""
        monkeypatch.setenv("CACHE_TTL_S", "30")

        # Redis cache miss
        redis_mock = _mock_redis_client(cached_value=None)
        mock_get_redis.return_value = redis_mock

        # DB returns a sample
        orm_sample = _make_orm_sample()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = orm_sample
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_db_session)
        try:
            with TestClient(app) as new_client:
                response = new_client.get(
                    REALTIME_URL,
                    params={"device_id": DEVICE_ID},
                    headers=AUTH_HEADER,
                )
                assert response.status_code == 200

                # TTL should be 30 from config
                call_args = redis_mock.set.call_args
                assert call_args[1].get("ex") == 30
        finally:
            app.dependency_overrides.clear()

    @patch("src.api.realtime.get_redis")
    def test_redis_failure_falls_back_to_db(
        self,
        mock_get_redis: AsyncMock,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """Redis failure is best-effort; falls back to DB query."""
        # Redis raises on get and set
        redis_mock = _mock_redis_client(
            get_side_effect=Exception("Redis down"),
            set_side_effect=Exception("Redis down"),
        )
        mock_get_redis.return_value = redis_mock

        # DB returns a sample
        orm_sample = _make_orm_sample()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = orm_sample
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_db_session)
        try:
            response = client.get(
                REALTIME_URL,
                params={"device_id": DEVICE_ID},
                headers=AUTH_HEADER,
            )
            # Should still return 200 despite Redis failure
            assert response.status_code == 200
            data = response.json()
            assert data["device_id"] == DEVICE_ID
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests for AC5: 404 if no data exists for device
# ---------------------------------------------------------------------------


class TestRealtimeNoData:
    """Tests for 404 when no data exists (AC5)."""

    @patch("src.api.realtime.get_redis")
    def test_no_data_returns_404(
        self,
        mock_get_redis: AsyncMock,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """AC5: 404 when no sample exists for device in DB."""
        # Redis cache miss
        redis_mock = _mock_redis_client(cached_value=None)
        mock_get_redis.return_value = redis_mock

        # DB returns no result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_db_session)
        try:
            response = client.get(
                REALTIME_URL,
                params={"device_id": DEVICE_ID},
                headers=AUTH_HEADER,
            )
            assert response.status_code == 404
            assert "no data" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()
