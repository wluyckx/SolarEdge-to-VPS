"""
Tests for Sungrow Modbus register map.

Verifies register map integrity, consistency, and grouping for batched reads.

CHANGELOG:
- 2026-02-14: Initial creation — TDD tests written first (STORY-002)

TODO:
- None
"""

from __future__ import annotations

from edge.src.registers import (
    ALL_GROUPS,
    ALL_REGISTERS,
    RegisterDef,
    RegisterGroup,
)

# ---------------------------------------------------------------------------
# Required register names per acceptance criteria
# ---------------------------------------------------------------------------

PV_REGISTER_NAMES = {
    "total_dc_power",
    "daily_pv_generation",
    "total_pv_generation",
    "mppt1_voltage",
    "mppt1_current",
    "mppt2_voltage",
    "mppt2_current",
}

BATTERY_REGISTER_NAMES = {
    "battery_power",
    "battery_soc",
    "battery_temperature",
    "daily_battery_charge",
    "daily_battery_discharge",
}

LOAD_REGISTER_NAMES = {
    "load_power",
    "daily_direct_consumption",
}

GRID_REGISTER_NAMES = {
    "export_power",
    "grid_power",
}

DEVICE_REGISTER_NAMES = {
    "device_type_code",
    "serial_number",
}

VALID_TYPES = {"U16", "U32", "S16", "S32", "UTF8"}


# ---------------------------------------------------------------------------
# Helper: collect all register names from ALL_GROUPS
# ---------------------------------------------------------------------------


def _all_register_names() -> set[str]:
    """Return the set of all register names across all groups."""
    return {reg.name for group in ALL_GROUPS for reg in group.registers}


# ===========================================================================
# AC1: PV registers present
# ===========================================================================


class TestPVRegisters:
    """AC1: registers.py defines all PV registers."""

    def test_pv_registers_present(self) -> None:
        names = _all_register_names()
        for reg_name in PV_REGISTER_NAMES:
            assert reg_name in names, f"PV register '{reg_name}' missing"

    def test_total_dc_power_is_u32(self) -> None:
        reg = ALL_REGISTERS["total_dc_power"]
        assert reg.reg_type == "U32"
        assert reg.unit == "W"

    def test_daily_pv_generation_has_scaling(self) -> None:
        reg = ALL_REGISTERS["daily_pv_generation"]
        assert reg.scale == 0.1
        assert reg.unit == "kWh"

    def test_total_pv_generation_is_u32(self) -> None:
        reg = ALL_REGISTERS["total_pv_generation"]
        assert reg.reg_type == "U32"
        assert reg.scale == 0.1

    def test_mppt_voltages_have_scaling(self) -> None:
        for name in ("mppt1_voltage", "mppt2_voltage"):
            reg = ALL_REGISTERS[name]
            assert reg.scale == 0.1
            assert reg.unit == "V"

    def test_mppt_currents_have_scaling(self) -> None:
        for name in ("mppt1_current", "mppt2_current"):
            reg = ALL_REGISTERS[name]
            assert reg.scale == 0.1
            assert reg.unit == "A"


# ===========================================================================
# AC2: Battery registers present
# ===========================================================================


class TestBatteryRegisters:
    """AC2: registers.py defines all battery registers."""

    def test_battery_registers_present(self) -> None:
        names = _all_register_names()
        for reg_name in BATTERY_REGISTER_NAMES:
            assert reg_name in names, f"Battery register '{reg_name}' missing"

    def test_battery_power_is_signed(self) -> None:
        reg = ALL_REGISTERS["battery_power"]
        assert reg.reg_type == "S16"
        assert reg.unit == "W"

    def test_battery_soc_has_scaling(self) -> None:
        reg = ALL_REGISTERS["battery_soc"]
        assert reg.scale == 0.1
        assert reg.unit == "%"

    def test_battery_temperature_has_scaling(self) -> None:
        reg = ALL_REGISTERS["battery_temperature"]
        assert reg.scale == 0.1

    def test_daily_charge_discharge_have_scaling(self) -> None:
        for name in ("daily_battery_charge", "daily_battery_discharge"):
            reg = ALL_REGISTERS[name]
            assert reg.scale == 0.1
            assert reg.unit == "kWh"


# ===========================================================================
# AC3: Load registers present
# ===========================================================================


