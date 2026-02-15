---
sidebar_position: 1
title: Introduction
---

# Sungrow-to-VPS API

The Sungrow-to-VPS API is a solar telemetry service that collects, stores, and serves data from Sungrow hybrid inverters. It provides endpoints for batch ingestion of telemetry samples, real-time data retrieval, and historical time-series rollups.

## Base URL

```
https://{your-domain}/v1/
```

All versioned endpoints are served under the `/v1/` prefix. Replace `{your-domain}` with your actual deployment domain.

## Authentication

All API endpoints require Bearer token authentication, except for the internal [`GET /health`](./api/health.md) endpoint. See the [Authentication](./authentication.md) page for details on token format and configuration.

## Endpoints

| Method | Path            | Description                          |
|--------|-----------------|--------------------------------------|
| POST   | `/v1/ingest`    | Batch ingest telemetry samples       |
| GET    | `/v1/realtime`  | Latest sample for a device           |
| GET    | `/v1/series`    | Historical rollups by time frame     |
| GET    | `/health`       | Internal health check (no auth)      |

## OpenAPI Specification

The raw OpenAPI JSON specification is available at [`/openapi.json`](pathname:///openapi.json) for use with API clients and code generators.
