"""
Battery control module for Sungrow SH4.0RS via WiNet-S Modbus TCP.

Single writer for the inverter's forced charge/discharge holding registers.
Commands (charge / discharge / hold / auto) are validated, power-clamped,
SOC-guarded, and audited. A deadman watchdog reverts the inverter to
self-consumption when a command's TTL expires, when SOC breaches limits,
when the daemon shuts down, or when a startup reconciliation finds the
inverter orphaned in forced mode. The inverter itself has NO forced-mode
timeout, so this module's revert paths are the safety boundary.

``dry_run=True`` (the default) runs the full command lifecycle — accept,
track, expire, audit — but never writes to Modbus.

Write sequence (0-based holding registers, FC06):
    13051 power (W) -> 13049 EMS mode = 2 (forced) -> 13050 command
Revert sequence:
    13050 = 0xCC (stop) -> 13049 = 0 (self-consumption)

CHANGELOG:
- 2026-07-18: Initial creation -- battery-control Phase 1 (AC1-AC5)

TODO:
- None
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from pymodbus.client import AsyncModbusTcpClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Register map (0-based addresses, verified live 2026-07-18)
# ---------------------------------------------------------------------------

REG_EMS_MODE = 13049
REG_FORCE_CMD = 13050
REG_FORCE_POWER = 13051

EMS_MODE_SELF = 0
EMS_MODE_FORCED = 2

CMD_CHARGE = 0xAA
CMD_DISCHARGE = 0xBB
CMD_STOP = 0xCC

MODBUS_TIMEOUT_S: float = 10.0

_MODE_TO_CMD = {
    "charge": CMD_CHARGE,
    "discharge": CMD_DISCHARGE,
    "hold": CMD_STOP,
}


class ControlError(Exception):
    """A command was rejected or a Modbus write sequence failed."""


class CommandRequest(BaseModel):
    """A battery control command as received from the API or a planner."""

    mode: Literal["charge", "discharge", "hold", "auto"]
    power_w: int = 0
    ttl_s: int = 0
    issuer: str = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class ControlLimits:
    """Hard safety bounds enforced on every command.

    Power maxima default to the values read from the inverter's own limit
    registers 33046/33047 (4000/6600 W). The SOC floor sits above the 10%
    BMS minimum so forced discharge never races the BMS cutoff. The SOC
    ceiling defaults to 95% to limit time parked at full charge (LFP
    calendar aging); raise it deliberately ahead of high-price days.
    """

    max_charge_w: int = 4000
    max_discharge_w: int = 6600
    min_soc_pct: float = 12.0
    max_soc_pct: float = 95.0
    min_ttl_s: int = 60
    max_ttl_s: int = 21600  # 6 h


@dataclass(slots=True)
class ActiveCommand:
    """The currently armed forced-mode command."""

    mode: str
    power_w: int
    issuer: str
    issued_at: float
    expires_at: float

    def to_public(self) -> dict[str, Any]:
        d = asdict(self)
        d["issued_at"] = _iso(self.issued_at)
        d["expires_at"] = _iso(self.expires_at)
        return d


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=UTC).isoformat()


class SungrowController:
    """Single-writer battery controller with deadman watchdog.

    Args:
        host: WiNet-S IP / hostname.
        port: Modbus TCP port.
        slave_id: Modbus unit ID.
        limits: Hard safety bounds.
        dry_run: When True (default), never write to Modbus.
        state_path: JSON file persisting the active command across restarts.
        audit_path: JSONL audit trail of every command, write, and revert.
        client_factory: Returns a (pymodbus-compatible) async client.
            Injectable for tests.
        modbus_lock: Shared lock serializing Modbus access with the poller.
        now_fn: Wall-clock source (epoch seconds). Injectable for tests.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int = 502,
        slave_id: int = 1,
        limits: ControlLimits | None = None,
        dry_run: bool = True,
        state_path: str = "/data/control-state.json",
        audit_path: str = "/data/control-audit.jsonl",
        client_factory: Callable[[], Any] | None = None,
        modbus_lock: asyncio.Lock | None = None,
        now_fn: Callable[[], float] = time.time,
    ) -> None:
        self._host = host
        self._port = port
        self._slave_id = slave_id
        self.limits = limits or ControlLimits()
        self.dry_run = dry_run
        self._state_path = Path(state_path)
        self._audit_path = Path(audit_path)
        self._client_factory = client_factory or (
            lambda: AsyncModbusTcpClient(host, port=port, timeout=MODBUS_TIMEOUT_S)
        )
        self._lock = modbus_lock or asyncio.Lock()
        self._now = now_fn
        self._active: ActiveCommand | None = None
        self._last_soc_pct: float | None = None
        self._load_state()

    # -- telemetry ---------------------------------------------------------

    def observe_soc(self, soc_pct: float | None) -> None:
        """Record the latest battery SOC from the poll loop."""
        if soc_pct is not None:
            self._last_soc_pct = float(soc_pct)

    def observe(self, sample: Any) -> None:
        """Record telemetry from a normalized SungrowSample (best-effort)."""
        self.observe_soc(getattr(sample, "battery_soc_pct", None))

    # -- public API --------------------------------------------------------

    async def apply(self, req: CommandRequest) -> dict[str, Any]:
        """Validate and execute a command; returns the accepted result.

        Raises:
            ControlError: On validation failure or a failed write sequence
                (after best-effort rollback to self-consumption).
        """
        if req.mode == "auto":
            ok = await self._revert(reason="manual_auto", issuer=req.issuer)
            if not ok:
                raise ControlError("write sequence failed during revert to auto")
            return self._result(mode="auto", power_w=0, expires_at=None)

        self._validate_ttl(req)
        power_w = self._validate_and_clamp_power(req)

        now = self._now()
        cmd = ActiveCommand(
            mode=req.mode,
            power_w=power_w,
            issuer=req.issuer,
            issued_at=now,
            expires_at=now + req.ttl_s,
        )
        self._audit(
            "command_accepted",
            mode=cmd.mode,
            power_w=cmd.power_w,
            ttl_s=req.ttl_s,
            issuer=cmd.issuer,
            expires_at=_iso(cmd.expires_at),
            dry_run=self.dry_run,
        )

        if not self.dry_run:
            ok = await self._write_force_sequence(cmd)
            if not ok:
                await self._write_revert_sequence()
                self._set_active(None)
                raise ControlError(
                    f"Modbus write sequence failed for {req.mode}; "
                    "reverted to self-consumption"
                )

        self._set_active(cmd)
        return self._result(
            mode=cmd.mode, power_w=cmd.power_w, expires_at=cmd.expires_at
        )

    async def watchdog_tick(self) -> None:
        """Enforce TTL and SOC guards on the active command (deadman)."""
        cmd = self._active
        if cmd is None:
            return
        if self._now() >= cmd.expires_at:
            await self._revert(reason="ttl_expired")
            return
        soc = self._last_soc_pct
        if soc is None:
            return
        if cmd.mode == "discharge" and soc <= self.limits.min_soc_pct:
            await self._revert(reason="soc_floor")
        elif cmd.mode == "charge" and soc >= self.limits.max_soc_pct:
            await self._revert(reason="soc_ceiling")

    async def watchdog_loop(
        self, shutdown_event: asyncio.Event, interval_s: float = 5.0
    ) -> None:
        """Run watchdog_tick until shutdown. Never raises."""
        logger.info("Control watchdog started (interval=%ss)", interval_s)
        while not shutdown_event.is_set():
            try:
                await self.watchdog_tick()
            except Exception:
                logger.error("Watchdog tick error", exc_info=True)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(shutdown_event.wait(), timeout=interval_s)
        logger.info("Control watchdog stopped")

    async def on_shutdown(self) -> None:
        """Revert any active force before the daemon exits (deadman)."""
        if self._active is not None:
            await self._revert(reason="daemon_shutdown")

    async def reconcile_on_startup(self) -> None:
        """Resolve persisted state vs. actual inverter mode at startup.

        - A persisted, expired command is reverted immediately.
        - With no persisted command, an inverter found in forced mode is
          orphaned (crash while forced) and is reverted to self-consumption.
        """
        if self._active is not None:
            if self._now() >= self._active.expires_at:
                await self._revert(reason="ttl_expired")
            else:
                self._audit(
                    "reconcile", note="resuming persisted active command",
                    active=self._active.to_public(),
                )
            return

        try:
            ems_mode = await self._read_holding(REG_EMS_MODE)
        except Exception:
            logger.warning("Startup reconcile: EMS mode read failed", exc_info=True)
            self._audit("reconcile_failed", note="EMS mode read failed")
            return

        if ems_mode == EMS_MODE_FORCED:
            if self.dry_run:
                self._audit(
                    "orphaned_force_mode_detected",
                    note="dry_run: inverter in forced mode, NOT reverting",
                )
                logger.warning(
                    "Inverter is in forced EMS mode with no active command "
                    "(dry_run: not reverting)"
                )
            else:
                await self._revert(reason="orphaned_force_mode")
        else:
            self._audit("reconcile", note="inverter in self-consumption, clean start")

    def status(self) -> dict[str, Any]:
        """Current controller state for the API / dashboards."""
        return {
            "dry_run": self.dry_run,
            "active": self._active.to_public() if self._active else None,
            "last_soc_pct": self._last_soc_pct,
            "limits": asdict(self.limits),
            "now": _iso(self._now()),
        }

    def audit_tail(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the last ``limit`` audit events (oldest first)."""
        if not self._audit_path.exists():
            return []
        lines = self._audit_path.read_text().splitlines()
        events = []
        for line in lines[-limit:]:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events

    # -- validation --------------------------------------------------------

    def _validate_ttl(self, req: CommandRequest) -> None:
        if not (self.limits.min_ttl_s <= req.ttl_s <= self.limits.max_ttl_s):
            self._audit("command_rejected", reason="ttl", issuer=req.issuer)
            raise ControlError(
                f"ttl_s must be between {self.limits.min_ttl_s} and "
                f"{self.limits.max_ttl_s} (got {req.ttl_s})"
            )

    def _validate_and_clamp_power(self, req: CommandRequest) -> int:
        if req.mode == "hold":
            return 0
        if req.power_w <= 0:
            self._audit("command_rejected", reason="power", issuer=req.issuer)
            raise ControlError(f"power_w must be > 0 for {req.mode}")
        soc = self._last_soc_pct
        if soc is None:
            self._audit("command_rejected", reason="no_telemetry", issuer=req.issuer)
            raise ControlError(
                "no SOC telemetry yet; refusing forced charge/discharge"
            )
        if req.mode == "discharge" and soc <= self.limits.min_soc_pct:
            self._audit("command_rejected", reason="soc_floor", issuer=req.issuer)
            raise ControlError(
                f"SOC {soc:.1f}% at/below floor {self.limits.min_soc_pct}%"
            )
        if req.mode == "charge" and soc >= self.limits.max_soc_pct:
            self._audit("command_rejected", reason="soc_ceiling", issuer=req.issuer)
            raise ControlError(
                f"SOC {soc:.1f}% at/above ceiling {self.limits.max_soc_pct}%"
            )
        cap = (
            self.limits.max_charge_w
            if req.mode == "charge"
            else self.limits.max_discharge_w
        )
        return min(req.power_w, cap)

    # -- revert / deadman --------------------------------------------------

    async def _revert(self, *, reason: str, issuer: str | None = None) -> bool:
        """Return the inverter to self-consumption and clear the command.

        On a failed write the active command is kept so the watchdog
        retries on every subsequent tick. Returns True on success.
        """
        if self.dry_run:
            self._audit("revert", reason=reason, issuer=issuer, dry_run=True)
            self._set_active(None)
            return True
        ok = await self._write_revert_sequence()
        if ok:
            self._audit("revert", reason=reason, issuer=issuer, dry_run=False)
            self._set_active(None)
        else:
            self._audit("revert_failed", reason=reason, issuer=issuer)
            logger.error("Revert to self-consumption FAILED (reason=%s)", reason)
        return ok

    # -- Modbus I/O --------------------------------------------------------

    async def _write_force_sequence(self, cmd: ActiveCommand) -> bool:
        writes = [
            (REG_FORCE_POWER, cmd.power_w),
            (REG_EMS_MODE, EMS_MODE_FORCED),
            (REG_FORCE_CMD, _MODE_TO_CMD[cmd.mode]),
        ]
        return await self._write_all(writes)

    async def _write_revert_sequence(self) -> bool:
        writes = [
            (REG_FORCE_CMD, CMD_STOP),
            (REG_EMS_MODE, EMS_MODE_SELF),
        ]
        return await self._write_all(writes)

    async def _write_all(self, writes: list[tuple[int, int]]) -> bool:
        async with self._lock:
            client = self._client_factory()
            try:
                ok = await client.connect()
                if not ok:
                    self._audit("write_failed", note="connect failed")
                    return False
                for addr, value in writes:
                    resp = await client.write_register(
                        addr, value, device_id=self._slave_id
                    )
                    if resp.isError():
                        self._audit("write_failed", address=addr, value=value)
                        return False
                    self._audit("write", address=addr, value=value)
                return True
            except Exception:
                logger.warning("Modbus write error", exc_info=True)
                self._audit("write_failed", note="exception during write")
                return False
            finally:
                client.close()

    async def _read_holding(self, address: int) -> int:
        async with self._lock:
            client = self._client_factory()
            try:
                ok = await client.connect()
                if not ok:
                    raise ControlError("connect failed for holding read")
                resp = await client.read_holding_registers(
                    address, count=1, device_id=self._slave_id
                )
                if resp.isError():
                    raise ControlError(f"holding read failed at {address}")
                return resp.registers[0]
            finally:
                client.close()

    # -- state / audit -----------------------------------------------------

    def _set_active(self, cmd: ActiveCommand | None) -> None:
        self._active = cmd
        self._save_state()

    def _save_state(self) -> None:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"active": asdict(self._active) if self._active else None}
            self._state_path.write_text(json.dumps(payload))
        except OSError:
            logger.warning("Failed to persist control state", exc_info=True)

    def _load_state(self) -> None:
        try:
            if not self._state_path.exists():
                return
            payload = json.loads(self._state_path.read_text())
            raw = payload.get("active")
            if raw:
                self._active = ActiveCommand(**raw)
        except (OSError, json.JSONDecodeError, TypeError):
            logger.warning("Failed to load control state", exc_info=True)

    def _result(
        self, *, mode: str, power_w: int, expires_at: float | None
    ) -> dict[str, Any]:
        return {
            "accepted": True,
            "mode": mode,
            "power_w": power_w,
            "expires_at": _iso(expires_at) if expires_at else None,
            "dry_run": self.dry_run,
        }

    def _audit(self, event: str, **fields: Any) -> None:
        entry = {"ts": _iso(self._now()), "event": event}
        entry.update({k: v for k, v in fields.items() if v is not None})
        try:
            self._audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self._audit_path.open("a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            logger.warning("Failed to write audit entry", exc_info=True)
