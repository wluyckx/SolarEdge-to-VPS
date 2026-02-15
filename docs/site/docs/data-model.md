---
sidebar_position: 5
title: Data Model
---

# Data Model

This page documents the telemetry sample schema and the Modbus register map that feeds it.

## SungrowSample Fields

Each telemetry sample represents a point-in-time reading from a Sungrow hybrid inverter.

| Field | Type | Unit | Nullable | Description |
|-------|------|------|----------|-------------|
| `device_id` | string | -- | No | Device identifier (matches `DEVICE_ID` on the edge or defaults to `SUNGROW_HOST`) |
| `ts` | datetime | UTC | No | Sample timestamp in ISO 8601 format |
| `pv_power_w` | float | W | No | Total DC power from all PV (MPPT) inputs |
| `pv_daily_kwh` | float | kWh | Yes | Cumulative PV energy generated today |
| `battery_power_w` | float | W | No | Battery charge/discharge power (positive = charging, negative = discharging) |
| `battery_soc_pct` | float | % | No | Battery state of charge (0--100) |
| `battery_temp_c` | float | C | Yes | Battery temperature |
| `load_power_w` | float | W | No | Total household load consumption |
| `export_power_w` | float | W | No | Grid export power (positive = exporting, negative = importing) |
| `sample_count` | int | -- | No | Number of raw samples aggregated (default 1) |

### Sign Conventions

- **battery_power_w**: Positive values indicate charging; negative values indicate discharging.
- **export_power_w**: Positive values indicate power being exported to the grid; negative values indicate power being imported from the grid.

## Modbus Register Map

The edge daemon reads registers from the Sungrow inverter via Modbus TCP (function code 0x04, input registers). Registers are defined in `edge/src/registers.py` and organized into five contiguous groups for efficient batched reads.

### Register Groups

| Group | Start Address | Word Count | Description |
|-------|--------------|------------|-------------|
| device | 4990 | 11 | Inverter identification (serial number, model code) |
| pv | 5004 | 15 | PV production and MPPT channel data |
| export | 5083 | 2 | Grid export/import power |
| load | 13008 | 10 | Household load and grid power |
| battery | 13022 | 6 | Battery power, state of charge, temperature |

### Key Registers

The following registers map directly to `SungrowSample` fields:

| Register Name | Address | Type | Scale | Unit | Maps to |
|---------------|---------|------|-------|------|---------|
| `total_dc_power` | 5004 | U32 | 1 | W | `pv_power_w` |
| `daily_pv_generation` | 5011 | U16 | 0.1 | kWh | `pv_daily_kwh` |
| `export_power` | 5083 | S32 | 1 | W | `export_power_w` |
| `load_power` | 13008 | S32 | 1 | W | `load_power_w` |
| `battery_power` | 13022 | S16 | 1 | W | `battery_power_w` |
| `battery_soc` | 13023 | U16 | 0.1 | % | `battery_soc_pct` |
| `battery_temperature` | 13024 | U16 | 0.1 | C | `battery_temp_c` |

### All Registers

#### Device Group (4990--5000)

| Address | Name | Type | Words | Scale | Unit | Range | Description |
|---------|------|------|-------|-------|------|-------|-------------|
| 4990 | `serial_number` | UTF8 | 10 | 1 | -- | -- | Inverter serial number (10 ASCII characters) |
| 5000 | `device_type_code` | U16 | 1 | 1 | -- | 0--65535 | Model identifier code |

#### PV Group (5004--5018)

| Address | Name | Type | Words | Scale | Unit | Range | Description |
|---------|------|------|-------|-------|------|-------|-------------|
| 5004 | `total_dc_power` | U32 | 2 | 1 | W | 0--20000 | Total DC power from all MPPT inputs |
| 5011 | `daily_pv_generation` | U16 | 1 | 0.1 | kWh | 0--100 | PV energy generated today |
| 5012 | `mppt1_voltage` | U16 | 1 | 0.1 | V | 0--600 | MPPT 1 DC voltage |
| 5013 | `mppt1_current` | U16 | 1 | 0.1 | A | 0--20 | MPPT 1 DC current |
| 5014 | `mppt2_voltage` | U16 | 1 | 0.1 | V | 0--600 | MPPT 2 DC voltage |
| 5015 | `mppt2_current` | U16 | 1 | 0.1 | A | 0--20 | MPPT 2 DC current |
| 5017 | `total_pv_generation` | U32 | 2 | 0.1 | kWh | 0--1000000 | Cumulative total PV energy generated |

#### Export Group (5083--5084)

| Address | Name | Type | Words | Scale | Unit | Range | Description |
|---------|------|------|-------|-------|------|-------|-------------|
| 5083 | `export_power` | S32 | 2 | 1 | W | -20000--20000 | Export power (positive = exporting, negative = importing) |

#### Load Group (13008--13017)

| Address | Name | Type | Words | Scale | Unit | Range | Description |
|---------|------|------|-------|-------|------|-------|-------------|
| 13008 | `load_power` | S32 | 2 | 1 | W | -20000--50000 | Total household load consumption |
| 13010 | `grid_power` | S16 | 1 | 1 | W | -20000--20000 | Grid power (positive = importing, negative = exporting) |
| 13017 | `daily_direct_consumption` | U16 | 1 | 0.1 | kWh | 0--200 | PV energy directly consumed today |

#### Battery Group (13022--13027)

| Address | Name | Type | Words | Scale | Unit | Range | Description |
|---------|------|------|-------|-------|------|-------|-------------|
| 13022 | `battery_power` | S16 | 1 | 1 | W | -10000--10000 | Battery power (positive = charging, negative = discharging) |
| 13023 | `battery_soc` | U16 | 1 | 0.1 | % | 0--100 | Battery state of charge |
| 13024 | `battery_temperature` | U16 | 1 | 0.1 | C | -20--60 | Battery temperature |
| 13026 | `daily_battery_discharge` | U16 | 1 | 0.1 | kWh | 0--100 | Battery energy discharged today |
| 13027 | `daily_battery_charge` | U16 | 1 | 0.1 | kWh | 0--100 | Battery energy charged today |

### Data Types

| Type | Size | Description |
|------|------|-------------|
| U16 | 1 word (16 bits) | Unsigned 16-bit integer |
| S16 | 1 word (16 bits) | Signed 16-bit integer (two's complement) |
| U32 | 2 words (32 bits) | Unsigned 32-bit integer (big-endian word order) |
| S32 | 2 words (32 bits) | Signed 32-bit integer (big-endian word order) |
| UTF8 | N words | ASCII string packed into N 16-bit words |

### Scaling

Registers with a scale factor of 0.1 store values in tenths of the engineering unit. The normalizer multiplies the raw integer by the scale factor to produce the final value. For example, a raw `battery_soc` value of 850 with scale 0.1 produces 85.0%.
