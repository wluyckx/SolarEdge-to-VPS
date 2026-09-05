"""
Best-effort local MQTT publisher for Home Assistant.

Publishes each normalized :class:`~edge.src.models.SungrowSample` to a local
MQTT broker (the HA ``core-mosquitto`` add-on) using Home Assistant MQTT
*discovery*, so HA auto-creates clean sensors with correct ``device_class`` /
``state_class`` for the Energy Dashboard.

Design principles (HC: the VPS path must never be affected):
- This is a **parallel fan-out** of data the daemon already has in hand from a
  single Modbus poll. It opens NO additional Modbus connection.
- It is **opt-in** (``mqtt_enabled``, default false) and **best-effort**: every
  publish is non-blocking (paho ``loop_start`` background thread with automatic
  reconnect) and the caller wraps ``publish`` so any failure is swallowed and
  never breaks the spool/upload pipeline.
- ``paho-mqtt`` is imported lazily so the module (and the test-suite) load
  without the dependency present; tests inject a fake client.

CHANGELOG:
- 2026-06-27: Initial creation (HA-only MQTT branch)

TODO:
- None
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from edge.src.models import SungrowSample

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sensor catalogue
#
# Each entry: (sample_field, friendly_name, device_class, unit, state_class).
# Only fields that are reliably available on the deployed SH4.0RS firmware are
# advertised. ``battery_charge_total_kwh`` is intentionally omitted: register
# 13027 reads 0 on this WiNet-S firmware (see registers.py), so advertising it
# would create a permanently-"unknown" HA entity. The model field is still
# published in the JSON state, so it auto-populates if a future register scan
# finds a working charge counter and adds it here.
# ---------------------------------------------------------------------------

_SENSORS: list[tuple[str, str, str | None, str | None, str | None]] = [
    ("pv_power_w", "PV Power", "power", "W", "measurement"),
    ("pv_total_kwh", "PV Energy Total", "energy", "kWh", "total_increasing"),
    ("pv_daily_kwh", "PV Energy Today", "energy", "kWh", "total_increasing"),
    ("battery_power_w", "Battery Power", "power", "W", "measurement"),
    ("battery_soc_pct", "Battery SOC", "battery", "%", "measurement"),
    ("battery_temp_c", "Battery Temperature", "temperature", "°C", "measurement"),
    (
        "battery_discharge_total_kwh",
        "Battery Discharge Total",
        "energy",
        "kWh",
        "total_increasing",
    ),
    ("load_power_w", "Load Power", "power", "W", "measurement"),
    ("export_power_w", "Grid Export Power", "power", "W", "measurement"),
]


def _slugify(value: str) -> str:
    """Lowercase and reduce to ``[a-z0-9_]`` for use in topics / unique_ids."""
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "sungrow"


class MqttPublisher:
    """Publishes SungrowSample telemetry to HA via MQTT discovery.

    Args:
        host: MQTT broker hostname (default add-on broker ``core-mosquitto``).
        port: MQTT broker port.
        username: MQTT username (empty string = anonymous).
        password: MQTT password.
        discovery_prefix: HA MQTT discovery prefix (default ``homeassistant``).
        base_topic: Root topic for state/availability (default ``sungrow_edge``).
        device_id: Inverter device id; used for topic/unique_id namespacing and
            the HA device name.
        client: Optional pre-built paho client (used by tests). When omitted a
            real paho client is constructed lazily.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str = "",
        password: str = "",
        discovery_prefix: str = "homeassistant",
        base_topic: str = "sungrow_edge",
        device_id: str = "sungrow",
        client: Any | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._discovery_prefix = discovery_prefix.rstrip("/")
        self._device_id = device_id
        self._object_id = _slugify(device_id)
        base = f"{base_topic.rstrip('/')}/{self._object_id}"
        self._state_topic = f"{base}/state"
        self._availability_topic = f"{base}/availability"
        # Re-announce discovery on the next publish after every (re)connect so a
        # broker restart or a late connect never leaves HA without configs.
        self._discovery_sent = False
        self._client = (
            client if client is not None else self._build_client(username, password)
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _build_client(self, username: str, password: str) -> Any:
        """Construct a paho-mqtt client (imported lazily)."""
        import paho.mqtt.client as mqtt

        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"sungrow-edge-{self._object_id}",
        )
        if username:
            client.username_pw_set(username, password or None)
        # Last Will: mark offline if the daemon dies / disconnects ungracefully.
        client.will_set(self._availability_topic, payload="offline", qos=1, retain=True)
        client.on_connect = self._on_connect
        return client

    def _on_connect(self, *args: Any, **kwargs: Any) -> None:
        """Force discovery re-announce on each (re)connect."""
        self._discovery_sent = False
        logger.info("MQTT connected to %s:%s", self._host, self._port)

    def start(self) -> None:
        """Begin the background network loop with automatic reconnect.

        Best-effort: a failure here disables publishing but never raises.
        """
        try:
            self._client.connect_async(self._host, self._port)
            self._client.loop_start()
            logger.info(
                "MQTT publisher started: %s:%s state_topic=%s",
                self._host,
                self._port,
                self._state_topic,
            )
        except Exception:
            logger.warning(
                "MQTT publisher failed to start (publishing disabled)",
                exc_info=True,
            )

    def stop(self) -> None:
        """Mark offline and stop the network loop. Best-effort."""
        try:
            self._client.publish(
                self._availability_topic, "offline", qos=1, retain=True
            )
            self._client.loop_stop()
            self._client.disconnect()
        except Exception:
            logger.warning("MQTT publisher stop error", exc_info=True)

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    async def publish(self, sample: SungrowSample) -> None:
        """Publish one telemetry sample (and discovery on first call / reconnect).

        Non-blocking: paho ``publish`` hands off to the background loop thread.
        """
        if not self._discovery_sent:
            self._publish_discovery()
            self._client.publish(self._availability_topic, "online", qos=1, retain=True)
            self._discovery_sent = True

        self._client.publish(
            self._state_topic, sample.model_dump_json(), qos=0, retain=False
        )

    def _publish_discovery(self) -> None:
        """Publish retained HA MQTT-discovery configs for every advertised sensor."""
        device = {
            "identifiers": [f"sungrow_edge_{self._object_id}"],
            "name": f"Sungrow Edge ({self._device_id})",
            "manufacturer": "Sungrow",
            "model": "SH4.0RS",
        }
        for key, friendly, device_class, unit, state_class in _SENSORS:
            config: dict[str, Any] = {
                "name": friendly,
                "unique_id": f"sungrow_edge_{self._object_id}_{key}",
                "state_topic": self._state_topic,
                "value_template": f"{{{{ value_json.{key} }}}}",
                "availability_topic": self._availability_topic,
                "device": device,
            }
            if device_class is not None:
                config["device_class"] = device_class
            if unit is not None:
                config["unit_of_measurement"] = unit
            if state_class is not None:
                config["state_class"] = state_class
            topic = f"{self._discovery_prefix}/sensor/{self._object_id}/{key}/config"
            self._client.publish(topic, json.dumps(config), qos=1, retain=True)
        logger.info("Published HA MQTT discovery for %d sensors", len(_SENSORS))
