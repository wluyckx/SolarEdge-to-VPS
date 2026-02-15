---
sidebar_position: 12
title: Security
---

# Security

This page documents the security controls in the Sungrow-to-VPS system.

## HTTPS-Only Boundary

All traffic between the edge daemon and the VPS is encrypted via HTTPS. A VPS-wide Caddy instance terminates TLS and automatically provisions Let's Encrypt certificates. Caddy runs as a separate Docker service shared across all projects on the VPS, reverse-proxying to the API container's exposed port 8000.

The edge daemon validates that `VPS_BASE_URL` starts with `https://` at startup. Plain HTTP URLs are rejected.

```mermaid
flowchart LR
    EDGE["Edge Daemon"] -->|HTTPS / TLS 1.2+| CADDY["Caddy\n(VPS-wide)"]
    CADDY -->|HTTP (Docker network)| API["FastAPI"]
```

The internal connection between Caddy and FastAPI is plain HTTP, but it occurs entirely within the Docker network and is not exposed to the internet.

## Bearer Token Authentication

All API endpoints under `/v1/` require a Bearer token in the `Authorization` header:

```
Authorization: Bearer <token>
```

### Token Validation

- Tokens are compared using **constant-time comparison** (`hmac.compare_digest`) to prevent timing-based side-channel attacks.
- Each token is bound to a specific `device_id`. A valid token can only access data for its own device.
- Token-to-device mapping is defined in the `DEVICE_TOKENS` environment variable at startup.

### Device Ownership

On every request, the API validates that the `device_id` in the request body or query parameter matches the device bound to the authenticated token. Mismatches return `403 Forbidden`.

## /health Endpoint Exclusion

The `GET /health` endpoint should **not be proxied through Caddy** to the public internet. The VPS-wide Caddy configuration should only proxy API paths (e.g., `/v1/*`), keeping `/health` accessible only within the Docker network for Docker HEALTHCHECK and internal monitoring.

The `GET /` root endpoint is accessible through Caddy but does not require authentication and returns only `{"status": "ok"}`.

## Non-Root Containers

Both the edge daemon and the VPS API containers run as a non-root user (`appuser`). This limits the blast radius of any container escape vulnerability:

- The application cannot modify system files or install packages.
- The application cannot access other containers' filesystems.
- Host-level damage from a compromised container is minimized.

## Idempotent Ingestion as DoS Mitigation

The `POST /v1/ingest` endpoint uses `ON CONFLICT (device_id, ts) DO NOTHING` when inserting samples. This means:

- **Replay attacks** do not create duplicate data. An attacker replaying captured requests cannot inflate storage usage or corrupt aggregates.
- **Accidental retries** from the edge daemon are safe. The same batch can be submitted multiple times without side effects.
- The `inserted` count in the response reflects only newly inserted rows, giving the caller visibility into what was actually new.

## Request Size Limits

Two limits protect against memory-pressure denial-of-service attacks on the ingest endpoint:

| Limit | Default | Description |
|-------|---------|-------------|
| `MAX_REQUEST_BYTES` | 1,048,576 (1 MB) | Maximum HTTP request body size |
| `MAX_SAMPLES_PER_REQUEST` | 1,000 | Maximum number of samples per batch |

Requests exceeding either limit receive `413 Payload Too Large` before any database interaction occurs. The body size check happens early in the request lifecycle, before JSON parsing, to prevent large payloads from consuming memory.

## No Secret Logging

The VPS API logs a configuration summary at startup for operational visibility, but explicitly omits sensitive values:

- `DEVICE_TOKENS` values are not logged. Only the number of configured devices is logged.
- `DATABASE_URL` password components are not logged.
- The edge daemon does not log `VPS_DEVICE_TOKEN`.

This ensures that secrets do not leak into log aggregation systems or container stdout.
