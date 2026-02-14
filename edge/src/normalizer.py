"""
Pure normalizer that converts raw Modbus register values into a SungrowSample.

Takes a dict of raw register word lists (as returned by the poller), applies
type conversions (U16/U32/S16/S32), scaling factors, and range validation,
then returns a validated SungrowSample pydantic model.

The poller returns ``dict[str, list[int]]`` where each key is a register name
and each value is a list of 16-bit words (length 1 for U16/S16, length 2 for
U32/S32).

This is a pure function: no side effects, no I/O, no clock.  The device_id
and timestamp are accepted as parameters so they can be injected by the caller.

CHANGELOG:
- 2026-02-14: Add S32 fallback decoder for devices exposing legacy S16 in low word
- 2026-02-14: Fallback export_power_w to -grid_power when export register is missing
- 2026-02-14: Fix contract to accept poller's dict[str, list[int]] format
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
# The poller delivers dict[str, list[int]] where each key is a register name
# and each value is a list of 16-bit words (1 word for U16/S16, 2 for U32/S32).
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
    raw: dict[str, list[int]],
) -> float | None:
    """Extract, type-convert, and scale a single register value.

    The *raw* dict maps register names to word lists as produced by the
    poller: 1-element lists for U16/S16, 2-element lists for U32/S32.

    Returns the scaled float value, or ``None`` if the required raw
    key is missing, has wrong word count, or the scaled value falls
    outside the register's valid_range.
    """
    name = reg_def.name
    reg_type = reg_def.reg_type

    if name not in raw:
        logger.warning("Register '%s': missing from raw data", name)
        return None

    words = raw[name]

    # --- Retrieve raw integer(s) ---
    if reg_type in ("U32", "S32"):
        if len(words) < 2:
            logger.warning(
                "Register '%s': expected 2 words for %s, got %d",
                name,
                reg_type,
                len(words),
            )
            return None
        hi_val, lo_val = words[0], words[1]
        if reg_type == "U32":
            raw_int = _convert_u32(hi_val, lo_val)
        else:
            raw_int = _convert_s32(hi_val, lo_val)
    elif reg_type in ("U16", "S16"):
        if len(words) < 1:
            logger.warning(
                "Register '%s': expected 1 word for %s, got 0",
                name,
                reg_type,
            )
            return None
        raw_val = words[0]
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
            # Some inverter firmwares expose S16 values in the low word while
            # still returning 2 words for documented S32 registers.
            # Example observed on load_power: [0, 62000].
            if reg_type == "S32" and len(words) >= 2 and words[0] in (0, 0xFFFF):
                alt_raw_int = _convert_s16(words[1])
                alt_scaled = alt_raw_int * reg_def.scale
                if lo <= alt_scaled <= hi:
                    logger.warning(
                        "Register '%s': S32 out-of-range %.4g from words=%s; "
                        "using legacy low-word S16 fallback %.4g",
                        name,
                        scaled,
                        words,
                        alt_scaled,
                    )
                    return alt_scaled

            logger.warning(
                "Register '%s': scaled value %.4g "
                "(raw words=%s) outside valid range (%s, %s)",
                name,
                scaled,
                words,
                lo,
                hi,
            )
            return None

    return scaled


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize(
    raw: dict[str, list[int]],
    *,
    device_id: str,
    ts: datetime,
) -> SungrowSample | None:
    """Convert raw Modbus register values into a validated SungrowSample.

    This is a **pure function**: it performs no I/O, has no side effects,
    and does not access the system clock.  The *device_id* and *ts* are
    passed in by the caller.

    Args:
        raw: Dict mapping register names to lists of raw 16-bit words,
            as returned by the poller.  1-element lists for U16/S16,
            2-element lists for U32/S32.
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

        # Some inverters do not expose export_power (register 5083).
        # Use grid_power fallback (positive import / negative export), so
        # export_power_w = -grid_power.
        if field_name == "export_power_w" and reg_name not in raw:
            grid_reg = ALL_REGISTERS.get("grid_power")
            if grid_reg is not None:
                grid_value = _extract_value(grid_reg, raw)
                if grid_value is not None:
                    fields[field_name] = -grid_value
                    logger.warning(
                        "Register '%s' missing; falling back to -grid_power",
                        reg_name,
                    )
                    continue

        value = _extract_value(reg_def, raw)
        if value is None:
            return None

        fields[field_name] = value

    return SungrowSample(
        device_id=device_id,
        ts=ts,
        **fields,
    )
