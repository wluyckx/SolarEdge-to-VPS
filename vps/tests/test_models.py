"""
Tests for the SungrowSample SQLAlchemy model.

Validates column names, column types, composite primary key, nullability,
table name, model instantiation, and repr per STORY-008 acceptance criteria.

TDD: These tests are written FIRST, before the model implementation.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-008)

TODO:
- None
"""

import datetime

from sqlalchemy import DateTime, Double, Integer, Text, inspect

from src.db.models import Base, SungrowSample


class TestSungrowSampleColumns:
    """Tests that SungrowSample model defines all required columns."""

    def test_has_device_id_column(self) -> None:
        """SungrowSample has a device_id column."""
        mapper = inspect(SungrowSample)
        column_names = [col.key for col in mapper.column_attrs]
        assert "device_id" in column_names

    def test_has_ts_column(self) -> None:
        """SungrowSample has a ts column."""
        mapper = inspect(SungrowSample)
        column_names = [col.key for col in mapper.column_attrs]
        assert "ts" in column_names

    def test_has_pv_power_w_column(self) -> None:
        """SungrowSample has a pv_power_w column."""
        mapper = inspect(SungrowSample)
        column_names = [col.key for col in mapper.column_attrs]
        assert "pv_power_w" in column_names

    def test_has_pv_daily_kwh_column(self) -> None:
        """SungrowSample has a pv_daily_kwh column."""
        mapper = inspect(SungrowSample)
        column_names = [col.key for col in mapper.column_attrs]
        assert "pv_daily_kwh" in column_names

    def test_has_battery_power_w_column(self) -> None:
        """SungrowSample has a battery_power_w column."""
        mapper = inspect(SungrowSample)
        column_names = [col.key for col in mapper.column_attrs]
        assert "battery_power_w" in column_names

    def test_has_battery_soc_pct_column(self) -> None:
        """SungrowSample has a battery_soc_pct column."""
        mapper = inspect(SungrowSample)
        column_names = [col.key for col in mapper.column_attrs]
        assert "battery_soc_pct" in column_names

    def test_has_battery_temp_c_column(self) -> None:
        """SungrowSample has a battery_temp_c column."""
        mapper = inspect(SungrowSample)
        column_names = [col.key for col in mapper.column_attrs]
        assert "battery_temp_c" in column_names

    def test_has_load_power_w_column(self) -> None:
        """SungrowSample has a load_power_w column."""
        mapper = inspect(SungrowSample)
        column_names = [col.key for col in mapper.column_attrs]
        assert "load_power_w" in column_names

    def test_has_export_power_w_column(self) -> None:
        """SungrowSample has an export_power_w column."""
        mapper = inspect(SungrowSample)
        column_names = [col.key for col in mapper.column_attrs]
        assert "export_power_w" in column_names

    def test_has_sample_count_column(self) -> None:
        """SungrowSample has a sample_count column for future weighted aggregation."""
        mapper = inspect(SungrowSample)
        column_names = [col.key for col in mapper.column_attrs]
        assert "sample_count" in column_names

    def test_total_column_count(self) -> None:
        """SungrowSample has exactly 10 columns.

        Columns: device_id, ts, pv_power_w, pv_daily_kwh, battery_power_w,
        battery_soc_pct, battery_temp_c, load_power_w, export_power_w,
        sample_count.
        """
        mapper = inspect(SungrowSample)
        column_names = [col.key for col in mapper.column_attrs]
        assert len(column_names) == 10


