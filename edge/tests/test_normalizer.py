"""
Tests for register normalizer -- converts raw Modbus values to SungrowSample.

Verifies type conversions (U16/U32/S16/S32), scaling, range validation,
and that the normalizer is a pure function with no side effects.

CHANGELOG:
- 2026-02-14: Initial creation -- TDD tests written first (STORY-004)

TODO:
- None
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest
from edge.src.models import SungrowSample
from edge.src.normalizer import normalize

# ---------------------------------------------------------------------------
# Helpers: build a minimal-valid raw register dict
# ---------------------------------------------------------------------------

_TS = datetime(2026, 2, 14, 12, 0, 0, tzinfo=UTC)
_DEVICE_ID = "sungrow-test-001"


def _make_raw(**overrides: list[int]) -> dict[str, list[int]]:
    """Return a raw register dict matching the poller's output format.

    Each value is a list of 16-bit words: 1-element for U16/S16,
    2-element [hi, lo] for U32/S32. Defaults produce values that,
    after type conversion and scaling, are within every register's
    valid_range.

    Required SungrowSample fields and the registers that feed them:
        pv_power_w        <- total_dc_power      (U32, scale=1, W)
        pv_daily_kwh      <- daily_pv_generation  (U16, scale=0.1, kWh)
        battery_power_w   <- battery_power         (S16, scale=1, W)
        battery_soc_pct   <- battery_soc           (U16, scale=0.1, %)
        battery_temp_c    <- battery_temperature   (U16, scale=0.1, C)
        load_power_w      <- load_power            (S32, scale=1, W)
        export_power_w    <- export_power          (S32, scale=1, W)
    """
    defaults: dict[str, list[int]] = {
        # U32: [hi_word, lo_word] -> (0 << 16) | 1000 = 1000 W
        "total_dc_power": [0, 1000],
        # U16: [50] * 0.1 = 5.0 kWh
        "daily_pv_generation": [50],
        # S16: [500] -> 500 W (charging)
        "battery_power": [500],
        # U16: [800] * 0.1 = 80.0 %
        "battery_soc": [800],
        # U16: [250] * 0.1 = 25.0 C
        "battery_temperature": [250],
        # S32: [hi, lo] -> 2000 W
        "load_power": [0, 2000],
        # S32: [hi, lo] -> 500 W
        "export_power": [0, 500],
    }
    defaults.update(overrides)
    return defaults


# ===========================================================================
# AC6: SungrowSample fields
# ===========================================================================


class TestSungrowSampleModel:
    """AC6: SungrowSample includes all required fields."""

    def test_sample_has_required_fields(self) -> None:
        sample = SungrowSample(
            device_id="dev-1",
            ts=_TS,
            pv_power_w=1000.0,
            pv_daily_kwh=5.0,
            battery_power_w=500.0,
            battery_soc_pct=80.0,
            battery_temp_c=25.0,
            load_power_w=2000.0,
            export_power_w=500.0,
        )
        assert sample.device_id == "dev-1"
        assert sample.ts == _TS
        assert sample.pv_power_w == 1000.0
        assert sample.pv_daily_kwh == 5.0
        assert sample.battery_power_w == 500.0
        assert sample.battery_soc_pct == 80.0
        assert sample.battery_temp_c == 25.0
        assert sample.load_power_w == 2000.0
        assert sample.export_power_w == 500.0

    def test_sample_is_pydantic_model(self) -> None:
        from pydantic import BaseModel

        assert issubclass(SungrowSample, BaseModel)


# ===========================================================================
# AC7: device_id and ts are passed through
# ===========================================================================


class TestPassthrough:
    """AC7: device_id and ts are passed through to SungrowSample."""

    def test_device_id_passed_through(self) -> None:
        raw = _make_raw()
        result = normalize(raw, device_id="my-device-42", ts=_TS)
        assert result is not None
        assert result.device_id == "my-device-42"

    def test_ts_passed_through(self) -> None:
        ts = datetime(2026, 6, 15, 8, 30, 0, tzinfo=UTC)
        raw = _make_raw()
        result = normalize(raw, device_id=_DEVICE_ID, ts=ts)
        assert result is not None
        assert result.ts == ts


# ===========================================================================
# AC1: Pure function -- known inputs produce expected outputs
# ===========================================================================


class TestKnownValues:
    """Known register values produce expected SungrowSample field values."""

    def test_all_defaults_produce_expected_sample(self) -> None:
        raw = _make_raw()
        result = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert result is not None
        assert result.pv_power_w == 1000.0
        assert result.pv_daily_kwh == pytest.approx(5.0)
        assert result.battery_power_w == 500.0
        assert result.battery_soc_pct == pytest.approx(80.0)
        assert result.battery_temp_c == pytest.approx(25.0)
        assert result.load_power_w == 2000.0
        assert result.export_power_w == 500.0

    def test_normalizer_returns_same_output_for_same_input(self) -> None:
        """Pure function: identical inputs -> identical outputs."""
        raw = _make_raw()
        r1 = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        r2 = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert r1 == r2


# ===========================================================================
# AC3: U32 assembly from two U16 registers
# ===========================================================================


class TestU32Assembly:
    """U32: two consecutive 16-bit registers assembled into one 32-bit value."""

    def test_u32_high_word_first(self) -> None:
        """[0x0001, 0x0000] -> 0x00010000 = 65536.

        Verifies U32 assembly math: (hi << 16) | lo.
        65536 exceeds total_dc_power valid_range (0, 20000) so the full
        normalize() rightly returns None.  We verify the assembly itself
        via the internal helper.
        """
        from edge.src.normalizer import _convert_u32

        assert _convert_u32(0x0001, 0x0000) == 65536

    def test_u32_assembly_in_sample(self) -> None:
        """[0x0000, 0x2710] -> 10000 W (in range for total_dc_power)."""
        raw = _make_raw(total_dc_power=[0x0000, 0x2710])
        result = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert result is not None
        assert result.pv_power_w == 10000.0

    def test_u32_low_word_only(self) -> None:
        """[0x0000, 0x1234] -> 0x1234 = 4660."""
        raw = _make_raw(total_dc_power=[0x0000, 0x1234])
        result = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert result is not None
        # valid_range for total_dc_power is (0, 20000); 4660 is in range
        assert result.pv_power_w == 4660.0

    def test_u32_both_words(self) -> None:
        """[0x0000, 0x03E8] -> 1000."""
        raw = _make_raw(total_dc_power=[0x0000, 0x03E8])
        result = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert result is not None
        assert result.pv_power_w == 1000.0


# ===========================================================================
# AC4: S16 signed values (two's complement)
# ===========================================================================


class TestS16Signed:
    """S16: signed 16-bit two's complement conversion."""

    def test_s16_negative_ffff(self) -> None:
        """Register 0xFFFF -> -1 (two's complement)."""
        raw = _make_raw(battery_power=[0xFFFF])
        result = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert result is not None
        assert result.battery_power_w == -1.0

    def test_s16_negative_large(self) -> None:
        """Register 0xFC18 -> -1000 (two's complement, in range)."""
        raw = _make_raw(battery_power=[0xFC18])
        result = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert result is not None
        assert result.battery_power_w == -1000.0

    def test_s16_positive(self) -> None:
        """Register 0x03E8 -> 1000 (positive stays positive)."""
        raw = _make_raw(battery_power=[0x03E8])
        result = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert result is not None
        assert result.battery_power_w == 1000.0


