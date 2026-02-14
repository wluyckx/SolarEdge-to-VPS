"""
Tests for the GET /v1/series endpoint (STORY-012).

Validates historical rollup queries with time-bucketed data at different
resolutions (day/month/year/all), frame validation, empty results, and
authentication/authorisation.

TDD: These tests are written FIRST, before the endpoint implementation.

CHANGELOG:
- 2026-02-14: Initial creation with TDD tests (STORY-012)

TODO:
- None
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

AUTH_HEADER = {"Authorization": "Bearer test-token-abc"}
DEVICE_ID = "device-001"
SERIES_URL = "/v1/series"


def _make_bucket_row(
    bucket: str = "2026-02-14T12:00:00+00:00",
    avg_pv_power_w: float = 3500.0,
    max_pv_power_w: float = 4200.0,
    avg_battery_power_w: float = -1500.0,
    avg_battery_soc_pct: float = 75.0,
    avg_load_power_w: float = 2000.0,
    avg_export_power_w: float = 500.0,
    sample_count: int = 12,
) -> dict:
    """Build a single bucket row dict mimicking a DB result mapping."""
    return {
        "bucket": datetime.fromisoformat(bucket),
        "avg_pv_power_w": avg_pv_power_w,
        "max_pv_power_w": max_pv_power_w,
        "avg_battery_power_w": avg_battery_power_w,
        "avg_battery_soc_pct": avg_battery_soc_pct,
        "avg_load_power_w": avg_load_power_w,
        "avg_export_power_w": avg_export_power_w,
        "sample_count": sample_count,
    }


def _mock_db_with_rows(rows: list[dict]) -> AsyncMock:
    """Create a mock AsyncSession whose execute returns the given rows."""
    session = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.all.return_value = rows
    session.execute = AsyncMock(return_value=result)
    return session


def _override_db_factory(mock_session: AsyncMock):
    """Create a dependency override for get_db that yields mock_session."""

    async def _override():
        yield mock_session

    return _override


# ---------------------------------------------------------------------------
# Tests for AC1: frame=day returns hourly-bucketed data for today
# ---------------------------------------------------------------------------


class TestSeriesFrameDay:
    """Tests for frame=day returning hourly buckets."""

    def test_frame_day_returns_hourly_buckets(self, client: TestClient) -> None:
        """AC1: frame=day returns hourly-bucketed data for today."""
        rows = [
            _make_bucket_row(bucket="2026-02-14T08:00:00+00:00", sample_count=12),
            _make_bucket_row(bucket="2026-02-14T09:00:00+00:00", sample_count=12),
            _make_bucket_row(bucket="2026-02-14T10:00:00+00:00", sample_count=10),
        ]
        mock_session = _mock_db_with_rows(rows)

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_session)
        try:
            response = client.get(
                SERIES_URL,
                params={"device_id": DEVICE_ID, "frame": "day"},
                headers=AUTH_HEADER,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["device_id"] == DEVICE_ID
            assert data["frame"] == "day"
            assert len(data["series"]) == 3

            # Verify bucket structure (AC5)
            bucket = data["series"][0]
            assert "bucket" in bucket
            assert "avg_pv_power_w" in bucket
            assert "max_pv_power_w" in bucket
            assert "avg_battery_power_w" in bucket
            assert "avg_battery_soc_pct" in bucket
            assert "avg_load_power_w" in bucket
            assert "avg_export_power_w" in bucket
            assert "sample_count" in bucket
            assert bucket["sample_count"] == 12
        finally:
            app.dependency_overrides.clear()

    def test_frame_day_queries_hourly_view(self, client: TestClient) -> None:
        """AC1: frame=day queries the sungrow_hourly view."""
        mock_session = _mock_db_with_rows([])

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_session)
        try:
            response = client.get(
                SERIES_URL,
                params={"device_id": DEVICE_ID, "frame": "day"},
                headers=AUTH_HEADER,
            )
            assert response.status_code == 200

            # Verify the SQL query targeted sungrow_hourly
            call_args = mock_session.execute.call_args
            sql_text = str(call_args[0][0])
            assert "sungrow_hourly" in sql_text
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests for AC2: frame=month returns daily-bucketed data
# ---------------------------------------------------------------------------


class TestSeriesFrameMonth:
    """Tests for frame=month returning daily buckets."""

    def test_frame_month_returns_daily_buckets(self, client: TestClient) -> None:
        """AC2: frame=month returns daily-bucketed data for current month."""
        rows = [
            _make_bucket_row(bucket="2026-02-01T00:00:00+00:00", sample_count=288),
            _make_bucket_row(bucket="2026-02-02T00:00:00+00:00", sample_count=288),
        ]
        mock_session = _mock_db_with_rows(rows)

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_session)
        try:
            response = client.get(
                SERIES_URL,
                params={"device_id": DEVICE_ID, "frame": "month"},
                headers=AUTH_HEADER,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["device_id"] == DEVICE_ID
            assert data["frame"] == "month"
            assert len(data["series"]) == 2
        finally:
            app.dependency_overrides.clear()

    def test_frame_month_queries_daily_view(self, client: TestClient) -> None:
        """AC2: frame=month queries the sungrow_daily view."""
        mock_session = _mock_db_with_rows([])

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_session)
        try:
            response = client.get(
                SERIES_URL,
                params={"device_id": DEVICE_ID, "frame": "month"},
                headers=AUTH_HEADER,
            )
            assert response.status_code == 200

            call_args = mock_session.execute.call_args
            sql_text = str(call_args[0][0])
            assert "sungrow_daily" in sql_text
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests for AC3: frame=year returns monthly-bucketed data
# ---------------------------------------------------------------------------


class TestSeriesFrameYear:
    """Tests for frame=year returning monthly buckets."""

    def test_frame_year_returns_monthly_buckets(self, client: TestClient) -> None:
        """AC3: frame=year returns monthly-bucketed data for current year."""
        rows = [
            _make_bucket_row(bucket="2026-01-01T00:00:00+00:00", sample_count=8640),
            _make_bucket_row(bucket="2026-02-01T00:00:00+00:00", sample_count=4032),
        ]
        mock_session = _mock_db_with_rows(rows)

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_session)
        try:
            response = client.get(
                SERIES_URL,
                params={"device_id": DEVICE_ID, "frame": "year"},
                headers=AUTH_HEADER,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["device_id"] == DEVICE_ID
            assert data["frame"] == "year"
            assert len(data["series"]) == 2
        finally:
            app.dependency_overrides.clear()

    def test_frame_year_queries_monthly_view(self, client: TestClient) -> None:
        """AC3: frame=year queries the sungrow_monthly view."""
        mock_session = _mock_db_with_rows([])

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_session)
        try:
            response = client.get(
                SERIES_URL,
                params={"device_id": DEVICE_ID, "frame": "year"},
                headers=AUTH_HEADER,
            )
            assert response.status_code == 200

            call_args = mock_session.execute.call_args
            sql_text = str(call_args[0][0])
            assert "sungrow_monthly" in sql_text
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests for AC4: frame=all returns monthly-bucketed data all-time
# ---------------------------------------------------------------------------


class TestSeriesFrameAll:
    """Tests for frame=all returning monthly buckets all-time."""

    def test_frame_all_returns_monthly_buckets(self, client: TestClient) -> None:
        """AC4: frame=all returns monthly-bucketed data all-time."""
        rows = [
            _make_bucket_row(bucket="2025-06-01T00:00:00+00:00", sample_count=8640),
            _make_bucket_row(bucket="2025-07-01T00:00:00+00:00", sample_count=8928),
            _make_bucket_row(bucket="2026-01-01T00:00:00+00:00", sample_count=8640),
        ]
        mock_session = _mock_db_with_rows(rows)

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_session)
        try:
            response = client.get(
                SERIES_URL,
                params={"device_id": DEVICE_ID, "frame": "all"},
                headers=AUTH_HEADER,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["device_id"] == DEVICE_ID
            assert data["frame"] == "all"
            assert len(data["series"]) == 3
        finally:
            app.dependency_overrides.clear()

    def test_frame_all_queries_monthly_view_without_time_filter(
        self, client: TestClient
    ) -> None:
        """AC4: frame=all queries sungrow_monthly without a time filter."""
        mock_session = _mock_db_with_rows([])

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_session)
        try:
            response = client.get(
                SERIES_URL,
                params={"device_id": DEVICE_ID, "frame": "all"},
                headers=AUTH_HEADER,
            )
            assert response.status_code == 200

            call_args = mock_session.execute.call_args
            sql_text = str(call_args[0][0])
            assert "sungrow_monthly" in sql_text
            # frame=all should NOT have date_trunc filter
            assert "date_trunc" not in sql_text
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests for AC5: Bucket fields
# ---------------------------------------------------------------------------


class TestSeriesBucketFields:
    """Tests for bucket field structure (AC5)."""

    def test_bucket_contains_all_required_fields(self, client: TestClient) -> None:
        """AC5: Each bucket includes all required metric fields."""
        rows = [
            _make_bucket_row(
                bucket="2026-02-14T10:00:00+00:00",
                avg_pv_power_w=3500.0,
                max_pv_power_w=4200.0,
                avg_battery_power_w=-1500.0,
                avg_battery_soc_pct=75.0,
                avg_load_power_w=2000.0,
                avg_export_power_w=500.0,
                sample_count=12,
            ),
        ]
        mock_session = _mock_db_with_rows(rows)

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_session)
        try:
            response = client.get(
                SERIES_URL,
                params={"device_id": DEVICE_ID, "frame": "day"},
                headers=AUTH_HEADER,
            )
            assert response.status_code == 200
            bucket = response.json()["series"][0]
            assert bucket["avg_pv_power_w"] == 3500.0
            assert bucket["max_pv_power_w"] == 4200.0
            assert bucket["avg_battery_power_w"] == -1500.0
            assert bucket["avg_battery_soc_pct"] == 75.0
            assert bucket["avg_load_power_w"] == 2000.0
            assert bucket["avg_export_power_w"] == 500.0
            assert bucket["sample_count"] == 12
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests for AC6: Auth validation (401/403)
# ---------------------------------------------------------------------------


class TestSeriesAuth:
    """Tests for authentication and authorisation on the series endpoint."""

    def test_no_auth_returns_401(self, client: TestClient) -> None:
        """AC6: Missing Authorization header returns 401."""
        response = client.get(
            SERIES_URL,
            params={"device_id": DEVICE_ID, "frame": "day"},
        )
        assert response.status_code == 401

    def test_invalid_token_returns_401(self, client: TestClient) -> None:
        """AC6: Invalid Bearer token returns 401."""
        response = client.get(
            SERIES_URL,
            params={"device_id": DEVICE_ID, "frame": "day"},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert response.status_code == 401

    def test_device_id_mismatch_returns_403(self, client: TestClient) -> None:
        """AC6: device_id not matching authenticated token returns 403."""
        response = client.get(
            SERIES_URL,
            params={"device_id": "wrong-device", "frame": "day"},
            headers=AUTH_HEADER,
        )
        assert response.status_code == 403
        assert "device_id" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Tests for AC7: Invalid frame returns 422
# ---------------------------------------------------------------------------


class TestSeriesInvalidFrame:
    """Tests for frame validation (AC7)."""

    def test_invalid_frame_returns_422(self, client: TestClient) -> None:
        """AC7: Invalid frame value returns 422."""
        response = client.get(
            SERIES_URL,
            params={"device_id": DEVICE_ID, "frame": "invalid"},
            headers=AUTH_HEADER,
        )
        assert response.status_code == 422

    def test_missing_frame_returns_422(self, client: TestClient) -> None:
        """AC7: Missing frame parameter returns 422."""
        response = client.get(
            SERIES_URL,
            params={"device_id": DEVICE_ID},
            headers=AUTH_HEADER,
        )
        assert response.status_code == 422

    def test_missing_device_id_returns_422(self, client: TestClient) -> None:
        """AC7: Missing device_id parameter returns 422."""
        response = client.get(
            SERIES_URL,
            params={"frame": "day"},
            headers=AUTH_HEADER,
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tests for AC8: Empty result returns empty series list
# ---------------------------------------------------------------------------


class TestSeriesEmptyResult:
    """Tests for empty query results (AC8)."""

    def test_empty_result_returns_empty_series(self, client: TestClient) -> None:
        """AC8: No data for the device returns {"series": []}."""
        mock_session = _mock_db_with_rows([])

        from src.api.deps import get_db
        from src.api.main import app

        app.dependency_overrides[get_db] = _override_db_factory(mock_session)
        try:
            response = client.get(
                SERIES_URL,
                params={"device_id": DEVICE_ID, "frame": "day"},
                headers=AUTH_HEADER,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["device_id"] == DEVICE_ID
            assert data["frame"] == "day"
            assert data["series"] == []
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests for aggregation service directly
# ---------------------------------------------------------------------------


class TestAggregationService:
    """Unit tests for the aggregation service query_series function."""

    @pytest.mark.asyncio
    async def test_query_series_day_builds_correct_sql(self) -> None:
        """query_series with frame=day queries sungrow_hourly with time filter."""
        mock_session = _mock_db_with_rows([])

        from src.services.aggregation import query_series

        result = await query_series(mock_session, DEVICE_ID, "day")
        assert result == []

        call_args = mock_session.execute.call_args
        sql_text = str(call_args[0][0])
        assert "sungrow_hourly" in sql_text
        assert "date_trunc('day'" in sql_text

    @pytest.mark.asyncio
    async def test_query_series_month_builds_correct_sql(self) -> None:
        """query_series with frame=month queries sungrow_daily with time filter."""
        mock_session = _mock_db_with_rows([])

        from src.services.aggregation import query_series

        result = await query_series(mock_session, DEVICE_ID, "month")
        assert result == []

        call_args = mock_session.execute.call_args
        sql_text = str(call_args[0][0])
        assert "sungrow_daily" in sql_text
        assert "date_trunc('month'" in sql_text

    @pytest.mark.asyncio
    async def test_query_series_year_builds_correct_sql(self) -> None:
        """query_series with frame=year queries sungrow_monthly with time filter."""
        mock_session = _mock_db_with_rows([])

        from src.services.aggregation import query_series

        result = await query_series(mock_session, DEVICE_ID, "year")
        assert result == []

        call_args = mock_session.execute.call_args
        sql_text = str(call_args[0][0])
        assert "sungrow_monthly" in sql_text
        assert "date_trunc('year'" in sql_text

    @pytest.mark.asyncio
    async def test_query_series_all_no_time_filter(self) -> None:
        """query_series with frame=all queries sungrow_monthly without time filter."""
        mock_session = _mock_db_with_rows([])

        from src.services.aggregation import query_series

        result = await query_series(mock_session, DEVICE_ID, "all")
        assert result == []

        call_args = mock_session.execute.call_args
        sql_text = str(call_args[0][0])
        assert "sungrow_monthly" in sql_text
        assert "date_trunc" not in sql_text

    @pytest.mark.asyncio
    async def test_query_series_returns_row_dicts(self) -> None:
        """query_series returns a list of dicts from the DB result."""
        rows = [
            _make_bucket_row(bucket="2026-02-14T10:00:00+00:00"),
            _make_bucket_row(bucket="2026-02-14T11:00:00+00:00"),
        ]
        mock_session = _mock_db_with_rows(rows)

        from src.services.aggregation import query_series

        result = await query_series(mock_session, DEVICE_ID, "day")
        assert len(result) == 2
        assert result[0]["avg_pv_power_w"] == 3500.0
        assert result[0]["sample_count"] == 12

    @pytest.mark.asyncio
    async def test_query_series_invalid_frame_raises_keyerror(self) -> None:
        """query_series with an invalid frame raises KeyError."""
        mock_session = _mock_db_with_rows([])

        from src.services.aggregation import query_series

        with pytest.raises(KeyError):
            await query_series(mock_session, DEVICE_ID, "invalid")