class TestSungrowSampleColumnTypes:
    """Tests that SungrowSample columns have correct SQLAlchemy types."""

    def test_device_id_is_text(self) -> None:
        """device_id column is Text type."""
        col = SungrowSample.__table__.columns["device_id"]
        assert isinstance(col.type, Text)

    def test_ts_is_timestamptz(self) -> None:
        """ts column is DateTime with timezone=True (TIMESTAMPTZ)."""
        col = SungrowSample.__table__.columns["ts"]
        assert isinstance(col.type, DateTime)
        assert col.type.timezone is True

    def test_pv_power_w_is_double(self) -> None:
        """pv_power_w column is Double type."""
        col = SungrowSample.__table__.columns["pv_power_w"]
        assert isinstance(col.type, Double)

    def test_pv_daily_kwh_is_double(self) -> None:
        """pv_daily_kwh column is Double type."""
        col = SungrowSample.__table__.columns["pv_daily_kwh"]
        assert isinstance(col.type, Double)

    def test_battery_power_w_is_double(self) -> None:
        """battery_power_w column is Double type."""
        col = SungrowSample.__table__.columns["battery_power_w"]
        assert isinstance(col.type, Double)

    def test_battery_soc_pct_is_double(self) -> None:
        """battery_soc_pct column is Double type."""
        col = SungrowSample.__table__.columns["battery_soc_pct"]
        assert isinstance(col.type, Double)

    def test_battery_temp_c_is_double(self) -> None:
        """battery_temp_c column is Double type."""
        col = SungrowSample.__table__.columns["battery_temp_c"]
        assert isinstance(col.type, Double)

    def test_load_power_w_is_double(self) -> None:
        """load_power_w column is Double type."""
        col = SungrowSample.__table__.columns["load_power_w"]
        assert isinstance(col.type, Double)

    def test_export_power_w_is_double(self) -> None:
        """export_power_w column is Double type."""
        col = SungrowSample.__table__.columns["export_power_w"]
        assert isinstance(col.type, Double)

    def test_sample_count_is_integer(self) -> None:
        """sample_count column is Integer type."""
        col = SungrowSample.__table__.columns["sample_count"]
        assert isinstance(col.type, Integer)


class TestSungrowSampleNullability:
    """Tests that SungrowSample columns have correct nullable settings."""

    def test_device_id_not_nullable(self) -> None:
        """device_id column is NOT NULL."""
        col = SungrowSample.__table__.columns["device_id"]
        assert col.nullable is False

    def test_ts_not_nullable(self) -> None:
        """ts column is NOT NULL."""
        col = SungrowSample.__table__.columns["ts"]
        assert col.nullable is False

    def test_pv_power_w_not_nullable(self) -> None:
        """pv_power_w column is NOT NULL."""
        col = SungrowSample.__table__.columns["pv_power_w"]
        assert col.nullable is False

    def test_pv_daily_kwh_nullable(self) -> None:
        """pv_daily_kwh column is nullable (cumulative, may be absent)."""
        col = SungrowSample.__table__.columns["pv_daily_kwh"]
        assert col.nullable is True

    def test_battery_power_w_not_nullable(self) -> None:
        """battery_power_w column is NOT NULL."""
        col = SungrowSample.__table__.columns["battery_power_w"]
        assert col.nullable is False

    def test_battery_soc_pct_not_nullable(self) -> None:
        """battery_soc_pct column is NOT NULL."""
        col = SungrowSample.__table__.columns["battery_soc_pct"]
        assert col.nullable is False

    def test_battery_temp_c_nullable(self) -> None:
        """battery_temp_c column is nullable (sensor may not report)."""
        col = SungrowSample.__table__.columns["battery_temp_c"]
        assert col.nullable is True

    def test_load_power_w_not_nullable(self) -> None:
        """load_power_w column is NOT NULL."""
        col = SungrowSample.__table__.columns["load_power_w"]
        assert col.nullable is False

    def test_export_power_w_not_nullable(self) -> None:
        """export_power_w column is NOT NULL."""
        col = SungrowSample.__table__.columns["export_power_w"]
        assert col.nullable is False

    def test_sample_count_not_nullable(self) -> None:
        """sample_count column is NOT NULL (defaults to 1)."""
        col = SungrowSample.__table__.columns["sample_count"]
        assert col.nullable is False


class TestSungrowSamplePrimaryKey:
    """Tests that SungrowSample has the correct composite primary key."""

    def test_composite_primary_key_columns(self) -> None:
        """Primary key consists of (device_id, ts)."""
        pk_columns = [col.name for col in SungrowSample.__table__.primary_key.columns]
        assert pk_columns == ["device_id", "ts"]

    def test_device_id_is_primary_key(self) -> None:
        """device_id is part of the primary key."""
        col = SungrowSample.__table__.columns["device_id"]
        assert col.primary_key is True

    def test_ts_is_primary_key(self) -> None:
        """ts is part of the primary key."""
        col = SungrowSample.__table__.columns["ts"]
        assert col.primary_key is True

    def test_pv_power_w_is_not_primary_key(self) -> None:
        """pv_power_w is NOT part of the primary key."""
        col = SungrowSample.__table__.columns["pv_power_w"]
        assert col.primary_key is False


class TestSungrowSampleTableName:
    """Tests that the table name is correct."""

    def test_table_name(self) -> None:
        """Table name is 'sungrow_samples'."""
        assert SungrowSample.__tablename__ == "sungrow_samples"


