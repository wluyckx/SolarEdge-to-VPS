"""
Continuous aggregates: hourly, daily, and monthly rollup views.

Creates TimescaleDB continuous aggregate materialized views for automated
rollups of sungrow_samples data. Three views (sungrow_hourly, sungrow_daily,
sungrow_monthly) aggregate PV power, battery power/SoC, load power, export
power, and sample count. Each view has an auto-refresh policy configured.

Revision ID: 002
Revises: 001
Create Date: 2026-02-14

CHANGELOG:
- 2026-02-14: Initial creation (STORY-013)

TODO:
- None
"""

from collections.abc import Sequence

from alembic import op

# Revision identifiers used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Shared SELECT columns for all continuous aggregates.
_AGG_COLUMNS = """\
    AVG(pv_power_w)       AS avg_pv_power_w,
    MAX(pv_power_w)       AS max_pv_power_w,
    AVG(battery_power_w)  AS avg_battery_power_w,
    AVG(battery_soc_pct)  AS avg_battery_soc_pct,
    AVG(load_power_w)     AS avg_load_power_w,
    AVG(export_power_w)   AS avg_export_power_w,
    SUM(sample_count)     AS sample_count"""


def _create_view_sql(view_name: str, bucket_interval: str) -> str:
    """Return the CREATE MATERIALIZED VIEW statement for a continuous aggregate."""
    return (
        f"CREATE MATERIALIZED VIEW {view_name}\n"
        f"WITH (timescaledb.continuous) AS\n"
        f"SELECT\n"
        f"    device_id,\n"
        f"    time_bucket('{bucket_interval}', ts) AS bucket,\n"
        f"{_AGG_COLUMNS}\n"
        f"FROM sungrow_samples\n"
        f"GROUP BY device_id, bucket\n"
        f"WITH NO DATA"
    )


def _add_refresh_policy_sql(
    view_name: str,
    start_offset: str,
    end_offset: str,
    schedule_interval: str,
) -> str:
    """Return the SELECT add_continuous_aggregate_policy statement."""
    return (
        f"SELECT add_continuous_aggregate_policy('{view_name}',\n"
        f"    start_offset  => INTERVAL '{start_offset}',\n"
        f"    end_offset    => INTERVAL '{end_offset}',\n"
        f"    schedule_interval => INTERVAL '{schedule_interval}'\n"
        f")"
    )


def _remove_refresh_policy_sql(view_name: str) -> str:
    """Return the SELECT remove_continuous_aggregate_policy statement."""
    return (
        f"SELECT remove_continuous_aggregate_policy('{view_name}', if_exists => TRUE)"
    )


def upgrade() -> None:
    """Create continuous aggregate views and refresh policies.

    Steps:
        1. Create sungrow_hourly continuous aggregate (1-hour buckets).
        2. Create sungrow_daily continuous aggregate (1-day buckets).
        3. Create sungrow_monthly continuous aggregate (1-month buckets).
        4. Add auto-refresh policies for all three views.
    """
    # AC1: Hourly continuous aggregate.
    op.execute(_create_view_sql("sungrow_hourly", "1 hour"))

    # AC2: Daily continuous aggregate.
    op.execute(_create_view_sql("sungrow_daily", "1 day"))

    # AC3: Monthly continuous aggregate.
    op.execute(_create_view_sql("sungrow_monthly", "1 month"))

    # AC5: Auto-refresh policies.
    op.execute(
        _add_refresh_policy_sql(
            "sungrow_hourly",
            start_offset="3 hours",
            end_offset="1 hour",
            schedule_interval="1 hour",
        )
    )
    op.execute(
        _add_refresh_policy_sql(
            "sungrow_daily",
            start_offset="3 days",
            end_offset="1 day",
            schedule_interval="1 day",
        )
    )
    op.execute(
        _add_refresh_policy_sql(
            "sungrow_monthly",
            start_offset="3 months",
            end_offset="1 month",
            schedule_interval="1 day",
        )
    )


def downgrade() -> None:
    """Remove refresh policies and drop continuous aggregate views.

    Policies must be removed before views can be dropped. Views are dropped
    in reverse order (monthly, daily, hourly).
    """
    # Remove refresh policies first.
    op.execute(_remove_refresh_policy_sql("sungrow_monthly"))
    op.execute(_remove_refresh_policy_sql("sungrow_daily"))
    op.execute(_remove_refresh_policy_sql("sungrow_hourly"))

    # Drop continuous aggregate views (CASCADE handles internal TimescaleDB objects).
    op.execute("DROP MATERIALIZED VIEW IF EXISTS sungrow_monthly CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS sungrow_daily CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS sungrow_hourly CASCADE")