class TestLoadRegisters:
    """AC3: registers.py defines load registers."""

    def test_load_registers_present(self) -> None:
        names = _all_register_names()
        for reg_name in LOAD_REGISTER_NAMES:
            assert reg_name in names, f"Load register '{reg_name}' missing"

    def test_load_power_is_signed_32(self) -> None:
        reg = ALL_REGISTERS["load_power"]
        assert reg.reg_type == "S32"
        assert reg.unit == "W"

    def test_daily_direct_consumption_has_scaling(self) -> None:
        reg = ALL_REGISTERS["daily_direct_consumption"]
        assert reg.scale == 0.1
        assert reg.unit == "kWh"


# ===========================================================================
# AC4: Grid estimate registers present
# ===========================================================================


class TestGridRegisters:
    """AC4: registers.py defines grid estimate registers."""

    def test_grid_registers_present(self) -> None:
        names = _all_register_names()
        for reg_name in GRID_REGISTER_NAMES:
            assert reg_name in names, f"Grid register '{reg_name}' missing"

    def test_export_power_is_s32(self) -> None:
        reg = ALL_REGISTERS["export_power"]
        assert reg.reg_type == "S32"
        assert reg.unit == "W"

    def test_grid_power_is_signed(self) -> None:
        reg = ALL_REGISTERS["grid_power"]
        assert reg.unit == "W"


# ===========================================================================
# AC5: Device info registers present
# ===========================================================================


class TestDeviceRegisters:
    """AC5: registers.py defines device info registers."""

    def test_device_registers_present(self) -> None:
        names = _all_register_names()
        for reg_name in DEVICE_REGISTER_NAMES:
            assert reg_name in names, f"Device register '{reg_name}' missing"

    def test_device_type_code_is_u16(self) -> None:
        reg = ALL_REGISTERS["device_type_code"]
        assert reg.reg_type == "U16"

    def test_serial_number_type(self) -> None:
        reg = ALL_REGISTERS["serial_number"]
        assert reg.reg_type == "UTF8"


# ===========================================================================
# AC6: Each register has required fields
# ===========================================================================


class TestRegisterFields:
    """AC6: Each register has address, name, type, unit, scaling factor, valid range."""

    def test_all_registers_have_required_fields(self) -> None:
        for group in ALL_GROUPS:
            for reg in group.registers:
                assert isinstance(reg.address, int), f"{reg.name}: address must be int"
                assert isinstance(reg.name, str) and len(reg.name) > 0, (
                    f"register at {reg.address}: name must be non-empty str"
                )
                assert reg.reg_type in VALID_TYPES, (
                    f"{reg.name}: invalid type '{reg.reg_type}'"
                )
                assert isinstance(reg.unit, str), f"{reg.name}: unit must be str"
                assert isinstance(reg.scale, (int, float)), (
                    f"{reg.name}: scale must be numeric"
                )
                # valid_range is optional but if present must be a 2-tuple
                if reg.valid_range is not None:
                    assert len(reg.valid_range) == 2, (
                        f"{reg.name}: valid_range must be (min, max)"
                    )

    def test_scaling_factors_are_positive_numbers(self) -> None:
        for group in ALL_GROUPS:
            for reg in group.registers:
                assert reg.scale > 0, f"{reg.name}: scale must be > 0, got {reg.scale}"

    def test_valid_range_min_less_than_max(self) -> None:
        for group in ALL_GROUPS:
            for reg in group.registers:
                if reg.valid_range is not None:
                    lo, hi = reg.valid_range
                    assert lo < hi, (
                        f"{reg.name}: valid_range min ({lo}) must be < max ({hi})"
                    )

    def test_no_duplicate_register_addresses(self) -> None:
        seen: dict[int, str] = {}
        for group in ALL_GROUPS:
            for reg in group.registers:
                # For multi-register types (U32, S32, UTF8), only the
                # start address is stored; that is the canonical address.
                assert reg.address not in seen, (
                    f"Duplicate address {reg.address}: "
                    f"'{seen[reg.address]}' and '{reg.name}'"
                )
                seen[reg.address] = reg.name

    def test_no_duplicate_register_names(self) -> None:
        seen: dict[str, int] = {}
        for group in ALL_GROUPS:
            for reg in group.registers:
                assert reg.name not in seen, (
                    f"Duplicate name '{reg.name}': "
                    f"address {seen[reg.name]} and {reg.address}"
                )
                seen[reg.name] = reg.address


