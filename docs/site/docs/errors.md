---
sidebar_position: 5
title: Error Reference
---

# Error Reference

All error responses follow a consistent JSON format with a `detail` field describing the error. Validation errors (422) include a structured array of field-level issues.

## 400 Bad Request

Returned when the `Content-Length` header is present but malformed (non-integer value).

```json
{
  "detail": "Invalid Content-Length header."
}
```

## 401 Unauthorized

Returned when the `Authorization` header is missing or the Bearer token is not recognised. The response includes a `WWW-Authenticate: Bearer` header.

**Missing credentials:**

```json
{
  "detail": "Missing authorization credentials."
}
```

**Invalid token:**

```json
{
  "detail": "Invalid or expired token."
}
```

## 403 Forbidden

Returned when the Bearer token is valid but the requested `device_id` does not match the device bound to the token.

**On ingest (sample device_id mismatch):**

```json
{
  "detail": "Sample device ID does not match authenticated device."
}
```

**On realtime/series (query device_id mismatch):**

```json
{
  "detail": "Device ID does not match authenticated device."
}
```

## 404 Not Found

Returned when no data exists for the requested device (on the realtime endpoint).

```json
{
  "detail": "No data found for device_id 'inverter-01'."
}
```

## 413 Payload Too Large

Returned when the request body or batch size exceeds configured limits. Only applies to `POST /v1/ingest`.

**Request body exceeds `MAX_REQUEST_BYTES` (default 1 MB):**

```json
{
  "detail": "Request body exceeds limit of 1048576 bytes."
}
```

**Batch size exceeds `MAX_SAMPLES_PER_REQUEST` (default 1000):**

```json
{
  "detail": "Batch size 1500 exceeds limit of 1000. Split into smaller batches."
}
```

## 422 Unprocessable Entity

Returned when request validation fails. This includes missing required fields, invalid data types, or invalid parameter values.

**Pydantic validation error (missing required fields):**

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["samples", 0, "pv_power_w"],
      "msg": "Field required"
    }
  ]
}
```

**Invalid frame parameter (on series endpoint):**

```json
{
  "detail": "Invalid frame 'week'. Must be one of: ['all', 'day', 'month', 'year']."
}
```
