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
- 2026-09-05: Bound SOC age to three polls and observe before I/O (WIM-ACTION-39).
- 2026-07-18: Wire battery controller (opt-in): SOC observation in the poll
  path, deadman watchdog task, control API task, revert-on-shutdown
- 2026-02-14: Add periodic raw register snapshot logging for field diagnostics
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
    from edge.src.control import SungrowController
    from edge.src.mqtt_publisher import MqttPublisher
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
        "spool_path=%s, device_id=%s, vps_base_url=%s, "
        "raw_debug_enabled=%s, raw_debug_every_n_polls=%s, "
        "mqtt_enabled=%s, mqtt_host=%s, mqtt_port=%s",
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
        settings.raw_debug_enabled,  # type: ignore[union-attr]
        settings.raw_debug_every_n_polls,  # type: ignore[union-attr]
        settings.mqtt_enabled,  # type: ignore[union-attr]
        settings.mqtt_host,  # type: ignore[union-attr]
        settings.mqtt_port,  # type: ignore[union-attr]
    )


def _log_raw_snapshot(raw: dict[str, list[int]]) -> None:
    """Log a compact raw register snapshot for debugging field decoding."""
    keys = (
        "total_dc_power",
        "daily_pv_generation",
        "battery_power",
        "battery_soc",
        "battery_temperature",
        "load_power",
        "grid_power",
        "export_power",
    )
    snapshot = {k: raw.get(k) for k in keys if k in raw}
    logger.warning("Raw register snapshot: %s", snapshot)


# ---------------------------------------------------------------------------
# Single-iteration functions (easily testable)
# ---------------------------------------------------------------------------


