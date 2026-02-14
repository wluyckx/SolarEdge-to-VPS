"""
SQLAlchemy ORM models for the VPS database.

Defines the SungrowSample model for storing solar, battery, and load
telemetry data in a TimescaleDB hypertable. Composite primary key
(device_id, ts) enables idempotent ingestion per HC-002.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-008)

TODO:
- None
"""

import datetime

from sqlalchemy import DateTime, Double, Integer, Text, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all VPS ORM models."""

    pass


class SungrowSample(Base):
    """Solar/battery/load telemetry sample from a Sungrow SH4.0RS inverter.

    Stored in the sungrow_samples TimescaleDB hypertable with a composite
    primary key on (device_id, ts) for idempotent ingestion (HC-002).

    Attributes:
        device_id: Identifier of the Sungrow inverter device.
        ts: Measurement timestamp in UTC.
        pv_power_w: Current PV production power in watts.
        pv_daily_kwh: Cumulative daily PV energy in kWh (nullable).
        battery_power_w: Battery power in watts.
            Positive = charging, negative = discharging.
        battery_soc_pct: Battery state of charge in percent (0-100).
        battery_temp_c: Battery temperature in Celsius (nullable).
        load_power_w: Household load power in watts.
        export_power_w: Grid export power in watts.
        sample_count: Number of samples aggregated (default 1).
    """

    __tablename__ = "sungrow_samples"

    device_id: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        nullable=False,
    )
    ts: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        nullable=False,
    )
    pv_power_w: Mapped[float] = mapped_column(Double, nullable=False)
    pv_daily_kwh: Mapped[float | None] = mapped_column(Double, nullable=True)
    battery_power_w: Mapped[float] = mapped_column(Double, nullable=False)
    battery_soc_pct: Mapped[float] = mapped_column(Double, nullable=False)
    battery_temp_c: Mapped[float | None] = mapped_column(Double, nullable=True)
    load_power_w: Mapped[float] = mapped_column(Double, nullable=False)
    export_power_w: Mapped[float] = mapped_column(Double, nullable=False)
    sample_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )

    def __repr__(self) -> str:
        """Return string representation of the SungrowSample."""
        return (
            f"SungrowSample(device_id={self.device_id!r}, "
            f"ts={self.ts!r}, pv_power_w={self.pv_power_w!r})"
        )