# ===========================================================================
# S32 signed 32-bit two's complement
# ===========================================================================


class TestS32Signed:
    """S32: signed 32-bit two's complement conversion."""

    def test_s32_negative(self) -> None:
        """[0xFFFF, 0xFE0C] -> -500 in S32 two's complement."""
        raw = _make_raw(export_power=[0xFFFF, 0xFE0C])
        result = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert result is not None
        assert result.export_power_w == -500.0

    def test_s32_positive(self) -> None:
        """[0x0000, 1500] -> +1500 in S32."""
        raw = _make_raw(export_power=[0x0000, 1500])
        result = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert result is not None
        assert result.export_power_w == 1500.0


# ===========================================================================
# AC2: Scaling factors
# ===========================================================================


class TestScaling:
    """Scaling: raw value * scale factor = engineering value."""

    def test_scaling_0_1(self) -> None:
        """Raw 500 with scale 0.1 -> 50.0%."""
        raw = _make_raw(battery_soc=[500])
        result = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert result is not None
        assert result.battery_soc_pct == pytest.approx(50.0)

    def test_scaling_applied_to_daily_pv(self) -> None:
        """daily_pv_generation: raw 234 * 0.1 = 23.4 kWh."""
        raw = _make_raw(daily_pv_generation=[234])
        result = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert result is not None
        assert result.pv_daily_kwh == pytest.approx(23.4)

    def test_scaling_applied_to_battery_temp(self) -> None:
        """battery_temperature: raw 300 * 0.1 = 30.0 C."""
        raw = _make_raw(battery_temperature=[300])
        result = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert result is not None
        assert result.battery_temp_c == pytest.approx(30.0)

    def test_raw_999_with_scale_0_1_produces_99_9(self) -> None:
        """raw 999 * 0.1 = 99.9 kWh (in daily_pv_generation range)."""
        raw = _make_raw(daily_pv_generation=[999])
        result = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert result is not None
        assert result.pv_daily_kwh == pytest.approx(99.9)


# ===========================================================================
# AC5: Missing required register returns None
# ===========================================================================


