---
sidebar_position: 10
title: Deployment
---

# Deployment Guide

This guide covers deploying both the edge daemon (on a Raspberry Pi or similar device) and the VPS stack (API, database, cache, and reverse proxy).

## Prerequisites

- **Docker** and **docker-compose** installed on both the edge device and the VPS.
- A **domain name** with DNS A record pointing to the VPS public IP address (required for automatic TLS).
- Network access from the edge device to the Sungrow inverter's WiNet-S dongle on the local network.
- Network access from the edge device to the VPS over the internet (port 443).

## VPS Deployment

### 1. Prepare Environment

```bash
cp .env.example .env
```

Edit `.env` and fill in all required values. See the [Configuration](./configuration.md) reference for details on each variable.

At minimum, set:

- `DATABASE_URL` -- PostgreSQL connection string
- `REDIS_URL` -- Redis connection string
- `DEVICE_TOKENS` -- at least one `token:device_id` pair
- `POSTGRES_PASSWORD` -- PostgreSQL password
- `DOMAIN` -- your public domain name

### 2. Generate Device Tokens

Generate cryptographically secure tokens for each device:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Format as `token:device_id` pairs in the `DEVICE_TOKENS` variable:

```bash
DEVICE_TOKENS=Xt7k...abc:inverter-01,Yp9m...def:inverter-02
```

Use the same token value for the corresponding edge daemon's `VPS_DEVICE_TOKEN`.

### 3. Start Services

```bash
cd vps
docker-compose up -d
```

This starts four containers:

| Container | Role |
|-----------|------|
| `api` | FastAPI application on port 8000 (internal) |
| `postgres` | TimescaleDB on port 5432 (internal) |
| `redis` | Redis on port 6379 (internal) |
| `caddy` | Reverse proxy on ports 80 and 443 (public) |

Caddy automatically provisions a TLS certificate from Let's Encrypt for the configured `DOMAIN`. HTTPS is available within minutes of the first start.

### 4. Verify VPS

```bash
# Check all containers are running
docker-compose ps

# Check API health (from the VPS itself)
curl http://localhost:8000/health

# Check HTTPS access (from any machine)
curl https://your-domain.example.com/
```

## Edge Deployment

### 1. Build the Image

On the Raspberry Pi (ARM64 native build):

```bash
docker build -t sungrow-edge edge/
```

For cross-architecture builds (e.g., building ARM64 on an x86 workstation):

```bash
docker buildx build --platform linux/arm64 -t sungrow-edge edge/
```

### 2. Prepare Environment

Create an `.env` file for the edge daemon with at minimum:

```bash
SUNGROW_HOST=192.168.1.100
VPS_BASE_URL=https://solar.example.com
VPS_DEVICE_TOKEN=Xt7k...abc
```

The `VPS_DEVICE_TOKEN` must match one of the tokens in the VPS `DEVICE_TOKENS` variable.

### 3. Run the Container

```bash
docker run -d \
  --name sungrow-edge \
  --restart unless-stopped \
  -v spool:/data \
  --env-file .env \
  sungrow-edge
```

The `-v spool:/data` mount persists the SQLite spool database across container restarts, ensuring no data loss during upgrades or reboots.

### 4. Verify Edge

```bash
# Check container is running
docker ps | grep sungrow-edge

# Check logs for successful polls
docker logs sungrow-edge --tail 20

# Check health file
docker exec sungrow-edge cat /data/health.json
```

## Initial Setup Checklist

- [ ] VPS: DNS A record points to VPS IP
- [ ] VPS: `.env` file populated with all required variables
- [ ] VPS: `docker-compose up -d` -- all four containers running
- [ ] VPS: `curl https://your-domain/` returns `{"status": "ok"}`
- [ ] Edge: `.env` file populated with `SUNGROW_HOST`, `VPS_BASE_URL`, `VPS_DEVICE_TOKEN`
- [ ] Edge: WiNet-S dongle reachable from edge device (`ping $SUNGROW_HOST`)
- [ ] Edge: Docker container running with spool volume mounted
- [ ] Edge: Logs show successful polls and uploads
- [ ] Edge: `/data/health.json` shows recent timestamps and `spool_count` near zero
