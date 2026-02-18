"""
Sungrow SH4.0RS Modbus TCP register map -- single source of truth.

Defines all register addresses, data types, scaling factors, units, and valid
value ranges for the Sungrow SH4.0RS hybrid inverter accessed via the WiNet-S
Modbus TCP dongle (port 502, slave ID 1, function code 0x04 input registers).

Registers are organised into contiguous groups for efficient batched reads.
Each group covers a contiguous Modbus address range so the poller can issue
one ``read_input_registers`` call per group.

References:
    - Sungrow Hybrid Inverter Communication Protocol
    - https://github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant
    - https://github.com/bohdan-s/SunGather

CHANGELOG:
- 2026-02-18: Revert register addresses to original 13008-13027 — addresses 13119-13150
  (GoSungrow p-codes) are cloud API parameter IDs, not Modbus register addresses.
  WiNet-S returns Modbus error for 13119+ range. Original addresses read successfully.
- 2026-02-14: Initial creation (STORY-002)

TODO:
- None
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Data definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RegisterDef:
    """Definition of a single Modbus register.

    Attributes:
        address: Modbus input register start address.
        name: Unique human-readable identifier used as dict key.
        reg_type: Data type -- one of ``"U16"``, ``"U32"``, ``"S16"``,
            ``"S32"``, ``"UTF8"``.
        unit: Engineering unit string (e.g. ``"W"``, ``"kWh"``, ``"%"``).
        scale: Multiplicative scaling factor applied to the raw integer
            value to obtain the engineering value.  For example 0.1 means
            the raw value is in tenths of the unit.
        valid_range: Optional ``(min, max)`` tuple for the *scaled* value.
            ``None`` when no range check is applicable.
        description: Free-text description of the register.
        word_count: Number of 16-bit Modbus words this register occupies.
            Automatically derived from *reg_type* when not set explicitly
            (U16/S16 -> 1, U32/S32 -> 2).  UTF8 registers must set this
            explicitly.
    """

    address: int
    name: str
    reg_type: str
    unit: str
    scale: float = 1.0
    valid_range: tuple[float, float] | None = None
    description: str = ""
    word_count: int = field(default=0, repr=False)

    def __post_init__(self) -> None:  # noqa: D105
        # Derive word_count from reg_type when caller did not set it.
        if self.word_count == 0:
            wc = _DEFAULT_WORD_COUNTS.get(self.reg_type)
            if wc is None:
                msg = (
                    f"Register '{self.name}': word_count must be set "
                    f"explicitly for type '{self.reg_type}'"
                )
                raise ValueError(msg)
            # frozen=True requires object.__setattr__
            object.__setattr__(self, "word_count", wc)


_DEFAULT_WORD_COUNTS: dict[str, int] = {
    "U16": 1,
    "S16": 1,
    "U32": 2,
    "S32": 2,
}


@dataclass(frozen=True, slots=True)
class RegisterGroup:
    """A contiguous range of Modbus registers that can be read in one call.

    Attributes:
        group_name: Human-readable group identifier (e.g. ``"pv"``).
        start_address: First Modbus register address in the batch.
        count: Total number of 16-bit words to read.
        registers: Ordered list of :class:`RegisterDef` within this range.
    """

    group_name: str
    start_address: int
    count: int
    registers: list[RegisterDef]


# ---------------------------------------------------------------------------
# Device info group (addresses 4990-5000)
# Read once at startup to identify the inverter.
# ---------------------------------------------------------------------------

_DEVICE_REGISTERS: list[RegisterDef] = [
    RegisterDef(
        address=4990,
        name="serial_number",
        reg_type="UTF8",
        unit="",
        scale=1,
        valid_range=None,
        description="Inverter serial number (10 ASCII chars in 10 words)",
        word_count=10,
    ),
    RegisterDef(
        address=5000,
        name="device_type_code",
        reg_type="U16",
        unit="",
        scale=1,
        valid_range=(0, 65535),
        description="Model identifier code",
    ),
]

DEVICE_GROUP = RegisterGroup(
    group_name="device",
    start_address=4990,
    count=11,  # 4990..5000 inclusive = 11 words
    registers=_DEVICE_REGISTERS,
)

# ---------------------------------------------------------------------------
# PV production group (addresses 5004-5018)
# ---------------------------------------------------------------------------

_PV_REGISTERS: list[RegisterDef] = [
    RegisterDef(
        address=5004,
        name="total_dc_power",
        reg_type="U32",
        unit="W",
        scale=1,
        valid_range=(0, 20000),
        description="Current total DC power from all MPPT inputs",
    ),
    RegisterDef(
        address=5011,
        name="daily_pv_generation",
        reg_type="U16",
        unit="kWh",
        scale=0.1,
        valid_range=(0, 100),
        description="PV energy generated today",
    ),
    RegisterDef(
        address=5012,
        name="mppt1_voltage",
        reg_type="U16",
        unit="V",
        scale=0.1,
        valid_range=(0, 600),
        description="MPPT 1 DC voltage",
    ),
    RegisterDef(
        address=5013,
        name="mppt1_current",
        reg_type="U16",
        unit="A",
        scale=0.1,
        valid_range=(0, 20),
        description="MPPT 1 DC current",
    ),
    RegisterDef(
        address=5014,
        name="mppt2_voltage",
        reg_type="U16",
        unit="V",
        scale=0.1,
        valid_range=(0, 600),
        description="MPPT 2 DC voltage",
    ),
    RegisterDef(
        address=5015,
        name="mppt2_current",
        reg_type="U16",
        unit="A",
        scale=0.1,
        valid_range=(0, 20),
        description="MPPT 2 DC current",
    ),
    RegisterDef(
        address=5017,
        name="total_pv_generation",
        reg_type="U32",
        unit="kWh",
        scale=0.1,
        valid_range=(0, 1_000_000),
        description="Cumulative total PV energy generated",
    ),
]

PV_GROUP = RegisterGroup(
    group_name="pv",
    start_address=5004,
    count=15,  # 5004..5018 inclusive = 15 words
    registers=_PV_REGISTERS,
)

# ---------------------------------------------------------------------------
# Export / grid estimate group (addresses 5083-5084)
# ---------------------------------------------------------------------------

_EXPORT_REGISTERS: list[RegisterDef] = [
    RegisterDef(
        address=5083,
        name="export_power",
        reg_type="S32",
        unit="W",
        scale=1,
        valid_range=(-20000, 20000),
        description=(
            "Inverter-estimated export power. "
            "Positive = exporting to grid, negative = importing."
        ),
    ),
]

EXPORT_GROUP = RegisterGroup(
    group_name="export",
    start_address=5083,
    count=2,  # S32 = 2 words
    registers=_EXPORT_REGISTERS,
)

# ---------------------------------------------------------------------------
# Load / consumption group (addresses 13008-13017)
# ---------------------------------------------------------------------------

_LOAD_REGISTERS: list[RegisterDef] = [
    RegisterDef(
        address=13008,
        name="load_power",
        reg_type="S32",
        unit="W",
        scale=1,
        valid_range=(-20000, 50000),
        description="Total house load consumption (two registers)",
    ),
    RegisterDef(
        address=13010,
        name="grid_power",
        reg_type="S16",
        unit="W",
        scale=1,
        valid_range=(-20000, 20000),
        description=(
            "Inverter-estimated grid power. Positive = importing, negative = exporting."
        ),
    ),
    RegisterDef(
        address=13017,
        name="daily_direct_consumption",
        reg_type="U16",
        unit="kWh",
        scale=0.1,
        valid_range=(0, 200),
        description="PV energy directly consumed today (not via grid/battery)",
    ),
]

LOAD_GROUP = RegisterGroup(
    group_name="load",
    start_address=13008,
    count=10,  # 13008..13017 inclusive = 10 words
    registers=_LOAD_REGISTERS,
)

# ---------------------------------------------------------------------------
# Battery group (addresses 13022-13027)
# ---------------------------------------------------------------------------

_BATTERY_REGISTERS: list[RegisterDef] = [
    RegisterDef(
        address=13022,
        name="battery_power",
        reg_type="S16",
        unit="W",
        scale=1,
        valid_range=(-10000, 10000),
        description="Battery power. Positive = charging, negative = discharging.",
    ),
    RegisterDef(
        address=13023,
        name="battery_soc",
        reg_type="U16",
        unit="%",
        scale=0.1,
        valid_range=(0, 100),
        description="Battery state of charge",
    ),
    RegisterDef(
        address=13024,
        name="battery_temperature",
        reg_type="U16",
        unit="C",
        scale=0.1,
        valid_range=(-20, 60),
        description="Battery temperature",
    ),
    RegisterDef(
        address=13026,
        name="daily_battery_discharge",
        reg_type="U16",
        unit="kWh",
        scale=0.1,
        valid_range=(0, 100),
        description="Battery energy discharged today",
    ),
    RegisterDef(
        address=13027,
        name="daily_battery_charge",
        reg_type="U16",
        unit="kWh",
        scale=0.1,
        valid_range=(0, 100),
        description="Battery energy charged today",
    ),
]

BATTERY_GROUP = RegisterGroup(
    group_name="battery",
    start_address=13022,
    count=6,  # 13022..13027 inclusive = 6 words
    registers=_BATTERY_REGISTERS,
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

ALL_GROUPS: list[RegisterGroup] = [
    DEVICE_GROUP,
    PV_GROUP,
    EXPORT_GROUP,
    LOAD_GROUP,
    BATTERY_GROUP,
]
"""All register groups in recommended read order."""

ALL_REGISTERS: dict[str, RegisterDef] = {
    reg.name: reg for group in ALL_GROUPS for reg in group.registers
}
"""Flat lookup of every register by name."""
