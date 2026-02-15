---
sidebar_position: 1
title: POST /v1/ingest
---

# POST /v1/ingest

Batch ingest telemetry samples from a Sungrow inverter. Samples are inserted into the TimescaleDB hypertable with idempotent conflict handling.

## Request

**Method:** `POST`
**Path:** `/v1/ingest`
**Content-Type:** `application/json`
**Authentication:** Bearer token required

### Request Body

```json
{
  "samples": [
    {
      "device_id": "inverter-01",
      "ts": "2026-02-15T10:30:00Z",
      "pv_power_w": 3450.5,
      "pv_daily_kwh": 12.3,
      "battery_power_w": -1200.0,
      "battery_soc_pct": 85.0,
      "battery_temp_c": 28.5,
      "load_power_w": 1500.0,
      "export_power_w": 750.5,
      "sample_count": 1
    }
  ]
}
```

### SampleIn Schema

| Field              | Type             | Required | Default | Description                              |
|--------------------|------------------|----------|---------|------------------------------------------|
| `device_id`        | string           | Yes      | --      | Device identifier                        |
| `ts`               | datetime (ISO 8601) | Yes   | --      | Sample timestamp (UTC)                   |
| `pv_power_w`       | float            | Yes      | --      | PV production power in watts             |
| `pv_daily_kwh`     | float \| null    | No       | null    | Cumulative PV energy today in kWh        |
| `battery_power_w`  | float            | Yes      | --      | Battery power in watts (negative = charging) |
| `battery_soc_pct`  | float            | Yes      | --      | Battery state of charge (0-100%)         |
| `battery_temp_c`   | float \| null    | No       | null    | Battery temperature in Celsius           |
| `load_power_w`     | float            | Yes      | --      | Household load power in watts            |
| `export_power_w`   | float            | Yes      | --      | Grid export power in watts               |
| `sample_count`     | integer          | No       | 1       | Number of raw samples aggregated         |

## Limits

| Limit                     | Default    | Error Code |
|---------------------------|------------|------------|
| `MAX_SAMPLES_PER_REQUEST` | 1000       | 413        |
| `MAX_REQUEST_BYTES`       | 1,048,576 (1 MB) | 413  |

Both limits are configurable via environment variables. When either limit is exceeded, the API returns `413 Payload Too Large`.

## Idempotency

The insert uses `ON CONFLICT DO NOTHING` on the `(device_id, ts)` composite key. This means:

- Duplicate samples (same device and timestamp) are silently skipped.
- The `inserted` count in the response reflects only newly inserted rows.
- It is safe to retry failed requests without creating duplicate data.

## Response

**Status:** `200 OK`

```json
{
  "inserted": 1
}
```

The `inserted` field indicates how many new rows were actually written. If all samples were duplicates, `inserted` will be `0`.

## Error Responses

| Status | Condition                                           | Example Detail                                              |
|--------|-----------------------------------------------------|-------------------------------------------------------------|
| 400    | Malformed `Content-Length` header                    | `"Invalid Content-Length header."`                           |
| 401    | Missing or invalid Bearer token                     | `"Missing authorization credentials."`                      |
| 403    | Sample `device_id` does not match authenticated device | `"Sample device ID does not match authenticated device."` |
| 413    | Request body exceeds `MAX_REQUEST_BYTES`            | `"Request body exceeds limit of 1048576 bytes."`            |
| 413    | Batch size exceeds `MAX_SAMPLES_PER_REQUEST`        | `"Batch size 1500 exceeds limit of 1000. Split into smaller batches."` |
| 422    | Validation error (missing fields, invalid types)    | Pydantic validation error array                             |

## Example

### Request

```bash
curl -X POST "https://your-domain.example.com/v1/ingest" \
  -H "Authorization: Bearer my-secret-token" \
  -H "Content-Type: application/json" \
  -d '{
    "samples": [
      {
        "device_id": "inverter-01",
        "ts": "2026-02-15T10:30:00Z",
        "pv_power_w": 3450.5,
        "pv_daily_kwh": 12.3,
        "battery_power_w": -1200.0,
        "battery_soc_pct": 85.0,
        "battery_temp_c": 28.5,
        "load_power_w": 1500.0,
        "export_power_w": 750.5,
        "sample_count": 1
      },
      {
        "device_id": "inverter-01",
        "ts": "2026-02-15T10:31:00Z",
        "pv_power_w": 3500.0,
        "battery_power_w": -1100.0,
        "battery_soc_pct": 86.0,
        "load_power_w": 1600.0,
        "export_power_w": 800.0
      }
    ]
  }'
```

### Response

```json
{
  "inserted": 2
}
```
