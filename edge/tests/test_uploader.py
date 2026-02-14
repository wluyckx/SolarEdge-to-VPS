"""
Unit tests for the HTTPS batch uploader module.

Tests verify:
- Uploader peeks BATCH_SIZE samples from spool (AC1).
- Uploader POSTs {"samples": [...]} to VPS_BASE_URL/v1/ingest (AC2).
- Uploader includes Bearer token in Authorization header (AC3).
- On 200 response: acks rows in spool (AC4).
- On failure (non-200, timeout, connection error): exponential backoff (AC5).
- Backoff resets to initial value on success (AC6).
- Validates VPS URL is HTTPS at startup; rejects http:// (AC7).
- TLS certificate verification always enabled (AC8).

CHANGELOG:
- 2026-02-14: Initial creation (STORY-006)

TODO:
- None
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from edge.src.uploader import Uploader

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_payload(
    device_id: str = "sungrow-test",
    ts: str = "2026-02-14T10:00:00Z",
    pv_power_w: int = 3500,
    battery_soc_pct: float = 72.5,
) -> str:
    """Return a valid JSON payload string matching the spool use case."""
    return json.dumps(
        {
            "device_id": device_id,
            "ts": ts,
            "pv_power_w": pv_power_w,
            "battery_soc_pct": battery_soc_pct,
        }
    )


def _make_spool_rows(count: int = 3) -> list[tuple[int, str]]:
    """Return a list of (rowid, payload) tuples simulating spool.peek() output."""
    return [
        (i + 1, _make_payload(ts=f"2026-02-14T10:00:{i:02d}Z")) for i in range(count)
    ]


# ---------------------------------------------------------------------------
# AC7: HTTPS URL validation at construction
# ---------------------------------------------------------------------------


class TestHTTPSValidation:
    """Uploader rejects non-HTTPS URLs at construction."""

    def test_http_url_rejected(self) -> None:
        """AC7: http:// URL raises ValueError at construction."""
        with pytest.raises(ValueError, match="HTTPS"):
            Uploader(
                vps_base_url="http://solar.example.com",
                vps_device_token="tok-123",
                batch_size=10,
            )

    def test_https_url_accepted(self) -> None:
        """AC7: https:// URL is accepted at construction."""
        uploader = Uploader(
            vps_base_url="https://solar.example.com",
            vps_device_token="tok-123",
            batch_size=10,
        )
        assert uploader._vps_base_url == "https://solar.example.com"

    def test_http_uppercase_rejected(self) -> None:
        """AC7: HTTP:// (uppercase) URL is also rejected."""
        with pytest.raises(ValueError, match="HTTPS"):
            Uploader(
                vps_base_url="HTTP://solar.example.com",
                vps_device_token="tok-123",
                batch_size=10,
            )


# ---------------------------------------------------------------------------
# AC1: Peek batch from spool
# ---------------------------------------------------------------------------


class TestPeekBatch:
    """Uploader peeks BATCH_SIZE samples from spool."""

    @pytest.mark.asyncio
    async def test_peeks_batch_size_samples(self) -> None:
        """AC1: upload_batch calls spool.peek with the configured batch_size."""
        spool = AsyncMock()
        spool.peek = AsyncMock(return_value=[])

        uploader = Uploader(
            vps_base_url="https://solar.example.com",
            vps_device_token="tok-123",
            batch_size=25,
        )

        await uploader.upload_batch(spool)

        spool.peek.assert_awaited_once_with(25)


# ---------------------------------------------------------------------------
# Empty batch skips upload
# ---------------------------------------------------------------------------


class TestEmptyBatch:
    """Uploader skips upload when spool is empty."""

    @pytest.mark.asyncio
    async def test_empty_batch_skips_upload(self) -> None:
        """Empty batch (no rows in spool) skips HTTP POST entirely."""
        spool = AsyncMock()
        spool.peek = AsyncMock(return_value=[])

        uploader = Uploader(
            vps_base_url="https://solar.example.com",
            vps_device_token="tok-123",
            batch_size=10,
        )

        with patch("edge.src.uploader.httpx.AsyncClient") as mock_client_cls:
            result = await uploader.upload_batch(spool)

            # Should not have created an HTTP client at all.
            mock_client_cls.assert_not_called()

        # upload_batch returns False (nothing uploaded).
        assert result is False
        # Spool.ack should not have been called.
        spool.ack.assert_not_awaited()


