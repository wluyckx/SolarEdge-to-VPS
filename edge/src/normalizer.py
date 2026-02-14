"""
Pure normalizer that converts raw Modbus register values into a SungrowSample.

Takes a flat dict of raw register integers (as returned by the poller),
applies type conversions (U16/U32/S16/S32), scaling factors, and range
validation, then returns a validated SungrowSample pydantic model.

This is a pure function: no side effects, no I/O, no clock.  The device_id
and timestamp are accepted as parameters so they can be injected by the caller.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-004)

TODO:
- None
"""

from __future__ import annotations

import logging
from datetime import datetime

from edge.src.models import SungrowSample
from edge.src.registers import ALL_REGISTERS, RegisterDef

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapping from SungrowSample field names to register names.
#
# For 32-bit registers (U32/S32) the poller delivers two keys:
#   "{name}_hi" (high word) and "{name}_lo" (low word).
# For 16-bit registers (U16/S16) the poller delivers one key: "{name}".
# ---------------------------------------------------------------------------

_FIELD_MAP: dict[str, str] = {
    "pv_power_w": "total_dc_power",
    "pv_daily_kwh": "daily_pv_generation",
    "battery_power_w": "battery_power",
    "battery_soc_pct": "battery_soc",
    "battery_temp_c": "battery_temperature",
    "load_power_w": "load_power",
    "export_power_w": "export_power",
}
"""Maps SungrowSample field name -> register name in ALL_REGISTERS."""


# ---------------------------------------------------------------------------
# Type conversion helpers
# ---------------------------------------------------------------------------


def _convert_u16(raw: int) -> int:
    """Interpret a raw value as unsigned 16-bit (no conversion needed)."""
    return raw & 0xFFFF


def _convert_s16(raw: int) -> int:
    """Interpret a raw 16-bit value as signed (two's complement)."""
    val = raw & 0xFFFF
    if val >= 0x8000:
        val -= 0x10000
    return val


def _convert_u32(hi: int, lo: int) -> int:
    """Assemble two U16 registers (high word first) into unsigned 32-bit."""
    return ((hi & 0xFFFF) << 16) | (lo & 0xFFFF)


def _convert_s32(hi: int, lo: int) -> int:
    """Assemble two U16 registers (high word first) into signed 32-bit."""
    val = ((hi & 0xFFFF) << 16) | (lo & 0xFFFF)
    if val >= 0x80000000:
        val -= 0x100000000
    return val


# ---------------------------------------------------------------------------
# Core: extract a single register value from the raw dict
# ---------------------------------------------------------------------------


def _extract_value(
    reg_def: RegisterDef,
    raw: dict[str, int],
) -> float | None:
    """Extract, type-convert, and scale a single register value.

    For 32-bit types, expects keys ``"{name}_hi"`` and ``"{name}_lo"``
    in *raw*.  For 16-bit types, expects a single key ``"{name}"``.

    Returns the scaled float value, or ``None`` if the required raw
    key(s) are missing or the scaled value falls outside the register's
    valid_range.
    """
    name = reg_def.name
    reg_type = reg_def.reg_type

    # --- Retrieve raw integer(s) ---
    if reg_type in ("U32", "S32"):
        hi_key = f"{name}_hi"
        lo_key = f"{name}_lo"
        if hi_key not in raw or lo_key not in raw:
            logger.warning(
                "Register '%s': missing raw keys (%s and/or %s)",
                name,
                hi_key,
                lo_key,
            )
            return None
        hi_val = raw[hi_key]
        lo_val = raw[lo_key]
        if reg_type == "U32":
            raw_int = _convert_u32(hi_val, lo_val)
        else:
            raw_int = _convert_s32(hi_val, lo_val)
    elif reg_type in ("U16", "S16"):
        if name not in raw:
            logger.warning("Register '%s': missing raw key", name)
            return None
        raw_val = raw[name]
        raw_int = _convert_u16(raw_val) if reg_type == "U16" else _convert_s16(raw_val)
    else:
        logger.warning("Register '%s': unsupported type '%s'", name, reg_type)
        return None

    # --- Apply scaling ---
    scaled = raw_int * reg_def.scale

    # --- Range validation ---
    if reg_def.valid_range is not None:
        lo, hi = reg_def.valid_range
        if not (lo <= scaled <= hi):
            raw_key = raw.get(name, raw.get(f"{name}_hi", -1))
            logger.warning(
                "Register '%s': scaled value %.4g "
                "(raw=%d) outside valid range (%s, %s)",
                name,
                scaled,
                raw_key,
                lo,
                hi,
            )
            return None

    return scaled


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize(
    raw: dict[str, int],
    *,
    device_id: str,
    ts: datetime,
) -> SungrowSample | None:
    """Convert raw Modbus register values into a validated SungrowSample.

    This is a **pure function**: it performs no I/O, has no side effects,
    and does not access the system clock.  The *device_id* and *ts* are
    passed in by the caller.

    Args:
        raw: Dict mapping register key names to raw integer values as
            delivered by the poller.  For 32-bit registers the keys are
            ``"{reg_name}_hi"`` and ``"{reg_name}_lo"``.
        device_id: Device identifier to embed in the sample.
        ts: Timestamp to embed in the sample.

    Returns:
        A validated :class:`SungrowSample` on success, or ``None`` if any
        required register is missing or any value fails range validation.
    """
    fields: dict[str, float] = {}

    for field_name, reg_name in _FIELD_MAP.items():
        reg_def = ALL_REGISTERS.get(reg_name)
        if reg_def is None:
            logger.warning("Register '%s' not found in ALL_REGISTERS", reg_name)
            return None

        value = _extract_value(reg_def, raw)
        if value is None:
            return None

        fields[field_name] = value

    return SungrowSample(
        device_id=device_id,
        ts=ts,
        **fields,
    )
