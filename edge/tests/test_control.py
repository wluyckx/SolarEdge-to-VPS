"""
Tests for the battery control module (SungrowController).

Verifies command validation, power clamping, SOC guardrails, the dry-run
invariant (no Modbus writes ever), the live write sequence and its rollback,
the TTL deadman watchdog, state persistence across restarts, startup
reconciliation of orphaned force mode, and the audit trail.

CHANGELOG:
- 2026-07-18: Initial creation -- TDD tests written first (battery-control AC1-AC5)

TODO:
- None
"""

from __future__ import annotations

import json

import pytest
from edge.src.control import (
    CMD_CHARGE,
    CMD_DISCHARGE,
    CMD_STOP,
    EMS_MODE_FORCED,
    EMS_MODE_SELF,
    REG_EMS_MODE,
    REG_FORCE_CMD,
    REG_FORCE_POWER,
    CommandRequest,
    ControlError,
    ControlLimits,
    SungrowController,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, *, error: bool = False, registers: list[int] | None = None):
        self._error = error
        self.registers = registers or []

    def isError(self) -> bool:  # noqa: N802 - pymodbus API
        return self._error


class FakeModbusClient:
    """Records writes; configurable failures and holding-register contents."""

    def __init__(self) -> None:
        self.writes: list[tuple[int, int]] = []
        self.holding: dict[int, int] = {}
        self.fail_connect = False
        self.fail_writes_at: set[int] = set()  # fail the Nth write (0-based)
        self.connect_count = 0

    async def connect(self) -> bool:
        self.connect_count += 1
        return not self.fail_connect

    async def write_register(self, address: int, value: int, **_kw) -> _FakeResponse:
        if len(self.writes) in self.fail_writes_at:
            self.writes.append((address, value))  # record the attempt
            return _FakeResponse(error=True)
        self.writes.append((address, value))
        return _FakeResponse()

    async def read_holding_registers(self, address: int, *, count: int = 1, **_kw):
        regs = [self.holding.get(address + i, 0) for i in range(count)]
        return _FakeResponse(registers=regs)

    def close(self) -> None:
        pass


class FakeClock:
    def __init__(self, start: float = 1_000_000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, s: float) -> None:
        self.t += s


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_client() -> FakeModbusClient:
    return FakeModbusClient()


@pytest.fixture()
def clock() -> FakeClock:
    return FakeClock()


def make_controller(
    tmp_path,
    fake_client: FakeModbusClient,
    clock: FakeClock,
    *,
    dry_run: bool = False,
    limits: ControlLimits | None = None,
) -> SungrowController:
    return SungrowController(
        host="192.0.2.1",
        port=502,
        slave_id=1,
        limits=limits or ControlLimits(),
        dry_run=dry_run,
        state_path=str(tmp_path / "control-state.json"),
        audit_path=str(tmp_path / "control-audit.jsonl"),
        client_factory=lambda: fake_client,
        now_fn=clock,
    )


def _audit_events(tmp_path) -> list[dict]:
    path = tmp_path / "control-audit.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _cmd(mode: str = "charge", power_w: int = 2000, ttl_s: int = 900) -> CommandRequest:
    return CommandRequest(mode=mode, power_w=power_w, ttl_s=ttl_s, issuer="test")


# ---------------------------------------------------------------------------
# AC1: validation and clamping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_charge_requires_positive_power(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    ctrl.observe_soc(50.0)
    with pytest.raises(ControlError, match="power_w"):
        await ctrl.apply(_cmd(power_w=0))
    assert fake_client.writes == []