# ---------------------------------------------------------------------------
# AC2 + AC3: POST with correct payload and Bearer token
# ---------------------------------------------------------------------------


class TestPostPayload:
    """Uploader POSTs correct JSON payload with Bearer auth."""

    @pytest.mark.asyncio
    async def test_posts_samples_to_ingest_endpoint(self) -> None:
        """AC2 + AC3: POST to /v1/ingest with Bearer token and samples payload."""
        rows = _make_spool_rows(2)
        spool = AsyncMock()
        spool.peek = AsyncMock(return_value=rows)
        spool.ack = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        uploader = Uploader(
            vps_base_url="https://solar.example.com",
            vps_device_token="my-secret-token",
            batch_size=10,
        )

        with patch("edge.src.uploader.httpx.AsyncClient", return_value=mock_client):
            await uploader.upload_batch(spool)

        # Verify POST was made.
        mock_client.post.assert_awaited_once()
        call_args = mock_client.post.call_args

        # Check URL.
        assert call_args[0][0] == "https://solar.example.com/v1/ingest"

        # Check payload structure.
        posted_json = call_args[1]["json"]
        assert "samples" in posted_json
        assert len(posted_json["samples"]) == 2
        # Each sample should be a parsed dict.
        assert posted_json["samples"][0]["device_id"] == "sungrow-test"

        # Check Authorization header.
        headers = call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer my-secret-token"


# ---------------------------------------------------------------------------
# AC4: Successful upload acks spool rows
# ---------------------------------------------------------------------------


class TestSuccessfulUpload:
    """On 200 response, uploader acks rows in spool."""

    @pytest.mark.asyncio
    async def test_200_acks_spool_rows(self) -> None:
        """AC4: 200 response triggers spool.ack with the peeked rowids."""
        rows = _make_spool_rows(3)
        spool = AsyncMock()
        spool.peek = AsyncMock(return_value=rows)
        spool.ack = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        uploader = Uploader(
            vps_base_url="https://solar.example.com",
            vps_device_token="tok-123",
            batch_size=10,
        )

        with patch("edge.src.uploader.httpx.AsyncClient", return_value=mock_client):
            result = await uploader.upload_batch(spool)

        # Should have acked the correct rowids.
        spool.ack.assert_awaited_once_with([1, 2, 3])
        assert result is True

    @pytest.mark.asyncio
    async def test_upload_returns_true_on_success(self) -> None:
        """upload_batch returns True on successful upload and ack."""
        rows = _make_spool_rows(1)
        spool = AsyncMock()
        spool.peek = AsyncMock(return_value=rows)
        spool.ack = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        uploader = Uploader(
            vps_base_url="https://solar.example.com",
            vps_device_token="tok-123",
            batch_size=10,
        )

        with patch("edge.src.uploader.httpx.AsyncClient", return_value=mock_client):
            result = await uploader.upload_batch(spool)

        assert result is True


# ---------------------------------------------------------------------------
# AC5: Failure does NOT ack rows
# ---------------------------------------------------------------------------


class TestFailureDoesNotAck:
    """On failure, uploader does NOT ack rows and triggers backoff."""

    @pytest.mark.asyncio
    async def test_401_does_not_ack(self) -> None:
        """401 response does not ack rows."""
        rows = _make_spool_rows(2)
        spool = AsyncMock()
        spool.peek = AsyncMock(return_value=rows)
        spool.ack = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 401

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        uploader = Uploader(
            vps_base_url="https://solar.example.com",
            vps_device_token="tok-123",
            batch_size=10,
        )

        with patch("edge.src.uploader.httpx.AsyncClient", return_value=mock_client):
            result = await uploader.upload_batch(spool)

        spool.ack.assert_not_awaited()
        assert result is False

    @pytest.mark.asyncio
    async def test_500_does_not_ack(self) -> None:
        """500 response does not ack rows."""
        rows = _make_spool_rows(2)
        spool = AsyncMock()
        spool.peek = AsyncMock(return_value=rows)
        spool.ack = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        uploader = Uploader(
            vps_base_url="https://solar.example.com",
            vps_device_token="tok-123",
            batch_size=10,
        )

        with patch("edge.src.uploader.httpx.AsyncClient", return_value=mock_client):
            result = await uploader.upload_batch(spool)

        spool.ack.assert_not_awaited()
        assert result is False

    @pytest.mark.asyncio
    async def test_connection_error_does_not_ack(self) -> None:
        """Connection error does not ack rows."""
        rows = _make_spool_rows(2)
        spool = AsyncMock()
        spool.peek = AsyncMock(return_value=rows)
        spool.ack = AsyncMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        uploader = Uploader(
            vps_base_url="https://solar.example.com",
            vps_device_token="tok-123",
            batch_size=10,
        )

        with patch("edge.src.uploader.httpx.AsyncClient", return_value=mock_client):
            result = await uploader.upload_batch(spool)

        spool.ack.assert_not_awaited()
        assert result is False

    @pytest.mark.asyncio
    async def test_timeout_error_does_not_ack(self) -> None:
        """Timeout error does not ack rows."""
        rows = _make_spool_rows(2)
        spool = AsyncMock()
        spool.peek = AsyncMock(return_value=rows)
        spool.ack = AsyncMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        uploader = Uploader(
            vps_base_url="https://solar.example.com",
            vps_device_token="tok-123",
            batch_size=10,
        )

        with patch("edge.src.uploader.httpx.AsyncClient", return_value=mock_client):
            result = await uploader.upload_batch(spool)

        spool.ack.assert_not_awaited()
        assert result is False