class TestSungrowSampleInstantiation:
    """Tests that SungrowSample can be instantiated with valid data."""

    def test_instantiate_with_all_fields(self) -> None:
        """SungrowSample can be created with all fields."""
        sample = SungrowSample(
            device_id="sungrow-001",
            ts=datetime.datetime(2026, 2, 14, 12, 0, 0, tzinfo=datetime.UTC),
            pv_power_w=3500.0,
            pv_daily_kwh=12.5,
            battery_power_w=-1500.0,
            battery_soc_pct=75.0,
            battery_temp_c=25.0,
            load_power_w=2000.0,
            export_power_w=0.0,
            sample_count=1,
        )
        assert sample.device_id == "sungrow-001"
        assert sample.pv_power_w == 3500.0
        assert sample.battery_soc_pct == 75.0
        assert sample.sample_count == 1

    def test_instantiate_with_required_fields_only(self) -> None:
        """SungrowSample can be created with required fields only."""
        sample = SungrowSample(
            device_id="sungrow-001",
            ts=datetime.datetime(2026, 2, 14, 12, 0, 0, tzinfo=datetime.UTC),
            pv_power_w=3500.0,
            battery_power_w=-1500.0,
            battery_soc_pct=75.0,
            load_power_w=2000.0,
            export_power_w=0.0,
            sample_count=1,
        )
        assert sample.pv_daily_kwh is None
        assert sample.battery_temp_c is None

    def test_instantiate_with_negative_battery_power(self) -> None:
        """Battery power can be negative (charging)."""
        sample = SungrowSample(
            device_id="sungrow-001",
            ts=datetime.datetime(2026, 2, 14, 12, 0, 0, tzinfo=datetime.UTC),
            pv_power_w=5000.0,
            battery_power_w=-2000.0,
            battery_soc_pct=60.0,
            load_power_w=1500.0,
            export_power_w=1500.0,
            sample_count=1,
        )
        assert sample.battery_power_w == -2000.0

    def test_instantiate_with_zero_pv(self) -> None:
        """PV power can be zero (nighttime)."""
        sample = SungrowSample(
            device_id="sungrow-001",
            ts=datetime.datetime(2026, 2, 14, 22, 0, 0, tzinfo=datetime.UTC),
            pv_power_w=0.0,
            battery_power_w=1500.0,
            battery_soc_pct=80.0,
            load_power_w=1500.0,
            export_power_w=0.0,
            sample_count=1,
        )
        assert sample.pv_power_w == 0.0


class TestSungrowSampleRepr:
    """Tests the string representation of SungrowSample."""

    def test_repr_contains_model_name(self) -> None:
        """SungrowSample repr includes the model name."""
        sample = SungrowSample(
            device_id="sungrow-001",
            ts=datetime.datetime(2026, 2, 14, 12, 0, 0, tzinfo=datetime.UTC),
            pv_power_w=3500.0,
            battery_power_w=-1500.0,
            battery_soc_pct=75.0,
            load_power_w=2000.0,
            export_power_w=0.0,
            sample_count=1,
        )
        result = repr(sample)
        assert "SungrowSample" in result

    def test_repr_contains_device_id(self) -> None:
        """SungrowSample repr includes the device_id."""
        sample = SungrowSample(
            device_id="sungrow-001",
            ts=datetime.datetime(2026, 2, 14, 12, 0, 0, tzinfo=datetime.UTC),
            pv_power_w=3500.0,
            battery_power_w=-1500.0,
            battery_soc_pct=75.0,
            load_power_w=2000.0,
            export_power_w=0.0,
            sample_count=1,
        )
        result = repr(sample)
        assert "sungrow-001" in result


class TestSungrowSampleDefaults:
    """Tests default values on SungrowSample columns."""

    def test_sample_count_has_server_default(self) -> None:
        """sample_count column has a server default of 1."""
        col = SungrowSample.__table__.columns["sample_count"]
        assert col.server_default is not None
        assert str(col.server_default.arg) == "1"


class TestBaseModel:
    """Tests that Base declarative base is properly defined."""

    def test_base_has_metadata(self) -> None:
        """Base has a metadata attribute for table definitions."""
        assert hasattr(Base, "metadata")

    def test_sungrow_sample_in_base_metadata(self) -> None:
        """SungrowSample table is registered in Base metadata."""
        table_names = list(Base.metadata.tables.keys())
        assert "sungrow_samples" in table_names
