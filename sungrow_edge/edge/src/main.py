"""
Edge daemon main loop for Sungrow-to-VPS solar telemetry pipeline.

Runs two concurrent asyncio loops:
1. **Poll loop**: reads Modbus registers via the Poller, normalizes them into
   a SungrowSample, and enqueues the JSON payload into the local SQLite spool.
2. **Upload loop**: calls uploader.upload_batch(spool) to flush buffered
   samples to the VPS ingest endpoint over HTTPS.

Both loops are resilient: an exception in one iteration is logged and does not
crash the loop or affect the other loop. Graceful shutdown on SIGTERM/SIGINT
sets a shared asyncio.Event, allowing both loops to finish their current
iteration and then attempt one final upload flush before exiting.

Structured JSON logging is used for all events. A HealthWriter instance
tracks last_poll_ts, last_upload_ts, and spool_count, writing a JSON health
file after each state change.

CHANGELOG:
- 2026-02-14: Replace inline health writer with HealthWriter (STORY-015)
- 2026-02-14: Initial creation (STORY-014)

TODO:
- None
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import signal
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from edge.src.health import HealthWriter
from edge.src.normalizer import normalize

if TYPE_CHECKING:
    from edge.src.poller import Poller
    from edge.src.spool import Spool
    from edge.src.uploader import Uploader

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured JSON logging setup
# ---------------------------------------------------------------------------


def configure_logging() -> None:
    """Configure structured JSON logging for the edge daemon.

    Sets up the root logger with a JSON-formatted handler writing to stderr.
    """

    class _JsonFormatter(logging.Formatter):
        """Minimal JSON log formatter."""

        def format(self, record: logging.LogRecord) -> str:
            log_entry = {
                "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "msg": record.getMessage(),
            }
            if record.exc_info and record.exc_info[1] is not None:
                log_entry["exception"] = self.formatException(record.exc_info)
            return json.dumps(log_entry)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Startup config logging
# ---------------------------------------------------------------------------


def log_config_summary(settings: object) -> None:
    """Log a config summary at startup, excluding secrets.

    Logs host, port, slave_id, intervals, batch_size, spool_path, and
    device_id but deliberately omits vps_device_token.

    Args:
        settings: An EdgeSettings instance (or any object with the same attrs).
    """
    logger.info(
        "Edge daemon starting with config: "
        "sungrow_host=%s, sungrow_port=%s, sungrow_slave_id=%s, "
        "poll_interval_s=%s, upload_interval_s=%s, "
        "inter_register_delay_ms=%s, batch_size=%s, "
        "spool_path=%s, device_id=%s, vps_base_url=%s",
        settings.sungrow_host,  # type: ignore[union-attr]
        settings.sungrow_port,  # type: ignore[union-attr]
        settings.sungrow_slave_id,  # type: ignore[union-attr]
        settings.poll_interval_s,  # type: ignore[union-attr]
        settings.upload_interval_s,  # type: ignore[union-attr]
        settings.inter_register_delay_ms,  # type: ignore[union-attr]
        settings.batch_size,  # type: ignore[union-attr]
        settings.spool_path,  # type: ignore[union-attr]
        settings.device_id,  # type: ignore[union-attr]
        settings.vps_base_url,  # type: ignore[union-attr]
    )


# ---------------------------------------------------------------------------
# Single-iteration functions (easily testable)
# ---------------------------------------------------------------------------


async def _poll_once(
    *,
    poller: Poller,
    spool: Spool,
    device_id: str,
    health: HealthWriter | None,
) -> None:
    """Execute a single poll-normalize-enqueue cycle.

    Catches all exceptions so that the caller's loop is never broken.
    After each poll attempt the health writer is updated with the current
    spool count and a fresh poll timestamp.

    Args:
        poller: The Modbus poller instance.
        spool: The local spool for buffering.
        device_id: Device identifier for the sample.
        health: HealthWriter instance, or None to skip health writes.
    """
    try:
        raw = await poller.poll()

        if raw is not None:
            ts = datetime.now(tz=UTC)
            sample = normalize(raw, device_id=device_id, ts=ts)

            if sample is not None:
                await spool.enqueue(sample.model_dump_json())
                logger.info("Poll success: enqueued sample for device=%s", device_id)
            else:
                logger.warning("Normalizer returned None, skipping enqueue")
        else:
            logger.warning("Poller returned None, skipping normalize and enqueue")
    except Exception:
        logger.error("Poll cycle error", exc_info=True)

    # Update health file after every poll attempt (success or failure)
    if health is not None:
        try:
            count = await spool.count()
            health.set_spool_count(count)
            health.record_poll()
        except Exception:
            logger.warning("Failed to write health file", exc_info=True)


async def _upload_once(
    *,
    uploader: Uploader,
    spool: Spool,
    health: HealthWriter | None = None,
) -> bool:
    """Execute a single upload cycle.

    Catches all exceptions so that the caller's loop is never broken.
    On a successful upload the health writer records an upload timestamp.

    Args:
        uploader: The HTTPS batch uploader.
        spool: The local spool to upload from.
        health: HealthWriter instance, or None to skip health writes.

    Returns:
        True if upload succeeded, False otherwise.
    """
    try:
        result = await uploader.upload_batch(spool)
        if result:
            logger.info("Upload success")
            if health is not None:
                health.record_upload()
        else:
            logger.debug("Upload returned False (spool may be empty)")
        return result
    except Exception:
        logger.error("Upload cycle error", exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Loop runners
# ---------------------------------------------------------------------------


async def _poll_loop(
    *,
    poller: Poller,
    spool: Spool,
    device_id: str,
    poll_interval_s: float,
    shutdown_event: asyncio.Event,
    health: HealthWriter | None,
) -> None:
    """Run the poll loop until shutdown_event is set.

    Executes _poll_once, then sleeps for poll_interval_s, checking the
    shutdown event between iterations.

    Args:
        poller: The Modbus poller instance.
        spool: The local spool for buffering.
        device_id: Device identifier for samples.
        poll_interval_s: Seconds between poll cycles.
        shutdown_event: Event to signal graceful shutdown.
        health: HealthWriter instance, or None to skip health writes.
    """
    logger.info("Poll loop started (interval=%ss)", poll_interval_s)
    while not shutdown_event.is_set():
        await _poll_once(
            poller=poller,
            spool=spool,
            device_id=device_id,
            health=health,
        )
        # Use wait with timeout so we can check shutdown between sleeps
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(
                shutdown_event.wait(),
                timeout=poll_interval_s,
            )
    logger.info("Poll loop stopped")


async def _upload_loop(
    *,
    uploader: Uploader,
    spool: Spool,
    upload_interval_s: float,
    shutdown_event: asyncio.Event,
    health: HealthWriter | None = None,
) -> None:
    """Run the upload loop until shutdown_event is set.

    Executes _upload_once, then sleeps for upload_interval_s, checking the
    shutdown event between iterations.

    Args:
        uploader: The HTTPS batch uploader.
        spool: The local spool to upload from.
        upload_interval_s: Seconds between upload cycles.
        shutdown_event: Event to signal graceful shutdown.
        health: HealthWriter instance, or None to skip health writes.
    """
    logger.info("Upload loop started (interval=%ss)", upload_interval_s)
    while not shutdown_event.is_set():
        await _upload_once(uploader=uploader, spool=spool, health=health)
        # Use wait with timeout so we can check shutdown between sleeps
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(
                shutdown_event.wait(),
                timeout=upload_interval_s,
            )
    logger.info("Upload loop stopped")


# ---------------------------------------------------------------------------
# Concurrent runner with graceful shutdown
# ---------------------------------------------------------------------------


async def run_loops(
    *,
    poller: Poller,
    spool: Spool,
    uploader: Uploader,
    device_id: str,
    poll_interval_s: float,
    upload_interval_s: float,
    shutdown_event: asyncio.Event,
    health: HealthWriter | None = None,
) -> None:
    """Run poll and upload loops concurrently until shutdown.

    Both loops run as independent asyncio tasks via asyncio.gather().
    When the shutdown_event is set, both loops finish their current iteration,
    then a final upload flush is attempted before returning.

    Args:
        poller: The Modbus poller instance.
        spool: The local spool for buffering.
        uploader: The HTTPS batch uploader.
        device_id: Device identifier for samples.
        poll_interval_s: Seconds between poll cycles.
        upload_interval_s: Seconds between upload cycles.
        shutdown_event: Event to signal graceful shutdown.
        health: HealthWriter instance, or None to skip health writes.
    """
    logger.info("Starting concurrent poll and upload loops")

    await asyncio.gather(
        _poll_loop(
            poller=poller,
            spool=spool,
            device_id=device_id,
            poll_interval_s=poll_interval_s,
            shutdown_event=shutdown_event,
            health=health,
        ),
        _upload_loop(
            uploader=uploader,
            spool=spool,
            upload_interval_s=upload_interval_s,
            shutdown_event=shutdown_event,
            health=health,
        ),
    )

    # Final upload flush after shutdown
    logger.info("Attempting final upload flush before exit")
    await _upload_once(uploader=uploader, spool=spool, health=health)
    logger.info("Shutdown complete")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


async def async_main() -> None:
    """Async entrypoint: load config, build components, run loops.

    Sets up SIGTERM/SIGINT handlers to trigger graceful shutdown.
    """
    configure_logging()

    from edge.src.config import EdgeSettings
    from edge.src.poller import Poller
    from edge.src.spool import Spool
    from edge.src.uploader import Uploader

    settings = EdgeSettings()
    log_config_summary(settings)

    shutdown_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda: _handle_signal(shutdown_event),
        )

    poller = Poller(
        host=settings.sungrow_host,
        port=settings.sungrow_port,
        slave_id=settings.sungrow_slave_id,
        inter_register_delay_ms=settings.inter_register_delay_ms,
    )

    uploader = Uploader(
        vps_base_url=settings.vps_base_url,
        vps_device_token=settings.vps_device_token,
        batch_size=settings.batch_size,
    )

    health = HealthWriter("/data/health.json")

    async with Spool(settings.spool_path) as spool:
        await run_loops(
            poller=poller,
            spool=spool,
            uploader=uploader,
            device_id=settings.device_id,
            poll_interval_s=settings.poll_interval_s,
            upload_interval_s=settings.upload_interval_s,
            shutdown_event=shutdown_event,
            health=health,
        )


def _handle_signal(shutdown_event: asyncio.Event) -> None:
    """Handle SIGTERM/SIGINT by setting the shutdown event.

    Args:
        shutdown_event: The event to set for graceful shutdown.
    """
    logger.info("Received shutdown signal, initiating graceful shutdown")
    shutdown_event.set()


def main() -> None:
    """Synchronous entrypoint for the edge daemon."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