# ---------------------------------------------------------------------------
# AC5: Exponential backoff on failure
# ---------------------------------------------------------------------------


class TestBackoff:
    """Exponential backoff on consecutive failures, capped at max."""

    def test_initial_backoff_is_one_second(self) -> None:
        """Initial backoff value is 1 second."""
        uploader = Uploader(
            vps_base_url="https://solar.example.com",
            vps_device_token="tok-123",
            batch_size=10,
        )
        assert uploader.current_backoff == 1.0

    @pytest.mark.asyncio
    async def test_401_triggers_backoff_increase(self) -> None:
        """401 response doubles the backoff."""
        rows = _make_spool_rows(1)
        spool = AsyncMock()
        spool.peek = AsyncMock(return_value=rows)
        spool.ack = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 401

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        uploader = Uploader(
            vps_base_url="https://solar.example.com",
            vps_device_token="tok-123",
            batch_size=10,
        )

        with patch("edge.src.uploader.httpx.AsyncClient", return_value=mock_client):
            await uploader.upload_batch(spool)

        assert uploader.current_backoff == 2.0

    @pytest.mark.asyncio
    async def test_500_triggers_backoff_increase(self) -> None:
        """500 response doubles the backoff."""
        rows = _make_spool_rows(1)
        spool = AsyncMock()
        spool.peek = AsyncMock(return_value=rows)
        spool.ack = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        uploader = Uploader(
            vps_base_url="https://solar.example.com",
            vps_device_token="tok-123",
            batch_size=10,
        )

        with patch("edge.src.uploader.httpx.AsyncClient", return_value=mock_client):
            await uploader.upload_batch(spool)

        assert uploader.current_backoff == 2.0

    @pytest.mark.asyncio
    async def test_connection_error_triggers_backoff(self) -> None:
        """Connection error doubles the backoff."""
        rows = _make_spool_rows(1)
        spool = AsyncMock()
        spool.peek = AsyncMock(return_value=rows)
        spool.ack = AsyncMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        uploader = Uploader(
            vps_base_url="https://solar.example.com",
            vps_device_token="tok-123",
            batch_size=10,
        )

        with patch("edge.src.uploader.httpx.AsyncClient", return_value=mock_client):
            await uploader.upload_batch(spool)

        assert uploader.current_backoff == 2.0

    @pytest.mark.asyncio
    async def test_backoff_doubles_on_consecutive_failures(self) -> None:
        """Backoff doubles: 1 -> 2 -> 4 -> 8 on consecutive failures."""
        rows = _make_spool_rows(1)
        spool = AsyncMock()
        spool.peek = AsyncMock(return_value=rows)
        spool.ack = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        uploader = Uploader(
            vps_base_url="https://solar.example.com",
            vps_device_token="tok-123",
            batch_size=10,
        )

        expected_backoffs = [2.0, 4.0, 8.0, 16.0]
        with patch("edge.src.uploader.httpx.AsyncClient", return_value=mock_client):
            for expected in expected_backoffs:
                await uploader.upload_batch(spool)
                assert uploader.current_backoff == expected

    @pytest.mark.asyncio
    async def test_backoff_caps_at_max(self) -> None:
        """Backoff caps at MAX_BACKOFF_S (default 300s)."""
        rows = _make_spool_rows(1)
        spool = AsyncMock()
        spool.peek = AsyncMock(return_value=rows)
        spool.ack = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        uploader = Uploader(
            vps_base_url="https://solar.example.com",
            vps_device_token="tok-123",
            batch_size=10,
            max_backoff_s=300,
        )

        # Fail many times to exceed cap: 1->2->4->8->16->32->64->128->256->300
        with patch("edge.src.uploader.httpx.AsyncClient", return_value=mock_client):
            for _ in range(20):
                await uploader.upload_batch(spool)

        assert uploader.current_backoff == 300.0

    @pytest.mark.asyncio
    async def test_backoff_caps_at_custom_max(self) -> None:
        """Backoff caps at custom MAX_BACKOFF_S value."""
        rows = _make_spool_rows(1)
        spool = AsyncMock()
        spool.peek = AsyncMock(return_value=rows)
        spool.ack = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        uploader = Uploader(
            vps_base_url="https://solar.example.com",
            vps_device_token="tok-123",
            batch_size=10,
            max_backoff_s=10,
        )

        # Fail many times: 1->2->4->8->10->10
        with patch("edge.src.uploader.httpx.AsyncClient", return_value=mock_client):
            for _ in range(10):
                await uploader.upload_batch(spool)

        assert uploader.current_backoff == 10.0