# ===========================================================================
# AC7: Register groups are contiguous for batched reads
# ===========================================================================


class TestRegisterGroups:
    """AC7: Registers grouped into contiguous ranges for efficient Modbus reads."""

    def test_all_groups_is_list(self) -> None:
        assert isinstance(ALL_GROUPS, list)
        assert len(ALL_GROUPS) > 0

    def test_each_group_has_required_attributes(self) -> None:
        for group in ALL_GROUPS:
            assert isinstance(group.group_name, str) and len(group.group_name) > 0
            assert isinstance(group.start_address, int) and group.start_address >= 0
            assert isinstance(group.count, int) and group.count > 0
            assert isinstance(group.registers, list) and len(group.registers) > 0

    def test_group_registers_within_contiguous_range(self) -> None:
        """Every register in a group must be within [start, start+count)."""
        for group in ALL_GROUPS:
            lo = group.start_address
            hi = group.start_address + group.count
            for reg in group.registers:
                reg_size = _reg_word_count(reg)
                assert lo <= reg.address < hi, (
                    f"Group '{group.group_name}': register '{reg.name}' "
                    f"(addr={reg.address}) is outside range [{lo}, {hi})"
                )
                assert reg.address + reg_size <= hi, (
                    f"Group '{group.group_name}': register '{reg.name}' "
                    f"(addr={reg.address}, size={reg_size}) extends beyond range"
                )

    def test_group_count_covers_all_registers(self) -> None:
        """Group count must be large enough to cover all registers in the group."""
        for group in ALL_GROUPS:
            max_end = 0
            for reg in group.registers:
                reg_end = reg.address + _reg_word_count(reg)
                if reg_end > max_end:
                    max_end = reg_end
            needed = max_end - group.start_address
            assert group.count >= needed, (
                f"Group '{group.group_name}': count={group.count} "
                f"but needs {needed} to cover all registers"
            )

    def test_group_count_not_excessive(self) -> None:
        """Group count should not be much larger than needed (max 10 padding)."""
        for group in ALL_GROUPS:
            max_end = 0
            for reg in group.registers:
                reg_end = reg.address + _reg_word_count(reg)
                if reg_end > max_end:
                    max_end = reg_end
            needed = max_end - group.start_address
            # Allow small padding for alignment, but not excessive
            assert group.count <= needed + 10, (
                f"Group '{group.group_name}': count={group.count} "
                f"is excessively larger than needed ({needed})"
            )

    def test_all_registers_dict_contains_all_registers(self) -> None:
        """ALL_REGISTERS dict is a flat lookup of all registers by name."""
        for group in ALL_GROUPS:
            for reg in group.registers:
                assert reg.name in ALL_REGISTERS
                assert ALL_REGISTERS[reg.name] is reg


# ===========================================================================
# Data class validation
# ===========================================================================


class TestDataclasses:
    """Verify RegisterDef and RegisterGroup are proper dataclasses."""

    def test_register_def_is_dataclass(self) -> None:
        import dataclasses

        assert dataclasses.is_dataclass(RegisterDef)

    def test_register_group_is_dataclass(self) -> None:
        import dataclasses

        assert dataclasses.is_dataclass(RegisterGroup)

    def test_register_def_fields(self) -> None:
        import dataclasses

        field_names = {f.name for f in dataclasses.fields(RegisterDef)}
        required = {"address", "name", "reg_type", "unit", "scale", "valid_range"}
        assert required.issubset(field_names), (
            f"RegisterDef missing fields: {required - field_names}"
        )

    def test_register_group_fields(self) -> None:
        import dataclasses

        field_names = {f.name for f in dataclasses.fields(RegisterGroup)}
        required = {"group_name", "start_address", "count", "registers"}
        assert required.issubset(field_names), (
            f"RegisterGroup missing fields: {required - field_names}"
        )


# ===========================================================================
# Helper
# ===========================================================================


def _reg_word_count(reg: RegisterDef) -> int:
    """Return the number of 16-bit Modbus words occupied by a register."""
    if reg.reg_type in ("U16", "S16"):
        return 1
    if reg.reg_type in ("U32", "S32"):
        return 2
    if reg.reg_type == "UTF8":
        # UTF8 registers occupy a variable number of words;
        # read from the register's word_count attribute.
        return getattr(reg, "word_count", 10)
    msg = f"Unknown register type: {reg.reg_type}"
    raise ValueError(msg)