@pytest.mark.asyncio
async def test_ttl_below_minimum_rejected(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    ctrl.observe_soc(50.0)
    with pytest.raises(ControlError, match="ttl_s"):
        await ctrl.apply(_cmd(ttl_s=30))


@pytest.mark.asyncio
async def test_ttl_above_maximum_rejected(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    ctrl.observe_soc(50.0)
    with pytest.raises(ControlError, match="ttl_s"):
        await ctrl.apply(_cmd(ttl_s=999_999))


@pytest.mark.asyncio
async def test_charge_power_clamped_to_limit(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    ctrl.observe_soc(50.0)
    result = await ctrl.apply(_cmd(power_w=9999))
    assert result["power_w"] == 4000
    assert (REG_FORCE_POWER, 4000) in fake_client.writes


@pytest.mark.asyncio
async def test_discharge_power_clamped_to_limit(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    ctrl.observe_soc(50.0)
    result = await ctrl.apply(_cmd(mode="discharge", power_w=9999))
    assert result["power_w"] == 6600


def test_invalid_mode_rejected():
    with pytest.raises(ValueError):
        CommandRequest(mode="explode", power_w=100, ttl_s=900, issuer="test")


# ---------------------------------------------------------------------------
# AC1: SOC guardrails at accept time
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discharge_rejected_at_soc_floor(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    ctrl.observe_soc(11.0)  # below default 12% floor
    with pytest.raises(ControlError, match="SOC"):
        await ctrl.apply(_cmd(mode="discharge", power_w=1000))
    assert fake_client.writes == []


@pytest.mark.asyncio
async def test_charge_rejected_at_soc_ceiling(tmp_path, fake_client, clock):
    ctrl = make_controller(
        tmp_path, fake_client, clock, limits=ControlLimits(max_soc_pct=95.0)
    )
    ctrl.observe_soc(96.0)
    with pytest.raises(ControlError, match="SOC"):
        await ctrl.apply(_cmd(power_w=1000))


@pytest.mark.asyncio
async def test_force_rejected_without_soc_telemetry(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    with pytest.raises(ControlError, match="telemetry"):
        await ctrl.apply(_cmd(power_w=1000))


@pytest.mark.asyncio
async def test_hold_allowed_without_soc_telemetry(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    result = await ctrl.apply(CommandRequest(mode="hold", ttl_s=900, issuer="test"))
    assert result["accepted"] is True


# ---------------------------------------------------------------------------
# AC2: dry-run invariant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dry_run_never_writes(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock, dry_run=True)
    ctrl.observe_soc(50.0)
    result = await ctrl.apply(_cmd())
    assert result["dry_run"] is True
    assert fake_client.writes == []
    assert ctrl.status()["active"] is not None


@pytest.mark.asyncio
async def test_dry_run_ttl_expiry_reverts_without_writes(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock, dry_run=True)
    ctrl.observe_soc(50.0)
    await ctrl.apply(_cmd(ttl_s=60))
    clock.advance(61)
    await ctrl.watchdog_tick()
    assert fake_client.writes == []
    assert ctrl.status()["active"] is None
    events = [e["event"] for e in _audit_events(tmp_path)]
    assert "revert" in events


# ---------------------------------------------------------------------------
# AC3: live write sequence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_charge_write_sequence_order(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    ctrl.observe_soc(50.0)
    await ctrl.apply(_cmd(power_w=2000))
    assert fake_client.writes == [
        (REG_FORCE_POWER, 2000),
        (REG_EMS_MODE, EMS_MODE_FORCED),
        (REG_FORCE_CMD, CMD_CHARGE),
    ]


@pytest.mark.asyncio
async def test_discharge_write_sequence(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    ctrl.observe_soc(50.0)
    await ctrl.apply(_cmd(mode="discharge", power_w=1500))
    assert fake_client.writes == [
        (REG_FORCE_POWER, 1500),
        (REG_EMS_MODE, EMS_MODE_FORCED),
        (REG_FORCE_CMD, CMD_DISCHARGE),
    ]


@pytest.mark.asyncio
async def test_hold_write_sequence(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    await ctrl.apply(CommandRequest(mode="hold", ttl_s=900, issuer="test"))
    assert fake_client.writes == [
        (REG_FORCE_POWER, 0),
        (REG_EMS_MODE, EMS_MODE_FORCED),
        (REG_FORCE_CMD, CMD_STOP),
    ]


@pytest.mark.asyncio
async def test_auto_write_sequence(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    await ctrl.apply(CommandRequest(mode="auto", issuer="test"))
    assert fake_client.writes == [
        (REG_FORCE_CMD, CMD_STOP),
        (REG_EMS_MODE, EMS_MODE_SELF),
    ]
    assert ctrl.status()["active"] is None


@pytest.mark.asyncio
async def test_failed_write_sequence_is_rolled_back(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    ctrl.observe_soc(50.0)
    fake_client.fail_writes_at = {2}  # power, mode succeed; cmd write fails
    with pytest.raises(ControlError, match="write"):
        await ctrl.apply(_cmd(power_w=2000))
    # rollback: stop + self-consumption appended after the failed sequence
    assert fake_client.writes[-2:] == [
        (REG_FORCE_CMD, CMD_STOP),
        (REG_EMS_MODE, EMS_MODE_SELF),
    ]
    assert ctrl.status()["active"] is None


# ---------------------------------------------------------------------------
# AC4: deadman watchdog
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ttl_expiry_reverts_to_auto(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    ctrl.observe_soc(50.0)
    await ctrl.apply(_cmd(ttl_s=300))
    fake_client.writes.clear()
    clock.advance(301)
    await ctrl.watchdog_tick()
    assert fake_client.writes == [
        (REG_FORCE_CMD, CMD_STOP),
        (REG_EMS_MODE, EMS_MODE_SELF),
    ]
    assert ctrl.status()["active"] is None
    assert any(
        e["event"] == "revert" and e["reason"] == "ttl_expired"
        for e in _audit_events(tmp_path)
    )


@pytest.mark.asyncio
async def test_watchdog_noop_before_expiry(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    ctrl.observe_soc(50.0)
    await ctrl.apply(_cmd(ttl_s=300))
    fake_client.writes.clear()
    clock.advance(100)
    await ctrl.watchdog_tick()
    assert fake_client.writes == []
    assert ctrl.status()["active"] is not None


@pytest.mark.asyncio
async def test_soc_floor_breach_reverts_discharge(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    ctrl.observe_soc(50.0)
    await ctrl.apply(_cmd(mode="discharge", power_w=1000, ttl_s=3600))
    fake_client.writes.clear()
    ctrl.observe_soc(11.5)
    await ctrl.watchdog_tick()
    assert (REG_EMS_MODE, EMS_MODE_SELF) in fake_client.writes
    assert any(
        e["event"] == "revert" and e["reason"] == "soc_floor"
        for e in _audit_events(tmp_path)
    )


@pytest.mark.asyncio
async def test_soc_ceiling_breach_reverts_charge(tmp_path, fake_client, clock):
    ctrl = make_controller(
        tmp_path, fake_client, clock, limits=ControlLimits(max_soc_pct=95.0)
    )
    ctrl.observe_soc(50.0)
    await ctrl.apply(_cmd(power_w=1000, ttl_s=3600))
    fake_client.writes.clear()
    ctrl.observe_soc(95.5)
    await ctrl.watchdog_tick()
    assert (REG_EMS_MODE, EMS_MODE_SELF) in fake_client.writes


@pytest.mark.asyncio
async def test_failed_revert_retried_next_tick(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    ctrl.observe_soc(50.0)
    await ctrl.apply(_cmd(ttl_s=60))
    clock.advance(61)
    fake_client.writes.clear()
    fake_client.fail_writes_at = {0}  # first revert write fails
    await ctrl.watchdog_tick()
    assert ctrl.status()["active"] is not None  # revert failed, still armed
    fake_client.fail_writes_at = set()
    await ctrl.watchdog_tick()
    assert ctrl.status()["active"] is None


@pytest.mark.asyncio
async def test_shutdown_reverts_active_force(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    ctrl.observe_soc(50.0)
    await ctrl.apply(_cmd(ttl_s=3600))
    fake_client.writes.clear()
    await ctrl.on_shutdown()
    assert fake_client.writes == [
        (REG_FORCE_CMD, CMD_STOP),
        (REG_EMS_MODE, EMS_MODE_SELF),
    ]


@pytest.mark.asyncio
async def test_shutdown_noop_when_idle(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    await ctrl.on_shutdown()
    assert fake_client.writes == []


# ---------------------------------------------------------------------------
# AC4/AC5: startup reconciliation + state persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_startup_reverts_orphaned_force_mode(tmp_path, fake_client, clock):
    fake_client.holding[REG_EMS_MODE] = EMS_MODE_FORCED
    ctrl = make_controller(tmp_path, fake_client, clock)
    await ctrl.reconcile_on_startup()
    assert (REG_EMS_MODE, EMS_MODE_SELF) in fake_client.writes
    assert any(
        e["event"] == "revert" and e["reason"] == "orphaned_force_mode"
        for e in _audit_events(tmp_path)
    )


@pytest.mark.asyncio
async def test_startup_noop_when_self_consumption(tmp_path, fake_client, clock):
    fake_client.holding[REG_EMS_MODE] = EMS_MODE_SELF
    ctrl = make_controller(tmp_path, fake_client, clock)
    await ctrl.reconcile_on_startup()
    assert fake_client.writes == []


@pytest.mark.asyncio
async def test_active_command_survives_restart(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    ctrl.observe_soc(50.0)
    await ctrl.apply(_cmd(ttl_s=3600))
    # "restart": new controller instance, same state file
    ctrl2 = make_controller(tmp_path, fake_client, clock)
    assert ctrl2.status()["active"] is not None
    assert ctrl2.status()["active"]["mode"] == "charge"


@pytest.mark.asyncio
async def test_expired_persisted_command_reverted_on_startup(
    tmp_path, fake_client, clock
):
    ctrl = make_controller(tmp_path, fake_client, clock)
    ctrl.observe_soc(50.0)
    await ctrl.apply(_cmd(ttl_s=60))
    clock.advance(3600)
    fake_client.writes.clear()
    ctrl2 = make_controller(tmp_path, fake_client, clock)
    await ctrl2.reconcile_on_startup()
    assert (REG_EMS_MODE, EMS_MODE_SELF) in fake_client.writes
    assert ctrl2.status()["active"] is None


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_records_command_and_writes(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    ctrl.observe_soc(50.0)
    await ctrl.apply(_cmd(power_w=2000))
    events = _audit_events(tmp_path)
    kinds = [e["event"] for e in events]
    assert "command_accepted" in kinds
    assert kinds.count("write") == 3
    accepted = next(e for e in events if e["event"] == "command_accepted")
    assert accepted["issuer"] == "test"
    assert accepted["mode"] == "charge"


@pytest.mark.asyncio
async def test_audit_records_rejection(tmp_path, fake_client, clock):
    ctrl = make_controller(tmp_path, fake_client, clock)
    ctrl.observe_soc(11.0)
    with pytest.raises(ControlError):
        await ctrl.apply(_cmd(mode="discharge"))
    assert any(e["event"] == "command_rejected" for e in _audit_events(tmp_path))


def test_default_soc_ceiling_is_95():
    """LFP calendar-aging default: don't park at 100% unless deliberate."""
    assert ControlLimits().max_soc_pct == 95.0


def test_observe_reads_sample_soc_field():
    """observe() must read SungrowSample.battery_soc_pct (regression:
    it read a nonexistent 'battery_soc' attr, so SOC never arrived and
    every charge/discharge was rejected as 'no telemetry' in production)."""
    from datetime import UTC, datetime

    from edge.src.models import SungrowSample

    sample = SungrowSample(
        device_id="dev-1",
        ts=datetime(2026, 7, 18, tzinfo=UTC),
        pv_power_w=0.0,
        pv_daily_kwh=0.0,
        battery_power_w=0.0,
        battery_soc_pct=42.0,
        battery_temp_c=20.0,
        load_power_w=0.0,
        export_power_w=0.0,
    )
    ctrl = SungrowController(
        host="192.0.2.1",
        state_path="/tmp/obs-state.json",
        audit_path="/tmp/obs-audit.jsonl",
        client_factory=lambda: FakeModbusClient(),
    )
    ctrl.observe(sample)
    assert ctrl.status()["last_soc_pct"] == 42.0