# ---------------------------------------------------------------------------
# AC6: Backoff resets on success
# ---------------------------------------------------------------------------


class TestBackoffReset:
    """Backoff resets to initial value (1s) on successful upload."""

    @pytest.mark.asyncio
    async def test_backoff_resets_on_success(self) -> None:
        """AC6: backoff resets to 1s after a successful upload."""
        rows = _make_spool_rows(1)
        spool = AsyncMock()
        spool.peek = AsyncMock(return_value=rows)
        spool.ack = AsyncMock()

        fail_response = MagicMock()
        fail_response.status_code = 500

        success_response = MagicMock()
        success_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        uploader = Uploader(
            vps_base_url="https://solar.example.com",
            vps_device_token="tok-123",
            batch_size=10,
        )

        with patch("edge.src.uploader.httpx.AsyncClient", return_value=mock_client):
            # Fail three times: backoff should be 1->2->4->8.
            mock_client.post = AsyncMock(return_value=fail_response)
            for _ in range(3):
                await uploader.upload_batch(spool)
            assert uploader.current_backoff == 8.0

            # Now succeed: backoff should reset to 1.0.
            mock_client.post = AsyncMock(return_value=success_response)
            await uploader.upload_batch(spool)
            assert uploader.current_backoff == 1.0

    @pytest.mark.asyncio
    async def test_backoff_resets_after_being_at_max(self) -> None:
        """Backoff resets from max (300s) to 1s on success."""
        rows = _make_spool_rows(1)
        spool = AsyncMock()
        spool.peek = AsyncMock(return_value=rows)
        spool.ack = AsyncMock()

        fail_response = MagicMock()
        fail_response.status_code = 500

        success_response = MagicMock()
        success_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        uploader = Uploader(
            vps_base_url="https://solar.example.com",
            vps_device_token="tok-123",
            batch_size=10,
            max_backoff_s=300,
        )

        with patch("edge.src.uploader.httpx.AsyncClient", return_value=mock_client):
            # Fail enough to hit cap.
            mock_client.post = AsyncMock(return_value=fail_response)
            for _ in range(20):
                await uploader.upload_batch(spool)
            assert uploader.current_backoff == 300.0

            # Succeed: backoff resets.
            mock_client.post = AsyncMock(return_value=success_response)
            await uploader.upload_batch(spool)
            assert uploader.current_backoff == 1.0


# ---------------------------------------------------------------------------
# AC8: TLS verification always enabled
# ---------------------------------------------------------------------------


class TestTLSVerification:
    """TLS certificate verification is always enabled."""

    @pytest.mark.asyncio
    async def test_tls_verify_true(self) -> None:
        """AC8: httpx.AsyncClient is created with verify=True."""
        rows = _make_spool_rows(1)
        spool = AsyncMock()
        spool.peek = AsyncMock(return_value=rows)
        spool.ack = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        uploader = Uploader(
            vps_base_url="https://solar.example.com",
            vps_device_token="tok-123",
            batch_size=10,
        )

        with patch(
            "edge.src.uploader.httpx.AsyncClient",
            return_value=mock_client,
        ) as mock_cls:
            await uploader.upload_batch(spool)

            # verify=True should be passed to AsyncClient constructor.
            mock_cls.assert_called_once_with(verify=True)
