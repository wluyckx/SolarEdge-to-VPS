"""
Initial schema: create sungrow_samples table with TimescaleDB hypertable.

Enables the TimescaleDB extension, creates the sungrow_samples table with
all required columns and composite primary key (device_id, ts), then
converts it to a TimescaleDB hypertable partitioned on the ts column
with a 7-day chunk interval.

Revision ID: 001
Revises: None
Create Date: 2026-02-14

CHANGELOG:
- 2026-02-14: Initial creation (STORY-008)

TODO:
- None
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create TimescaleDB extension and sungrow_samples hypertable.

    Steps:
        1. Enable timescaledb extension (idempotent).
        2. Create sungrow_samples table with composite PK (device_id, ts).
        3. Convert sungrow_samples to a TimescaleDB hypertable on ts column
           with 7-day chunk interval.
    """
    # AC5: Enable TimescaleDB extension.
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    # AC1, AC2, AC3: Create the sungrow_samples table with all columns
    # and composite primary key (device_id, ts).
    op.create_table(
        "sungrow_samples",
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pv_power_w", sa.Double(), nullable=False),
        sa.Column("pv_daily_kwh", sa.Double(), nullable=True),
        sa.Column("battery_power_w", sa.Double(), nullable=False),
        sa.Column("battery_soc_pct", sa.Double(), nullable=False),
        sa.Column("battery_temp_c", sa.Double(), nullable=True),
        sa.Column("load_power_w", sa.Double(), nullable=False),
        sa.Column("export_power_w", sa.Double(), nullable=False),
        sa.Column(
            "sample_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.PrimaryKeyConstraint("device_id", "ts"),
    )

    # AC6: Convert to TimescaleDB hypertable with 7-day chunk interval.
    op.execute(
        "SELECT create_hypertable("
        "'sungrow_samples', 'ts', "
        "chunk_time_interval => INTERVAL '7 days', "
        "if_not_exists => TRUE"
        ")"
    )


def downgrade() -> None:
    """Drop sungrow_samples table.

    Note: Does not drop the timescaledb extension as other tables may use it.
    """
    op.drop_table("sungrow_samples")
