---
sidebar_position: 9
title: Configuration
---

# Configuration Reference

All configuration is done through environment variables. Variables are grouped by component.

## Edge Daemon

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SUNGROW_HOST` | Yes | -- | WiNet-S IP address or hostname |
| `VPS_BASE_URL` | Yes | -- | VPS API base URL (must start with `https://`) |
| `VPS_DEVICE_TOKEN` | Yes | -- | Bearer token for VPS authentication |
| `SUNGROW_PORT` | No | `502` | Modbus TCP port |
| `SUNGROW_SLAVE_ID` | No | `1` | Modbus slave ID |
| `POLL_INTERVAL_S` | No | `5` | Seconds between poll cycles |
| `INTER_REGISTER_DELAY_MS` | No | `20` | Milliseconds between register group reads |
| `DEVICE_ID` | No | Value of `SUNGROW_HOST` | Device identifier sent with samples |
| `BATCH_SIZE` | No | `30` | Maximum samples per upload request |
| `UPLOAD_INTERVAL_S` | No | `10` | Seconds between upload attempts |
| `SPOOL_PATH` | No | `/data/spool.db` | Path to the SQLite spool database file |

### Validation Rules

| Variable | Rule |
|----------|------|
| `SUNGROW_HOST` | Non-empty string |
| `VPS_BASE_URL` | Must begin with `https://` |
| `VPS_DEVICE_TOKEN` | Non-empty string |
| `SUNGROW_PORT` | Integer, 1--65535 |
| `SUNGROW_SLAVE_ID` | Integer, 1--247 |
| `POLL_INTERVAL_S` | Integer, minimum 5 |
| `INTER_REGISTER_DELAY_MS` | Integer, minimum 0 |
| `BATCH_SIZE` | Integer, 1--1000 |
| `UPLOAD_INTERVAL_S` | Integer, minimum 1 |

## VPS API

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | -- | PostgreSQL async connection URL (e.g., `postgresql+asyncpg://user:pass@host/db`) |
| `REDIS_URL` | Yes | -- | Redis connection URL (e.g., `redis://redis:6379/0`) |
| `DEVICE_TOKENS` | Yes | -- | Comma-separated `token:device_id` pairs |
| `CACHE_TTL_S` | No | `5` | Redis cache TTL in seconds |
| `MAX_SAMPLES_PER_REQUEST` | No | `1000` | Maximum number of samples per ingest request |
| `MAX_REQUEST_BYTES` | No | `1048576` | Maximum request body size in bytes (default 1 MB) |

### Validation Rules

| Variable | Rule |
|----------|------|
| `DATABASE_URL` | Non-empty string; must be a valid async PostgreSQL URL |
| `REDIS_URL` | Non-empty string; must be a valid Redis URL |
| `DEVICE_TOKENS` | At least one `token:device_id` pair; each pair separated by commas; each pair contains exactly one colon |
| `CACHE_TTL_S` | Integer, minimum 1 |
| `MAX_SAMPLES_PER_REQUEST` | Integer, minimum 1 |
| `MAX_REQUEST_BYTES` | Integer, minimum 1 |

### DEVICE_TOKENS Format

```
DEVICE_TOKENS=abc123:inverter-01,def456:inverter-02
```

Each pair maps a Bearer token to a device ID. The token is the string before the colon; the device ID is the string after. Multiple pairs are separated by commas.

## Infrastructure

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTGRES_PASSWORD` | Yes | -- | Password for the PostgreSQL superuser |

### Validation Rules

| Variable | Rule |
|----------|------|
| `POSTGRES_PASSWORD` | Non-empty string |

## Example `.env` File

```bash
# Edge daemon
SUNGROW_HOST=192.168.1.100
VPS_BASE_URL=https://solar.example.com
VPS_DEVICE_TOKEN=abc123
SUNGROW_PORT=502
SUNGROW_SLAVE_ID=1
POLL_INTERVAL_S=5
BATCH_SIZE=30
UPLOAD_INTERVAL_S=10

# VPS API
DATABASE_URL=postgresql+asyncpg://postgres:secret@postgres:5432/sungrow
REDIS_URL=redis://redis:6379/0
DEVICE_TOKENS=abc123:inverter-01
CACHE_TTL_S=5
MAX_SAMPLES_PER_REQUEST=1000
MAX_REQUEST_BYTES=1048576

# Infrastructure
POSTGRES_PASSWORD=secret
```
