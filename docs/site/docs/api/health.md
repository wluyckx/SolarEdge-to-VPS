---
sidebar_position: 4
title: GET /health
---

# GET /health

Internal health check endpoint used by Docker HEALTHCHECK. This endpoint is **not proxied via Caddy** and is only accessible within the Docker network.

## Request

**Method:** `GET`
**Path:** `/health`
**Authentication:** None required

:::warning Internal Only
This endpoint is not exposed to the public internet. It is only accessible from within the Docker network (e.g., by the Docker daemon for health checks or by other containers).
:::

## Response

**Status:** `200 OK`

```json
{
  "status": "ok"
}
```

## Usage

The endpoint is referenced in the Dockerfile `HEALTHCHECK` instruction:

```dockerfile
HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1
```

## Root Endpoint

The API also exposes a `GET /` root endpoint that returns the same response:

```json
{
  "status": "ok"
}
```

This root endpoint does **not** require authentication but, unlike `/health`, it **is** accessible through the Caddy reverse proxy.