class TestMissingRegister:
    """Missing required register -> normalize returns None."""

    def test_missing_battery_power(self) -> None:
        raw = _make_raw()
        del raw["battery_power"]
        result = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert result is None

    def test_missing_total_dc_power(self) -> None:
        raw = _make_raw()
        del raw["total_dc_power"]
        result = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert result is None

    def test_missing_load_power(self) -> None:
        raw = _make_raw()
        del raw["load_power"]
        result = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert result is None

    def test_missing_export_power(self) -> None:
        raw = _make_raw()
        del raw["export_power"]
        result = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert result is None

    def test_empty_dict_returns_none(self) -> None:
        result = normalize({}, device_id=_DEVICE_ID, ts=_TS)
        assert result is None


# ===========================================================================
# AC5: Out-of-range value returns None (with warning logged)
# ===========================================================================


class TestOutOfRange:
    """Out-of-range scaled value -> normalize returns None with warning."""

    def test_pv_power_over_max(self) -> None:
        """total_dc_power valid_range is (0, 20000). 25000 W is over."""
        raw = _make_raw(total_dc_power=[0, 25000])
        result = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert result is None

    def test_battery_soc_over_100(self) -> None:
        """battery_soc valid_range is (0, 100). raw 1100 * 0.1 = 110%."""
        raw = _make_raw(battery_soc=[1100])
        result = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert result is None

    def test_out_of_range_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Out-of-range should log a warning with register name."""
        raw = _make_raw(battery_soc=[1100])
        with caplog.at_level(logging.WARNING):
            normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert any("battery_soc" in msg for msg in caplog.messages)
        # Should mention the raw value or scaled value
        assert any("1100" in msg or "110" in msg for msg in caplog.messages)

    def test_negative_export_power_out_of_range(self) -> None:
        """export_power valid_range is (-20000, 20000). -25000 is out.

        -25000 in 32-bit two's complement: 0xFFFF9E58
        hi = 0xFFFF, lo = 0x9E58
        """
        raw = _make_raw(export_power=[0xFFFF, 0x9E58])
        result = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert result is None


# ===========================================================================
# Integration: poller output format feeds into normalizer
# ===========================================================================


class TestPollerNormalizerIntegration:
    """Verify that the poller's output format is accepted by the normalizer.

    The poller returns dict[str, list[int]] where each key is a register
    name (from registers.py) and each value is a list of raw 16-bit words
    sliced from the Modbus group response.  This test builds a realistic
    poller-shaped dict using the register definitions and confirms that
    normalize() produces a valid SungrowSample.
    """

    def test_simulated_poller_output_normalizes(self) -> None:
        """Build a dict exactly as _extract_register_values would."""
        from edge.src.registers import ALL_GROUPS

        # Simulate raw Modbus words per group, then slice per register
        # using the same logic as poller._extract_register_values.
        raw: dict[str, list[int]] = {}
        for group in ALL_GROUPS:
            # Create a zeroed word buffer for the entire group
            words = [0] * group.count
            # Fill in known registers with realistic raw values
            for reg in group.registers:
                offset = reg.address - group.start_address
                if reg.name == "total_dc_power":
                    # U32: 3000 W -> [0x0000, 0x0BB8]
                    words[offset] = 0x0000
                    words[offset + 1] = 0x0BB8
                elif reg.name == "daily_pv_generation":
                    # U16: 45 * 0.1 = 4.5 kWh
                    words[offset] = 45
                elif reg.name == "battery_power":
                    # S16: 750 W (charging)
                    words[offset] = 750
                elif reg.name == "battery_soc":
                    # U16: 650 * 0.1 = 65.0%
                    words[offset] = 650
                elif reg.name == "battery_temperature":
                    # U16: 230 * 0.1 = 23.0 C
                    words[offset] = 230
                elif reg.name == "load_power":
                    # S32: 1500 W -> [0, 1500]
                    words[offset] = 0
                    words[offset + 1] = 1500
                elif reg.name == "export_power":
                    # S32: 800 W -> [0, 800]
                    words[offset] = 0
                    words[offset + 1] = 800
            # Slice per register, exactly as the poller does
            for reg in group.registers:
                offset = reg.address - group.start_address
                raw[reg.name] = words[offset : offset + reg.word_count]

        result = normalize(raw, device_id=_DEVICE_ID, ts=_TS)
        assert result is not None
        assert result.pv_power_w == 3000.0
        assert result.pv_daily_kwh == pytest.approx(4.5)
        assert result.battery_power_w == 750.0
        assert result.battery_soc_pct == pytest.approx(65.0)
        assert result.battery_temp_c == pytest.approx(23.0)
        assert result.load_power_w == 1500.0
        assert result.export_power_w == 800.0
