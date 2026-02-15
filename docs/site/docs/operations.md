---
sidebar_position: 11
title: Operations
---

# Operational Runbook

This page covers health monitoring, common failure modes, and recovery procedures for the Sungrow-to-VPS system.

## Health Checks

### Edge Health

The edge daemon writes `/data/health.json` after each successful poll and upload:

```json
{
  "last_poll_ts": "2026-02-15T10:30:00Z",
  "last_upload_ts": "2026-02-15T10:30:05Z",
  "spool_count": 0
}
```

**What to watch:**

| Indicator | Healthy | Unhealthy |
|-----------|---------|-----------|
| `last_poll_ts` | Within 2x `POLL_INTERVAL_S` of now | Stale by minutes or more |
| `last_upload_ts` | Within 2x `UPLOAD_INTERVAL_S` of now | Stale by minutes or more |
| `spool_count` | 0 or low single digits | Growing steadily over time |

A growing `spool_count` combined with a stale `last_upload_ts` indicates the upload loop is failing. Check VPS connectivity and edge logs.

### VPS Health

The VPS API exposes `GET /health` on port 8000 (internal only, not proxied through Caddy). The Docker HEALTHCHECK uses this endpoint:

```bash
curl -f http://localhost:8000/health
# Returns: {"status": "ok"}
```

Check container health status:

```bash
docker-compose ps
# Look for "(healthy)" in the STATUS column
```

## Common Failure Modes

### Modbus Timeout

**Symptoms:** Edge logs show connection timeout or "ModbusException" errors. `last_poll_ts` in health file stops updating. No new samples appear in the spool.

**Causes:**
- WiNet-S dongle is unreachable (network issue, power loss, Wi-Fi disconnect).
- Incorrect `SUNGROW_HOST` or `SUNGROW_PORT`.
- Inverter is shut down (e.g., nighttime with no battery backup to the dongle).

**Troubleshooting:**
1. Ping the WiNet-S dongle: `ping $SUNGROW_HOST`
2. Test Modbus connectivity: `nc -zv $SUNGROW_HOST 502`
3. Check edge daemon logs: `docker logs sungrow-edge --tail 50`
4. Verify `SUNGROW_HOST` and `SUNGROW_PORT` in the edge `.env` file.
5. Power-cycle the WiNet-S dongle if the network is reachable but Modbus is not responding.

The poll loop automatically retries on the next interval. No manual intervention is needed once the underlying connectivity is restored.

### Spool Growth

**Symptoms:** `spool_count` in `/data/health.json` increases over time. `last_upload_ts` is stale. Edge logs show upload errors (HTTP 5xx, connection refused, timeout).

**Causes:**
- VPS is unreachable (network outage, VPS down, DNS failure).
- VPS API is returning errors (database down, misconfiguration).
- Bearer token mismatch between edge `VPS_DEVICE_TOKEN` and VPS `DEVICE_TOKENS`.

**Troubleshooting:**
1. From the edge device, test VPS connectivity: `curl https://your-domain.example.com/`
2. Check edge logs for HTTP status codes: `docker logs sungrow-edge --tail 50`
3. If 401/403 errors: verify `VPS_DEVICE_TOKEN` matches a token in `DEVICE_TOKENS`.
4. If connection refused: check VPS containers are running (`docker-compose ps`).
5. If DNS failure: verify the domain resolves correctly.

Once the VPS is reachable again, the upload loop automatically drains the spool backlog. No manual intervention is needed.

### Redis Unavailability

**Symptoms:** VPS API logs show Redis connection warnings. The `/v1/realtime` endpoint is slower than usual (hitting the database on every request instead of the cache).

**Impact:** The API remains fully functional. Redis is best-effort -- all endpoints continue to work by falling back to direct database queries. The only impact is increased database load and slightly higher latency on the realtime endpoint.

**Troubleshooting:**
1. Check Redis container status: `docker-compose ps redis`
2. Check Redis logs: `docker-compose logs redis --tail 20`
3. Test Redis connectivity from the API container: `docker-compose exec api python -c "import redis; r = redis.from_url('$REDIS_URL'); r.ping()"`
4. Restart Redis if needed: `docker-compose restart redis`

### Database Connection Loss

**Symptoms:** Ingest returns HTTP 500. Realtime and series endpoints fail. VPS API logs show database connection errors. Docker HEALTHCHECK may still pass (it only checks the `/health` endpoint, which does not query the database).

**Causes:**
- PostgreSQL container crashed or was stopped.
- `DATABASE_URL` is incorrect.
- Database disk is full.

**Troubleshooting:**
1. Check PostgreSQL container status: `docker-compose ps postgres`
2. Check PostgreSQL logs: `docker-compose logs postgres --tail 30`
3. Check disk space: `docker-compose exec postgres df -h /var/lib/postgresql/data`
4. Restart if needed: `docker-compose restart postgres`
5. Verify `DATABASE_URL` in `.env`.

During a database outage, the edge spool grows. Once the database is restored, the backlog drains automatically.

### 413 Payload Too Large Errors

**Symptoms:** Edge upload logs show HTTP 413 responses. Samples accumulate in the spool.

**Causes:**
- `BATCH_SIZE` on the edge exceeds `MAX_SAMPLES_PER_REQUEST` on the VPS.
- Individual request body exceeds `MAX_REQUEST_BYTES`.

**Fix:** Ensure `BATCH_SIZE` (edge) is less than or equal to `MAX_SAMPLES_PER_REQUEST` (VPS). The default edge `BATCH_SIZE` of 30 is well within the default VPS limit of 1000.

## Log Interpretation

Both the edge daemon and the VPS API emit structured JSON logs.

### Edge Log Format

```json
{"ts": "2026-02-15T10:30:00.123Z", "level": "INFO", "logger": "poller", "msg": "Poll completed"}
```

### Key Log Events

| Logger | Level | Message | Meaning |
|--------|-------|---------|---------|
| poller | INFO | Poll completed | Successful Modbus read and spool enqueue |
| poller | ERROR | Poll failed | Modbus read error (timeout, connection refused) |
| uploader | INFO | Upload completed | Batch successfully sent to VPS |
| uploader | WARNING | Upload failed | HTTP error or connection failure; will retry |
| uploader | INFO | Backoff | Exponential backoff delay before next retry |
| main | INFO | Shutdown | Graceful shutdown initiated |
| main | INFO | Final flush | Final upload attempt during shutdown |

## Recovery Procedures

### Restart Edge Daemon

```bash
docker restart sungrow-edge
```

The daemon picks up where it left off. Spooled samples are preserved in the Docker volume.

### Restart VPS Stack

```bash
cd vps
docker-compose restart
```

Or to recreate containers (e.g., after a config change):

```bash
docker-compose up -d --force-recreate
```

### Clear Edge Spool (Emergency)

Only use this if the spool database is corrupted. This deletes all unuploaded samples.

```bash
docker stop sungrow-edge
docker run --rm -v spool:/data alpine rm /data/spool.db
docker start sungrow-edge
```

### Force Certificate Renewal

Caddy handles certificate renewal automatically. To force a renewal:

```bash
docker-compose restart caddy
```
