---
sidebar_position: 3
title: GET /v1/series
---

# GET /v1/series

Retrieve historical time-bucketed rollup data for a device. Returns aggregated metrics at different time resolutions depending on the requested frame.

## Request

**Method:** `GET`
**Path:** `/v1/series`
**Authentication:** Bearer token required

### Query Parameters

| Parameter   | Type   | Required | Description                                    |
|-------------|--------|----------|------------------------------------------------|
| `device_id` | string | Yes      | Device identifier                              |
| `frame`     | string | Yes      | Time frame: `day`, `month`, `year`, or `all`   |

## Frame Behaviour

Each frame queries a different TimescaleDB continuous aggregate view with a specific time range filter:

| Frame   | Bucket Size | Source View       | Time Filter                          |
|---------|-------------|-------------------|--------------------------------------|
| `day`   | 1 hour      | `sungrow_hourly`  | Today (from start of current day)    |
| `month` | 1 day       | `sungrow_daily`   | Current month (from start of month)  |
| `year`  | 1 month     | `sungrow_monthly` | Current year (from start of year)    |
| `all`   | 1 month     | `sungrow_monthly` | No time filter (all historical data) |

**Fallback:** If a continuous aggregate view does not exist (e.g., in a fresh development environment), the endpoint falls back to querying the raw `sungrow_samples` table with `time_bucket()` aggregation.

## Response

**Status:** `200 OK`

```json
{
  "device_id": "inverter-01",
  "frame": "day",
  "series": [
    {
      "bucket": "2026-02-15T08:00:00",
      "avg_pv_power_w": 1200.5,
      "max_pv_power_w": 2100.0,
      "avg_battery_power_w": -500.0,
      "avg_battery_soc_pct": 72.3,
      "avg_load_power_w": 1100.0,
      "avg_export_power_w": 600.5,
      "sample_count": 60
    }
  ]
}
```

### BucketOut Schema

| Field                 | Type             | Description                                   |
|-----------------------|------------------|-----------------------------------------------|
| `bucket`              | string (ISO 8601)| Start timestamp of the time bucket (UTC)      |
| `avg_pv_power_w`      | float            | Average PV production power in watts          |
| `max_pv_power_w`      | float            | Maximum PV production power in watts          |
| `avg_battery_power_w` | float            | Average battery power in watts                |
| `avg_battery_soc_pct` | float            | Average battery state of charge (0-100%)      |
| `avg_load_power_w`    | float            | Average household load power in watts         |
| `avg_export_power_w`  | float            | Average grid export power in watts            |
| `sample_count`        | integer          | Number of raw samples in the bucket           |

## Error Responses

| Status | Condition                                        | Example Detail                                                      |
|--------|--------------------------------------------------|---------------------------------------------------------------------|
| 401    | Missing or invalid Bearer token                  | `"Missing authorization credentials."`                              |
| 403    | Query `device_id` does not match authenticated device | `"Device ID does not match authenticated device."`             |
| 422    | Invalid `frame` value                            | `"Invalid frame 'week'. Must be one of: ['all', 'day', 'month', 'year']."` |

## Example

### Request

```bash
curl -X GET "https://your-domain.example.com/v1/series?device_id=inverter-01&frame=day" \
  -H "Authorization: Bearer my-secret-token"
```

### Response

```json
{
  "device_id": "inverter-01",
  "frame": "day",
  "series": [
    {
      "bucket": "2026-02-15T06:00:00",
      "avg_pv_power_w": 250.0,
      "max_pv_power_w": 800.0,
      "avg_battery_power_w": -200.0,
      "avg_battery_soc_pct": 60.5,
      "avg_load_power_w": 900.0,
      "avg_export_power_w": 0.0,
      "sample_count": 12
    },
    {
      "bucket": "2026-02-15T07:00:00",
      "avg_pv_power_w": 1500.0,
      "max_pv_power_w": 2400.0,
      "avg_battery_power_w": -800.0,
      "avg_battery_soc_pct": 68.0,
      "avg_load_power_w": 1050.0,
      "avg_export_power_w": 450.0,
      "sample_count": 60
    },
    {
      "bucket": "2026-02-15T08:00:00",
      "avg_pv_power_w": 3200.0,
      "max_pv_power_w": 4100.0,
      "avg_battery_power_w": -1200.0,
      "avg_battery_soc_pct": 78.5,
      "avg_load_power_w": 1200.0,
      "avg_export_power_w": 800.0,
      "sample_count": 60
    }
  ]
}
```
