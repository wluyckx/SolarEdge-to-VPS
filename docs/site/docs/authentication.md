---
sidebar_position: 2
title: Authentication
---

# Authentication

All API endpoints under `/v1/` require Bearer token authentication. The internal `/health` endpoint does not require authentication.

## Bearer Token Format

Include the token in the `Authorization` header:

```
Authorization: Bearer <token>
```

## Token Configuration

Tokens are configured on the server via the `DEVICE_TOKENS` environment variable. The format is a comma-separated list of `token:device_id` pairs:

```
DEVICE_TOKENS=token1:device1,token2:device2
```

Each token is bound to a specific `device_id`. A token can only access data for its associated device.

## Device Ownership

When making API requests, the `device_id` in the request (whether in the body or query parameter) must match the `device_id` associated with the Bearer token. If there is a mismatch, the API returns `403 Forbidden`.

## Error Responses

### 401 Unauthorized

Returned when the token is missing or invalid.

**Missing token:**

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

The response includes a `WWW-Authenticate: Bearer` header.

### 403 Forbidden

Returned when the token is valid but the requested `device_id` does not match the device bound to the token.

```json
{
  "detail": "Device ID does not match authenticated device."
}
```

## Example

```bash
curl -X GET "https://your-domain.example.com/v1/realtime?device_id=inverter-01" \
  -H "Authorization: Bearer my-secret-token"
```