async def _poll_once(
    *,
    poller: Poller,
    spool: Spool,
    device_id: str,
    health: HealthWriter | None,
    publisher: MqttPublisher | None = None,
    controller: SungrowController | None = None,
    raw_debug_enabled: bool = False,
    raw_debug_every_n_polls: int = 60,
    raw_debug_state: list[int] | None = None,
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
            if raw_debug_enabled and raw_debug_state is not None:
                raw_debug_state[0] += 1
                if raw_debug_state[0] % raw_debug_every_n_polls == 0:
                    _log_raw_snapshot(raw)

            ts = datetime.now(tz=UTC)
            sample = normalize(raw, device_id=device_id, ts=ts)

            if sample is not None:
                # Timestamp SOC before downstream awaits can delay delivery.
                # A controller failure must not affect telemetry persistence.
                if controller is not None:
                    try:
                        controller.observe(sample)
                    except Exception:
                        logger.warning(
                            "Controller observe failed (non-fatal)", exc_info=True
                        )
                await spool.enqueue(sample.model_dump_json())
                logger.info("Poll success: enqueued sample for device=%s", device_id)
                # Best-effort HA fan-out. Isolated so an MQTT failure can never
                # affect the spool/VPS upload path (the sample is already
                # enqueued above).
                if publisher is not None:
                    try:
                        await publisher.publish(sample)
                    except Exception:
                        logger.warning(
                            "MQTT publish failed (non-fatal; VPS path unaffected)",
                            exc_info=True,
                        )
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
    publisher: MqttPublisher | None = None,
    controller: SungrowController | None = None,
    raw_debug_enabled: bool = False,
    raw_debug_every_n_polls: int = 60,
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
    raw_debug_state = [0]
    while not shutdown_event.is_set():
        await _poll_once(
            poller=poller,
            spool=spool,
            device_id=device_id,
            health=health,
            publisher=publisher,
            controller=controller,
            raw_debug_enabled=raw_debug_enabled,
            raw_debug_every_n_polls=raw_debug_every_n_polls,
            raw_debug_state=raw_debug_state,
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
    publisher: MqttPublisher | None = None,
    controller: SungrowController | None = None,
    raw_debug_enabled: bool = False,
    raw_debug_every_n_polls: int = 60,
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

    tasks = [
        _poll_loop(
            poller=poller,
            spool=spool,
            device_id=device_id,
            poll_interval_s=poll_interval_s,
            shutdown_event=shutdown_event,
            health=health,
            publisher=publisher,
            controller=controller,
            raw_debug_enabled=raw_debug_enabled,
            raw_debug_every_n_polls=raw_debug_every_n_polls,
        ),
        _upload_loop(
            uploader=uploader,
            spool=spool,
            upload_interval_s=upload_interval_s,
            shutdown_event=shutdown_event,
            health=health,
        ),
    ]
    if controller is not None:
        tasks.append(controller.watchdog_loop(shutdown_event))

    await asyncio.gather(*tasks)

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

    # One lock serializes ALL Modbus access (poller reads + controller
    # writes) — the WiNet-S reliably serves only one client at a time.
    modbus_lock = asyncio.Lock()

    poller = Poller(
        host=settings.sungrow_host,
        port=settings.sungrow_port,
        slave_id=settings.sungrow_slave_id,
        inter_register_delay_ms=settings.inter_register_delay_ms,
        modbus_lock=modbus_lock,
    )

    uploader = Uploader(
        vps_base_url=settings.vps_base_url,
        vps_device_token=settings.vps_device_token,
        batch_size=settings.batch_size,
    )

    health = HealthWriter("/data/health.json")

    # Optional HA local-MQTT fan-out (off unless mqtt_enabled). Built and
    # started here; passed into the poll loop for best-effort publishing.
    publisher: MqttPublisher | None = None
    if settings.mqtt_enabled:
        from edge.src.mqtt_publisher import MqttPublisher

        publisher = MqttPublisher(
            host=settings.mqtt_host,
            port=settings.mqtt_port,
            username=settings.mqtt_username,
            password=settings.mqtt_password,
            discovery_prefix=settings.mqtt_discovery_prefix,
            base_topic=settings.mqtt_base_topic,
            device_id=settings.device_id,
        )
        publisher.start()

    # Optional battery control (off unless control_enabled). The controller
    # shares the modbus lock with the poller and reverts the inverter to
    # self-consumption on TTL expiry, SOC breach, and daemon shutdown.
    controller: SungrowController | None = None
    api_task = None
    if settings.control_enabled:
        from edge.src.control import ControlLimits, SungrowController
        from edge.src.control_api import build_app, serve_api

        controller = SungrowController(
            host=settings.sungrow_host,
            port=settings.sungrow_port,
            slave_id=settings.sungrow_slave_id,
            limits=ControlLimits(
                max_charge_w=settings.control_max_charge_w,
                max_discharge_w=settings.control_max_discharge_w,
                min_soc_pct=settings.control_min_soc_pct,
                max_soc_pct=settings.control_max_soc_pct,
                max_ttl_s=settings.control_max_ttl_s,
            ),
            dry_run=settings.control_dry_run,
            state_path=settings.control_state_path,
            audit_path=settings.control_audit_path,
            modbus_lock=modbus_lock,
            soc_max_age_s=3 * settings.poll_interval_s,
        )
        await controller.reconcile_on_startup()
        app = build_app(controller, token=settings.control_api_token)
        api_task = asyncio.get_running_loop().create_task(
            serve_api(
                app,
                port=settings.control_api_port,
                shutdown_event=shutdown_event,
            )
        )
        logger.info(
            "Battery control enabled (dry_run=%s, api_port=%s)",
            settings.control_dry_run,
            settings.control_api_port,
        )

    try:
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
                publisher=publisher,
                controller=controller,
                raw_debug_enabled=settings.raw_debug_enabled,
                raw_debug_every_n_polls=settings.raw_debug_every_n_polls,
            )
    finally:
        if controller is not None:
            await controller.on_shutdown()
        if api_task is not None:
            await asyncio.wait([api_task], timeout=5)
            api_task.cancel()
        if publisher is not None:
            publisher.stop()


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
