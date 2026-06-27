"""
Tests for the Home Assistant MQTT publisher and its main-loop integration.

Verifies discovery-once semantics, reconnect re-announce, discovery payload
shape, and that the publisher is wired into the poll loop as a best-effort
fan-out that never breaks the spool/VPS path.

CHANGELOG:
- 2026-06-27: Initial creation (HA-only MQTT branch)

TODO:
- None
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from edge.src.models import SungrowSample
from edge.src.mqtt_publisher import _SENSORS, MqttPublisher, _slugify

_STATE_TOPIC = "sungrow_edge/sungrow_223/state"
_AVAIL_TOPIC = "sungrow_edge/sungrow_223/availability"


class FakeClient:
    """Minimal stand-in for a paho-mqtt client; records publish() calls."""

    def __init__(self) -> None:
        self.published: list[tuple[str, Any, int, bool]] = []
        self.will: tuple[str, Any, bool] | None = None
        self.username: str | None = None
        self.started = False
        self.stopped = False
        self.disconnected = False

    def will_set(self, topic: str, payload: Any = None, qos: int = 0,
                 retain: bool = False) -> None:
        self.will = (topic, payload, retain)

    def username_pw_set(self, username: str, password: Any = None) -> None:
        self.username = username

    def publish(self, topic: str, payload: Any = None, qos: int = 0,
                retain: bool = False) -> None:
        self.published.append((topic, payload, qos, retain))

    def connect_async(self, *args: Any, **kwargs: Any) -> None:
        self.started = True

    def loop_start(self) -> None:
        self.started = True

    def loop_stop(self) -> None:
        self.stopped = True

    def disconnect(self) -> None:
        self.disconnected = True

    # convenience
    def topics(self) -> list[str]:
        return [t for t, _, _, _ in self.published]

    def discovery_topics(self) -> list[str]:
        return [t for t in self.topics() if t.startswith("homeassistant/sensor/")]


def _sample() -> SungrowSample:
    return SungrowSample(
        device_id="sungrow-223",
        ts=datetime(2026, 6, 27, 12, 0, 0, tzinfo=UTC),
        pv_power_w=3500.0,
        pv_daily_kwh=12.5,
        battery_power_w=1000.0,
        battery_soc_pct=72.5,
        battery_temp_c=25.0,
        load_power_w=2000.0,
        export_power_w=500.0,
        pv_total_kwh=9918.0,
        battery_discharge_total_kwh=2574.1,
    )


def _publisher(client: FakeClient) -> MqttPublisher:
    return MqttPublisher(
        host="core-mosquitto", port=1883, device_id="sungrow-223", client=client
    )


class TestSlugify:
    def test_slugify_replaces_non_alnum(self) -> None:
        assert _slugify("sungrow-223") == "sungrow_223"

    def test_slugify_empty_falls_back(self) -> None:
        assert _slugify("---") == "sungrow"


class TestDiscovery:
    @pytest.mark.asyncio
    async def test_first_publish_sends_discovery_availability_and_state(self) -> None:
        client = FakeClient()
        pub = _publisher(client)

        await pub.publish(_sample())

        # One discovery config per advertised sensor.
        assert len(client.discovery_topics()) == len(_SENSORS)
        # Availability online + a state message.
        assert _AVAIL_TOPIC in client.topics()
        assert _STATE_TOPIC in client.topics()

    @pytest.mark.asyncio
    async def test_second_publish_sends_only_state(self) -> None:
        client = FakeClient()
        pub = _publisher(client)

        await pub.publish(_sample())
        client.published.clear()
        await pub.publish(_sample())

        assert client.topics() == [_STATE_TOPIC]
        assert client.discovery_topics() == []

    @pytest.mark.asyncio
    async def test_reconnect_reannounces_discovery(self) -> None:
        client = FakeClient()
        pub = _publisher(client)

        await pub.publish(_sample())
        pub._on_connect()  # simulate a broker reconnect
        client.published.clear()
        await pub.publish(_sample())

        assert len(client.discovery_topics()) == len(_SENSORS)

    def test_discovery_payload_shape_for_energy_sensor(self) -> None:
        client = FakeClient()
        pub = _publisher(client)

        pub._publish_discovery()

        payloads = {
            t: p for t, p, _, _ in client.published
            if t.endswith("/pv_total_kwh/config")
        }
        assert payloads, "pv_total_kwh discovery config was not published"
        cfg = json.loads(next(iter(payloads.values())))
        assert cfg["state_topic"] == _STATE_TOPIC
        assert cfg["value_template"] == "{{ value_json.pv_total_kwh }}"
        assert cfg["device_class"] == "energy"
        assert cfg["state_class"] == "total_increasing"
        assert cfg["unit_of_measurement"] == "kWh"
        assert cfg["availability_topic"] == _AVAIL_TOPIC
        assert cfg["device"]["identifiers"] == ["sungrow_edge_sungrow_223"]

    def test_discovery_configs_are_retained(self) -> None:
        client = FakeClient()
        pub = _publisher(client)
        pub._publish_discovery()
        for topic, _payload, _qos, retain in client.published:
            if topic.startswith("homeassistant/sensor/"):
                assert retain is True

    @pytest.mark.asyncio
    async def test_state_payload_is_sample_json(self) -> None:
        client = FakeClient()
        pub = _publisher(client)
        sample = _sample()

        await pub.publish(sample)

        state = [p for t, p, _, _ in client.published if t == _STATE_TOPIC]
        assert state, "no state message published"
        parsed = json.loads(state[0])
        assert parsed["pv_power_w"] == 3500.0
        assert parsed["pv_total_kwh"] == 9918.0
        assert parsed["battery_discharge_total_kwh"] == 2574.1
        # Unavailable-on-this-firmware field still serialised (null).
        assert parsed["battery_charge_total_kwh"] is None

    def test_build_client_sets_lwt_auth_and_callback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The default (non-injected) client path wires LWT, auth, callback."""
        import sys
        import types

        captured: dict[str, Any] = {}

        class _FakeClient:
            def __init__(self, version: Any, client_id: str | None = None) -> None:
                captured["client_id"] = client_id
                self.will: Any = None
                self.auth: Any = None
                self.on_connect: Any = None

            def username_pw_set(self, username: str, password: Any = None) -> None:
                self.auth = (username, password)

            def will_set(self, topic: str, payload: Any = None, qos: int = 0,
                         retain: bool = False) -> None:
                self.will = (topic, payload, qos, retain)

        class _CB:
            VERSION2 = 2

        client_mod = types.ModuleType("paho.mqtt.client")
        client_mod.Client = _FakeClient  # type: ignore[attr-defined]
        client_mod.CallbackAPIVersion = _CB  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "paho", types.ModuleType("paho"))
        monkeypatch.setitem(sys.modules, "paho.mqtt", types.ModuleType("paho.mqtt"))
        monkeypatch.setitem(sys.modules, "paho.mqtt.client", client_mod)

        pub = MqttPublisher(
            host="h", port=1883, username="u", password="p",
            device_id="sungrow-223",
        )
        client = pub._client
        assert client.auth == ("u", "p")
        assert client.will == (_AVAIL_TOPIC, "offline", 1, True)
        assert client.on_connect is not None
        assert captured["client_id"] == "sungrow-edge-sungrow_223"


