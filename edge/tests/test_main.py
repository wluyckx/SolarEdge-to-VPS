"""
Unit tests for the edge daemon main loop module.

Tests verify:
- Poll loop calls poller.poll() -> normalizer.normalize() -> spool.enqueue() (AC1).
- Normalizer returning None skips spool.enqueue() (AC7).
- Poller returning None skips normalizer and spool.
- Upload loop calls uploader.upload_batch(spool) (AC2).
- Empty spool (upload_batch returns False) just waits.
- Shutdown signal cancels loops gracefully (AC4).
- Health file updated after poll (AC6).
- Poll error doesn't crash the loop.
- Upload error doesn't crash the loop.
- Startup logs config summary without secrets (AC5).

CHANGELOG:
- 2026-02-14: Initial creation -- TDD tests written first (STORY-014)

TODO:
- None
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from edge.src.models import SungrowSample

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_RAW = {"total_dc_power": [100], "daily_pv_generation": [50]}
"""Fake raw poller data (just needs to be a non-None dict for mocking)."""


def _make_sample(
    device_id: str = "sungrow-test",
    ts: datetime | None = None,
) -> SungrowSample:
    """Create a fake SungrowSample for test assertions."""
    if ts is None:
        ts = datetime(2026, 2, 14, 10, 0, 0, tzinfo=UTC)
    return SungrowSample(
        device_id=device_id,
        ts=ts,
        pv_power_w=3500.0,
        pv_daily_kwh=12.5,
        battery_power_w=1000.0,
        battery_soc_pct=72.5,
        battery_temp_c=25.0,
        load_power_w=2000.0,
        export_power_w=500.0,
    )


def _make_settings(**overrides: object) -> MagicMock:
    """Create a mock EdgeSettings with sensible defaults."""
    defaults = {
        "sungrow_host": "192.168.1.100",
        "sungrow_port": 502,
        "sungrow_slave_id": 1,
        "poll_interval_s": 5,
        "inter_register_delay_ms": 20,
        "vps_base_url": "https://solar.example.com",
        "vps_device_token": "secret-token-abc",
        "device_id": "sungrow-test",
        "batch_size": 30,
        "upload_interval_s": 10,
        "spool_path": "/tmp/test-spool.db",
    }
    defaults.update(overrides)
    settings = MagicMock()
    for key, value in defaults.items():
        setattr(settings, key, value)
    return settings


def _make_components() -> dict[str, AsyncMock | MagicMock]:
    """Create mock poller, spool, and uploader with sensible defaults."""
    poller = AsyncMock()
    poller.poll = AsyncMock(return_value=_FAKE_RAW)

    spool = AsyncMock()
    spool.open = AsyncMock()
    spool.close = AsyncMock()
    spool.enqueue = AsyncMock()
    spool.count = AsyncMock(return_value=0)
    spool.__aenter__ = AsyncMock(return_value=spool)
    spool.__aexit__ = AsyncMock(return_value=None)

    uploader = AsyncMock()
    uploader.upload_batch = AsyncMock(return_value=True)

    return {"poller": poller, "spool": spool, "uploader": uploader}


# ---------------------------------------------------------------------------
# Test: poll loop calls poller.poll() -> normalize() -> spool.enqueue()
# ---------------------------------------------------------------------------


class TestPollLoopHappyPath:
    """AC1: poll loop executes the full pipeline on each iteration."""

    @pytest.mark.asyncio
    async def test_poll_loop_calls_full_pipeline(self) -> None:
        """Poll loop calls poller.poll(), normalize(), spool.enqueue()."""
        from edge.src.main import _poll_once

        components = _make_components()
        sample = _make_sample()

        with patch("edge.src.main.normalize", return_value=sample) as mock_normalize:
            await _poll_once(
                poller=components["poller"],
                spool=components["spool"],
                device_id="sungrow-test",
                health=None,
            )

        # Poller was called
        components["poller"].poll.assert_awaited_once()
        # Normalizer was called with the raw data
        mock_normalize.assert_called_once()
        call_args = mock_normalize.call_args
        assert call_args.args[0] == _FAKE_RAW
        assert call_args.kwargs["device_id"] == "sungrow-test"
        # Spool enqueue was called with the JSON-serialized sample
        components["spool"].enqueue.assert_awaited_once()
        enqueued_json = components["spool"].enqueue.call_args.args[0]
        parsed = json.loads(enqueued_json)
        assert parsed["device_id"] == "sungrow-test"
        assert parsed["pv_power_w"] == 3500.0


# ---------------------------------------------------------------------------
# Test: normalizer returning None skips spool.enqueue() (AC7)
# ---------------------------------------------------------------------------


class TestNormalizerNoneSkipsEnqueue:
    """AC7: normalizer returning None does not enqueue to spool."""

    @pytest.mark.asyncio
    async def test_normalizer_none_skips_enqueue(self) -> None:
        """When normalize() returns None, spool.enqueue() is NOT called."""
        from edge.src.main import _poll_once

        components = _make_components()

        with patch("edge.src.main.normalize", return_value=None):
            await _poll_once(
                poller=components["poller"],
                spool=components["spool"],
                device_id="sungrow-test",
                health=None,
            )

        components["poller"].poll.assert_awaited_once()
        components["spool"].enqueue.assert_not_awaited()


# ---------------------------------------------------------------------------
# Test: poller returning None skips normalizer and spool
# ---------------------------------------------------------------------------


class TestPollerNoneSkipsNormalizerAndSpool:
    """When poller returns None, normalizer and spool are not called."""

    @pytest.mark.asyncio
    async def test_poller_none_skips_everything(self) -> None:
        """Poller returning None skips normalize() and spool.enqueue()."""
        from edge.src.main import _poll_once

        components = _make_components()
        components["poller"].poll = AsyncMock(return_value=None)

        with patch("edge.src.main.normalize") as mock_normalize:
            await _poll_once(
                poller=components["poller"],
                spool=components["spool"],
                device_id="sungrow-test",
                health=None,
            )

        mock_normalize.assert_not_called()
        components["spool"].enqueue.assert_not_awaited()


# ---------------------------------------------------------------------------
# Test: upload loop calls uploader.upload_batch(spool) (AC2)
# ---------------------------------------------------------------------------


class TestUploadLoopHappyPath:
    """AC2: upload loop calls uploader.upload_batch(spool)."""

    @pytest.mark.asyncio
    async def test_upload_once_calls_upload_batch(self) -> None:
        """Upload loop calls uploader.upload_batch with the spool."""
        from edge.src.main import _upload_once

        components = _make_components()

        await _upload_once(
            uploader=components["uploader"],
            spool=components["spool"],
        )

        components["uploader"].upload_batch.assert_awaited_once_with(
            components["spool"]
        )


# ---------------------------------------------------------------------------
# Test: empty spool (upload_batch returns False) just waits
# ---------------------------------------------------------------------------


class TestUploadEmptySpool:
    """When spool is empty, upload_batch returns False and loop continues."""

    @pytest.mark.asyncio
    async def test_upload_empty_spool_returns_false(self) -> None:
        """upload_batch returning False does not cause errors."""
        from edge.src.main import _upload_once

        components = _make_components()
        components["uploader"].upload_batch = AsyncMock(return_value=False)

        # Should not raise
        result = await _upload_once(
            uploader=components["uploader"],
            spool=components["spool"],
        )

        # upload_batch was called, returned False, no crash
        components["uploader"].upload_batch.assert_awaited_once()
        assert result is False


# ---------------------------------------------------------------------------
# Test: shutdown signal cancels loops gracefully (AC4)
# ---------------------------------------------------------------------------


class TestGracefulShutdown:
    """AC4: Graceful shutdown on SIGTERM/SIGINT."""

    @pytest.mark.asyncio
    async def test_shutdown_stops_loops(self) -> None:
        """Sending shutdown event causes run_loops to exit."""
        from edge.src.main import run_loops

        components = _make_components()
        shutdown_event = asyncio.Event()

        # Make poll slow enough that we can trigger shutdown
        async def slow_poll() -> dict[str, list[int]]:
            await asyncio.sleep(0.05)
            return _FAKE_RAW

        components["poller"].poll = AsyncMock(side_effect=slow_poll)

        sample = _make_sample()

        with patch("edge.src.main.normalize", return_value=sample):
            # Trigger shutdown after a brief delay
            async def _trigger_shutdown() -> None:
                await asyncio.sleep(0.1)
                shutdown_event.set()

            task = asyncio.create_task(
                run_loops(
                    poller=components["poller"],
                    spool=components["spool"],
                    uploader=components["uploader"],
                    device_id="sungrow-test",
                    poll_interval_s=0.05,
                    upload_interval_s=0.05,
                    shutdown_event=shutdown_event,
                    health=None,
                )
            )
            trigger = asyncio.create_task(_trigger_shutdown())

            # Should complete within a reasonable time
            await asyncio.wait_for(asyncio.gather(task, trigger), timeout=5.0)

    @pytest.mark.asyncio
    async def test_shutdown_attempts_final_upload(self) -> None:
        """On shutdown, a final upload flush is attempted."""
        from edge.src.main import run_loops

        components = _make_components()
        shutdown_event = asyncio.Event()

        sample = _make_sample()

        with patch("edge.src.main.normalize", return_value=sample):

            async def _trigger_shutdown() -> None:
                await asyncio.sleep(0.1)
                shutdown_event.set()

            task = asyncio.create_task(
                run_loops(
                    poller=components["poller"],
                    spool=components["spool"],
                    uploader=components["uploader"],
                    device_id="sungrow-test",
                    poll_interval_s=0.05,
                    upload_interval_s=0.05,
                    shutdown_event=shutdown_event,
                    health=None,
                )
            )
            trigger = asyncio.create_task(_trigger_shutdown())

            await asyncio.wait_for(asyncio.gather(task, trigger), timeout=5.0)

        # upload_batch should have been called (during loop and/or final flush)
        assert components["uploader"].upload_batch.await_count >= 1


# ---------------------------------------------------------------------------
# Test: health file updated after poll (AC6)
# ---------------------------------------------------------------------------


class TestHealthFileUpdate:
    """AC6: Health file updated on each poll loop iteration."""

    @pytest.mark.asyncio
    async def test_health_file_written_after_poll(self, tmp_path: Path) -> None:
        """Health file is written with JSON after a successful poll."""
        from edge.src.health import HealthWriter
        from edge.src.main import _poll_once

        components = _make_components()
        components["spool"].count = AsyncMock(return_value=5)
        sample = _make_sample()
        health_path = tmp_path / "health.json"
        health = HealthWriter(health_path)

        with patch("edge.src.main.normalize", return_value=sample):
            await _poll_once(
                poller=components["poller"],
                spool=components["spool"],
                device_id="sungrow-test",
                health=health,
            )

        assert health_path.exists()
        health_data = json.loads(health_path.read_text())
        assert "last_poll_ts" in health_data
        assert health_data["spool_count"] == 5

    @pytest.mark.asyncio
    async def test_health_file_updated_even_on_poll_failure(
        self, tmp_path: Path
    ) -> None:
        """Health file is updated even when poller returns None."""
        from edge.src.health import HealthWriter
        from edge.src.main import _poll_once

        components = _make_components()
        components["poller"].poll = AsyncMock(return_value=None)
        components["spool"].count = AsyncMock(return_value=3)
        health_path = tmp_path / "health.json"
        health = HealthWriter(health_path)

        await _poll_once(
            poller=components["poller"],
            spool=components["spool"],
            device_id="sungrow-test",
            health=health,
        )

        assert health_path.exists()
        health_data = json.loads(health_path.read_text())
        assert "last_poll_ts" in health_data
        assert health_data["spool_count"] == 3


# ---------------------------------------------------------------------------
# Test: poll error doesn't crash the loop
# ---------------------------------------------------------------------------


class TestPollErrorResilience:
    """Poll errors do not crash the poll loop."""

    @pytest.mark.asyncio
    async def test_poll_exception_does_not_crash(self) -> None:
        """An exception in poller.poll() is caught, loop continues."""
        from edge.src.main import _poll_once

        components = _make_components()
        components["poller"].poll = AsyncMock(
            side_effect=RuntimeError("Modbus connection lost")
        )

        # Should not raise
        await _poll_once(
            poller=components["poller"],
            spool=components["spool"],
            device_id="sungrow-test",
            health=None,
        )

        # Spool enqueue should NOT have been called
        components["spool"].enqueue.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_enqueue_exception_does_not_crash(self) -> None:
        """An exception in spool.enqueue() is caught, loop continues."""
        from edge.src.main import _poll_once

        components = _make_components()
        components["spool"].enqueue = AsyncMock(
            side_effect=RuntimeError("SQLite write error")
        )
        sample = _make_sample()

        with patch("edge.src.main.normalize", return_value=sample):
            # Should not raise
            await _poll_once(
                poller=components["poller"],
                spool=components["spool"],
                device_id="sungrow-test",
                health=None,
            )


# ---------------------------------------------------------------------------
# Test: upload error doesn't crash the loop
# ---------------------------------------------------------------------------


class TestUploadErrorResilience:
    """Upload errors do not crash the upload loop."""

    @pytest.mark.asyncio
    async def test_upload_exception_does_not_crash(self) -> None:
        """An exception in upload_batch() is caught, loop continues."""
        from edge.src.main import _upload_once

        components = _make_components()
        components["uploader"].upload_batch = AsyncMock(
            side_effect=RuntimeError("Network error")
        )

        # Should not raise
        await _upload_once(
            uploader=components["uploader"],
            spool=components["spool"],
        )


# ---------------------------------------------------------------------------
# Test: startup logs config summary without secrets (AC5)
# ---------------------------------------------------------------------------


class TestStartupLogging:
    """AC5: Structured JSON logging for startup with no secrets."""

    def test_log_config_summary_contains_host(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Startup log includes sungrow_host."""
        from edge.src.main import log_config_summary

        settings = _make_settings()

        with caplog.at_level(logging.INFO, logger="edge.src.main"):
            log_config_summary(settings)

        full_log = caplog.text
        assert "192.168.1.100" in full_log

    def test_log_config_summary_does_not_contain_token(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Startup log does NOT include the VPS device token."""
        from edge.src.main import log_config_summary

        settings = _make_settings()

        with caplog.at_level(logging.INFO, logger="edge.src.main"):
            log_config_summary(settings)

        full_log = caplog.text
        assert "secret-token-abc" not in full_log

    def test_log_config_summary_contains_intervals(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Startup log includes poll and upload intervals."""
        from edge.src.main import log_config_summary

        settings = _make_settings()

        with caplog.at_level(logging.INFO, logger="edge.src.main"):
            log_config_summary(settings)

        full_log = caplog.text
        assert "5" in full_log  # poll_interval_s
        assert "10" in full_log  # upload_interval_s


# ---------------------------------------------------------------------------
# Test: full integration of poll loop with multiple iterations
# ---------------------------------------------------------------------------


class TestPollLoopMultipleIterations:
    """Poll loop runs multiple iterations before shutdown."""

    @pytest.mark.asyncio
    async def test_poll_loop_runs_multiple_times(self) -> None:
        """Poll loop executes multiple poll cycles before shutdown."""
        from edge.src.main import _poll_loop

        components = _make_components()
        shutdown_event = asyncio.Event()
        call_count = 0
        sample = _make_sample()

        async def counting_poll() -> dict[str, list[int]]:
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                shutdown_event.set()
            return _FAKE_RAW

        components["poller"].poll = AsyncMock(side_effect=counting_poll)

        with patch("edge.src.main.normalize", return_value=sample):
            await asyncio.wait_for(
                _poll_loop(
                    poller=components["poller"],
                    spool=components["spool"],
                    device_id="sungrow-test",
                    poll_interval_s=0.01,
                    shutdown_event=shutdown_event,
                    health=None,
                ),
                timeout=5.0,
            )

        assert call_count >= 3


# ---------------------------------------------------------------------------
# Test: full integration of upload loop with multiple iterations
# ---------------------------------------------------------------------------


class TestUploadLoopMultipleIterations:
    """Upload loop runs multiple iterations before shutdown."""

    @pytest.mark.asyncio
    async def test_upload_loop_runs_multiple_times(self) -> None:
        """Upload loop executes multiple upload cycles before shutdown."""
        from edge.src.main import _upload_loop

        components = _make_components()
        shutdown_event = asyncio.Event()
        call_count = 0

        async def counting_upload(spool: object) -> bool:
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                shutdown_event.set()
            return True

        components["uploader"].upload_batch = AsyncMock(side_effect=counting_upload)

        await asyncio.wait_for(
            _upload_loop(
                uploader=components["uploader"],
                spool=components["spool"],
                upload_interval_s=0.01,
                shutdown_event=shutdown_event,
            ),
            timeout=5.0,
        )

        assert call_count >= 3
