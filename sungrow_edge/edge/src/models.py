"""
Pydantic models for normalized energy telemetry samples.

Defines the SungrowSample model that represents a single snapshot of
inverter telemetry after raw Modbus register values have been converted
to engineering units with proper scaling.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-004)

TODO:
- None
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SungrowSample(BaseModel):
    """A single normalized telemetry sample from a Sungrow hybrid inverter.

    All values are in engineering units after scaling and type conversion.
    The device_id and ts are injected by the caller (not derived from
    register data), keeping the normalizer a pure function.

    Attributes:
        device_id: Unique identifier for the inverter device.
        ts: Timestamp of the sample (injected, not from registers).
        pv_power_w: Current total DC power from PV panels in watts.
        pv_daily_kwh: PV energy generated today in kilowatt-hours.
        battery_power_w: Battery power in watts.
            Positive = charging, negative = discharging.
        battery_soc_pct: Battery state of charge as a percentage (0-100).
        battery_temp_c: Battery temperature in degrees Celsius.
        load_power_w: Total house load consumption in watts.
        export_power_w: Power exported to grid in watts.
            Positive = exporting, negative = importing.
    """

    device_id: str
    ts: datetime
    pv_power_w: float
    pv_daily_kwh: float
    battery_power_w: float
    battery_soc_pct: float
    battery_temp_c: float
    load_power_w: float
    export_power_w: float