class TestStop:
    def test_stop_marks_offline_and_stops_loop(self) -> None:
        client = FakeClient()
        pub = _publisher(client)
        pub.stop()
        assert (_AVAIL_TOPIC, "offline", 1, True) in client.published
        assert client.stopped is True
        assert client.disconnected is True


# ---------------------------------------------------------------------------
# Main-loop integration: best-effort, isolated from the VPS path
# ---------------------------------------------------------------------------


def _components() -> dict[str, AsyncMock]:
    poller = AsyncMock()
    poller.poll = AsyncMock(return_value={"total_dc_power": [0, 1000]})
    spool = AsyncMock()
    spool.enqueue = AsyncMock()
    spool.count = AsyncMock(return_value=0)
    return {"poller": poller, "spool": spool}


class TestPollOncePublishes:
    @pytest.mark.asyncio
    async def test_poll_once_publishes_when_publisher_present(self) -> None:
        from edge.src.main import _poll_once

        comp = _components()
        publisher = AsyncMock()
        with patch("edge.src.main.normalize", return_value=_sample()):
            await _poll_once(
                poller=comp["poller"],
                spool=comp["spool"],
                device_id="sungrow-223",
                health=None,
                publisher=publisher,
            )
        publisher.publish.assert_awaited_once()
        comp["spool"].enqueue.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_publisher_failure_does_not_break_enqueue(self) -> None:
        from edge.src.main import _poll_once

        comp = _components()
        publisher = AsyncMock()
        publisher.publish = AsyncMock(side_effect=RuntimeError("mqtt down"))
        with patch("edge.src.main.normalize", return_value=_sample()):
            # Must not raise despite the publish failure.
            await _poll_once(
                poller=comp["poller"],
                spool=comp["spool"],
                device_id="sungrow-223",
                health=None,
                publisher=publisher,
            )
        # The VPS spool enqueue still happened.
        comp["spool"].enqueue.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_publisher_is_a_noop(self) -> None:
        from edge.src.main import _poll_once

        comp = _components()
        with patch("edge.src.main.normalize", return_value=_sample()):
            await _poll_once(
                poller=comp["poller"],
                spool=comp["spool"],
                device_id="sungrow-223",
                health=None,
            )
        comp["spool"].enqueue.assert_awaited_once()
