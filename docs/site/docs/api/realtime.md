---
sidebar_position: 2
title: GET /v1/realtime
---

# GET /v1/realtime

Retrieve the most recent telemetry sample for a device. Results are cached in Redis for fast repeated access.

## Request

**Method:** `GET`
**Path:** `/v1/realtime`
**Authentication:** Bearer token required

### Query Parameters

| Parameter   | Type   | Required | Description        |
|-------------|--------|----------|--------------------|
| `device_id` | string | Yes      | Device identifier  |

## Caching Behaviour

Responses are cached in Redis with the key `realtime:{device_id}` and a configurable TTL.

| Setting       | Default | Description                      |
|---------------|---------|----------------------------------|
| `CACHE_TTL_S` | 5       | Cache time-to-live in seconds    |

**Best-effort caching:** If Redis is unavailable, the endpoint falls back to a direct database query. Redis failures are logged but do not cause request failures.

The cache is invalidated implicitly by TTL expiry. After new data is ingested, the cached value will be replaced on the next request after the TTL expires.

## Response

**Status:** `200 OK`

### SungrowSample Response Fields

| Field              | Type             | Description                              |
|--------------------|------------------|------------------------------------------|
| `device_id`        | string           | Device identifier                        |
| `ts`               | string (ISO 8601)| Sample timestamp (UTC)                   |
| `pv_power_w`       | float            | PV production power in watts             |
| `pv_daily_kwh`     | float \| null    | Cumulative PV energy today in kWh        |
| `battery_power_w`  | float            | Battery power in watts (negative = charging) |
| `battery_soc_pct`  | float            | Battery state of charge (0-100%)         |
| `battery_temp_c`   | float \| null    | Battery temperature in Celsius           |
| `load_power_w`     | float            | Household load power in watts            |
| `export_power_w`   | float            | Grid export power in watts               |
| `sample_count`     | integer          | Number of raw samples aggregated         |

### Example Response

```json
{
  "device_id": "inverter-01",
  "ts": "2026-02-15T10:30:00",
  "pv_power_w": 3450.5,
  "pv_daily_kwh": 12.3,
  "battery_power_w": -1200.0,
  "battery_soc_pct": 85.0,
  "battery_temp_c": 28.5,
  "load_power_w": 1500.0,
  "export_power_w": 750.5,
  "sample_count": 1
}
```

## Error Responses

| Status | Condition                                        | Example Detail                                     |
|--------|--------------------------------------------------|----------------------------------------------------|
| 401    | Missing or invalid Bearer token                  | `"Missing authorization credentials."`             |
| 403    | Query `device_id` does not match authenticated device | `"Device ID does not match authenticated device."` |
| 404    | No data exists for the requested device          | `"No data found for device_id 'inverter-01'."`     |

## Example

### Request

```bash
curl -X GET "https://your-domain.example.com/v1/realtime?device_id=inverter-01" \
  -H "Authorization: Bearer my-secret-token"
```

### Response

```json
{
  "device_id": "inverter-01",
  "ts": "2026-02-15T10:30:00",
  "pv_power_w": 3450.5,
  "pv_daily_kwh": 12.3,
  "battery_power_w": -1200.0,
  "battery_soc_pct": 85.0,
  "battery_temp_c": 28.5,
  "load_power_w": 1500.0,
  "export_power_w": 750.5,
  "sample_count": 1
}
```
