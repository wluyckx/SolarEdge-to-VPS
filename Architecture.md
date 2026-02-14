# Architecture.md — Sungrow-to-VPS Pipeline

**Last Updated**: 2026-02-14

---

## Overview

A standalone data collection and forwarding pipeline that reads real-time solar, battery, and load telemetry from a **Sungrow SH4.0RS hybrid inverter** (via WiNet-S Modbus TCP dongle) on a home LAN, normalizes and buffers the data on an edge device, and pushes it to a remote VPS for storage and exposure through REST API endpoints.

**Primary Goal**: Capture and persist Sungrow inverter telemetry (PV production, battery state, load consumption, inverter status) with no data loss, making it available for historical analysis and real-time monitoring.

**Companion Project**: This pipeline is fully standalone from the [P1-Edge-VPS](../P1-Edge-VPS/) project, which handles HomeWizard P1 grid data. Both follow the same architecture patterns (poller → normalizer → spool → HTTPS uploader → FastAPI → TimescaleDB) but operate independently with separate VPS deployments.

---

## Tech Stack

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Language | Python | 3.12+ | All components |
| Modbus Client | pymodbus | >=3.6 | Async Modbus TCP communication with WiNet-S |
| Edge HTTP Client | httpx | latest | Async HTTPS batch upload to VPS |
| Edge Buffer | SQLite (aiosqlite) | latest | Persistent spool for readings (WAL mode) |
| Edge Config | pydantic-settings | latest | Environment variable configuration |
| Edge Validation | pydantic | >=2.0 | Data model validation |
| VPS Framework | FastAPI | latest | REST API |
| VPS Server | uvicorn | latest | ASGI server |
| VPS Database | PostgreSQL + TimescaleDB | pg16 + latest | Time-series storage with continuous aggregates |
| VPS DB Driver | asyncpg | latest | Async PostgreSQL driver |
| VPS ORM | SQLAlchemy | 2.x | Async ORM |
| VPS Cache | Redis | 7-alpine | Realtime cache |
| VPS Migrations | Alembic | latest | Database schema migrations |
| VPS Reverse Proxy | Caddy | 2 | Auto-HTTPS, TLS termination |
| Testing | pytest + pytest-asyncio | latest | Test framework |
| Mocking | pytest-mock | latest | Mock framework |
| Linting | ruff | latest | Linting and formatting |

### Dependencies NOT in Tech Stack (Forbidden Without ADR)
Any package not listed above requires an Architecture Proposal before use.

---

## Directory Structure

```
SolarEdge-to-VPS/
├── CLAUDE.md                           # Agent workflow rules
├── Architecture.md                     # This file
├── SKILL.md                            # Security guidelines (VibeSec)
├── docs/
│   ├── BACKLOG.md                      # Stories and requirements (XML)
│   └── stories/                        # Detailed story files per phase
│       ├── phase-1-edge-foundation.md
│       ├── phase-2-vps-ingestion.md
│       ├── phase-3-api-features.md
│       └── phase-4-production.md
├── edge/                               # Runs on Raspberry Pi / edge device
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py                     # Asyncio entrypoint, runs poll + upload loops
│   │   ├── config.py                   # Pydantic Settings (env var config)
│   │   ├── registers.py                # Sungrow Modbus register map (single source of truth)
│   │   ├── poller.py                   # Modbus TCP poller (pymodbus async)
│   │   ├── normalizer.py               # Raw registers → SungrowSample (pure function)
│   │   ├── spool.py                    # SQLite ring buffer (WAL mode)
│   │   ├── uploader.py                 # HTTPS batch uploader with exponential backoff
│   │   └── health.py                   # Health file writer
│   └── tests/
│       ├── conftest.py
│       ├── fixtures/
│       │   └── modbus_responses.json   # Known register response data
│       ├── test_config.py
│       ├── test_registers.py
│       ├── test_poller.py
│       ├── test_normalizer.py
│       ├── test_spool.py
│       ├── test_uploader.py
│       ├── test_main.py
│       └── test_health.py
├── vps/                                # Runs on VPS (Docker Compose)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── docker-compose.yml
│   ├── Caddyfile
│   ├── src/
│   │   ├── __init__.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── ingest.py               # POST /v1/ingest — batch sample ingestion
│   │   │   ├── realtime.py             # GET /v1/realtime — latest snapshot
│   │   │   ├── series.py               # GET /v1/series — historical rollups
│   │   │   ├── health.py               # GET /health — service health
│   │   │   └── deps.py                 # FastAPI dependency injection
│   │   ├── auth/
│   │   │   └── bearer.py               # Bearer token validation
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── models.py               # SQLAlchemy ORM models
│   │   │   ├── session.py              # Async session factory
│   │   │   └── migrations/
│   │   │       ├── env.py
│   │   │       └── versions/
│   │   │           ├── 001_initial_schema.py
│   │   │           └── 002_continuous_aggregates.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── ingestion.py            # Batch insert logic
│   │   │   └── aggregation.py          # Frame-based rollup queries
│   │   └── cache/
│   │       └── redis_client.py         # Redis connection + cache helpers
│   └── tests/
│       ├── conftest.py
│       ├── fixtures/
│       │   └── sample_data.json
│       ├── test_models.py
│       ├── test_auth.py
│       ├── test_ingest.py
│       ├── test_realtime.py
│       ├── test_series.py
│       └── test_health.py
└── .gitignore
```

---

## Key Components

### 1. Modbus Register Map
- **Location**: `edge/src/registers.py`
- **Responsibility**: Single source of truth for Sungrow SH4.0RS Modbus register addresses, types, scaling factors, and valid ranges
- **Protocol**: Defines register groups for batched reads (PV, battery, load, grid estimate, device info)
- **Dependencies**: None (pure data definitions)

### 2. Modbus Poller
- **Location**: `edge/src/poller.py`
- **Responsibility**: Reads Modbus TCP registers from WiNet-S dongle in batched groups, returns raw register values
- **Protocol**: Modbus TCP on port 502, slave/unit ID 1, with inter-register delays for WiNet-S stability
- **Dependencies**: pymodbus (AsyncModbusTcpClient), registers.py

### 3. Normalizer
- **Location**: `edge/src/normalizer.py`
- **Responsibility**: Pure function that converts raw Modbus register values into a validated SungrowSample with proper units and scaling
- **Dependencies**: pydantic (validation), registers.py (scaling factors)

### 4. SQLite Spool
- **Location**: `edge/src/spool.py`
- **Responsibility**: Persistent FIFO buffer using SQLite in WAL mode. Survives process/host restarts.
- **Protocol**: enqueue → peek → ack pattern (same as P1-Edge-VPS)
- **Dependencies**: aiosqlite

### 5. HTTPS Batch Uploader
- **Location**: `edge/src/uploader.py`
- **Responsibility**: Reads batches from spool, POSTs to VPS ingest endpoint, marks acknowledged rows
- **Protocol**: HTTPS POST with Bearer token, exponential backoff on failure
- **Dependencies**: httpx, spool.py

### 6. VPS Ingestion
- **Location**: `vps/src/api/ingest.py`, `vps/src/services/ingestion.py`
- **Responsibility**: Validates and inserts sample batches into TimescaleDB
- **Protocol**: POST /v1/ingest with Bearer auth, ON CONFLICT DO NOTHING
- **Dependencies**: SQLAlchemy, asyncpg, bearer.py

### 7. VPS API
- **Location**: `vps/src/api/`
- **Responsibility**: REST endpoints for realtime, historical series
- **Dependencies**: FastAPI, Redis (cache), TimescaleDB (storage)

---

## Data Flow

```
┌──────────────────────────────────────────────────────────┐
│                       HOME LAN                            │
│                                                           │
│  ┌─────────────────────┐                                 │
│  │ Sungrow SH4.0RS     │                                 │
│  │ (WiNet-S dongle)    │                                 │
│  │ Modbus TCP :502     │                                 │
│  └─────────┬───────────┘                                 │
│            │ Modbus TCP (5s poll, 20ms inter-register)   │
│            │                                              │
│  ┌─────────▼──────────────────────────────────────────┐  │
│  │           EDGE DEVICE (Raspberry Pi)                │  │
│  │                                                     │  │
│  │  ┌──────────────┐                                   │  │
│  │  │ Modbus Poller│  → raw register values            │  │
│  │  └──────┬───────┘                                   │  │
│  │         │                                           │  │
│  │  ┌──────▼───────┐                                   │  │
│  │  │ Normalizer   │  → SungrowSample (validated)      │  │
│  │  └──────┬───────┘                                   │  │
│  │         │                                           │  │
│  │  ┌──────▼───────┐                                   │  │
│  │  │ SQLite Spool │  → persistent FIFO buffer         │  │
│  │  └──────┬───────┘                                   │  │
│  │         │                                           │  │
│  │  ┌──────▼───────┐                                   │  │
│  │  │ Uploader     │  → HTTPS POST batches             │  │
│  │  └──────┬───────┘                                   │  │
│  └─────────┼───────────────────────────────────────────┘  │
└────────────┼──────────────────────────────────────────────┘
             │ HTTPS (Bearer token)
┌────────────▼──────────────────────────────────────────────┐
│                         VPS                                │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  Caddy (auto-HTTPS, TLS termination)                  │ │
│  └──────────────────┬───────────────────────────────────┘ │
│                     │                                      │
│  ┌──────────────────▼───────────────────────────────────┐ │
│  │  FastAPI                                              │ │
│  │  ├── POST /v1/ingest      (batch insert)              │ │
│  │  ├── GET  /v1/realtime    (latest + Redis cache)      │ │
│  │  ├── GET  /v1/series      (hourly/daily/monthly)      │ │
│  │  └── GET  /health         (service health)            │ │
│  └──────────┬────────────────────┬──────────────────────┘ │
│             │                    │                          │
│  ┌──────────▼────────┐  ┌───────▼────────┐                │
│  │  TimescaleDB      │  │  Redis         │                │
│  │  (hypertable +    │  │  (realtime     │                │
│  │   continuous      │  │   cache)       │                │
│  │   aggregates)     │  │                │                │
│  └───────────────────┘  └────────────────┘                │
└────────────────────────────────────────────────────────────┘
```

### Flow: Poll → Normalize → Spool → Upload → Ingest
1. Poller connects to WiNet-S via Modbus TCP, reads register groups with 20ms delays
2. Normalizer converts raw registers to SungrowSample with proper scaling and validation
3. Sample JSON serialized and enqueued in SQLite spool (WAL mode, crash-safe)
4. Uploader peeks batch from spool, POSTs to VPS `/v1/ingest` with Bearer token
5. VPS validates, inserts with ON CONFLICT DO NOTHING, returns inserted count
6. Uploader acks rows in spool (deletes after acknowledgment)
7. On failure: exponential backoff, samples remain in spool until delivered

### Flow: Realtime Query
1. Client GETs `/v1/realtime?device_id=X` with Bearer token
2. Auth validates token, verifies device_id matches
3. Check Redis cache for `realtime:{device_id}`
4. Cache miss: query `sungrow_samples ORDER BY ts DESC LIMIT 1`
5. Cache result in Redis (TTL = CACHE_TTL_S, default 5s)
6. Return latest sample

### Flow: Historical Series Query
1. Client GETs `/v1/series?device_id=X&frame=day` with Bearer token
2. Auth validates token, verifies device_id matches
3. Route to appropriate continuous aggregate based on frame
4. Return time-bucketed series data

### Flow Characteristics
- **Reactive**: Polling at configurable intervals (default 5s)
- **Offline-first**: SQLite spool survives outages; no data loss
- **Configurable**: Poll interval, batch size, upload interval, inter-register delay all via env vars
- **Resilient**: Exponential backoff on Modbus failures and upload failures

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Transport | HTTPS POST (not MQTT) | Simpler, proven in P1-Edge-VPS, no broker to maintain |
| Edge buffer | SQLite WAL | Crash-safe, proven durable in P1-Edge-VPS |
| Modbus library | pymodbus async | Most mature Python Modbus library, async support |
| VPS database | TimescaleDB | Continuous aggregates for rollups, time-series optimized |
| Auth | Bearer tokens | Simple per-device auth, proven in P1-Edge-VPS |
| Monorepo | edge/ + vps/ | Atomic commits, shared understanding, proven pattern |
| Register map | Single Python file | All register definitions in one place for maintainability |

---

## Integration Points

### Inputs

- **Sungrow SH4.0RS (via WiNet-S)**:
  - Protocol: Modbus TCP, port 502, slave ID 1
  - Endpoint: WiNet-S dongle IP on local LAN
  - Auth: None (local LAN access only)
  - Data: PV production, battery SoC/power/temperature, load power, grid estimate, inverter state, MPPT voltages/currents
  - Constraints: 5s minimum poll interval, 20ms inter-register delay, max ~100 registers per request

### Outputs

- **VPS REST API**: HTTPS endpoints for realtime, historical, and health data
- **TimescaleDB**: Persistent time-series storage with automated rollups

---

## Development Patterns

### Error Handling
- Poller: log warning on Modbus errors, exponential backoff on connection loss, never crash the poll loop
- Normalizer: return None on invalid data, log warning with details
- Spool: WAL mode for crash safety, parameterized queries for SQL injection prevention
- Uploader: exponential backoff (1s → 2s → 4s → ... → max 300s), reset on success
- VPS ingest: validate schema, reject malformed payloads with 422, never crash on bad input

### Configuration
- Use environment variables for all runtime configuration (pydantic-settings)
- No hardcoded IPs, URLs, or secrets in code
- Validate VPS URL scheme (HTTPS only) at startup
- Validate Modbus parameters at startup (port range, slave ID)

### Modbus Register Read Pattern
```python
# Read registers in groups with inter-register delay
# Each group is a contiguous range of registers
async def poll_register_group(client, start_addr, count, slave_id, delay_ms):
    result = await client.read_input_registers(
        address=start_addr, count=count, slave=slave_id
    )
    await asyncio.sleep(delay_ms / 1000.0)
    return result.registers if not result.isError() else None
```

---

## Development Workflow

```bash
# Setup (edge)
cd edge && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# Setup (vps)
cd vps && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# Lint (must pass with zero warnings)
ruff check edge/src/ vps/src/

# Format (must pass)
ruff format --check edge/src/ vps/src/

# Test
pytest edge/tests/ vps/tests/ -q

# Test with coverage report
pytest edge/tests/ vps/tests/ --cov=edge/src --cov=vps/src --cov-report=term-missing

# Run edge locally
cd edge && python -m src.main

# Run VPS locally
cd vps && docker compose up

# Clean rebuild
rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
```

---

## Testing Strategy

| Test Type | Location | Coverage Target | Tools |
|-----------|----------|-----------------|-------|
| Unit Tests | `edge/tests/`, `vps/tests/` | 90%+ | pytest, pytest-asyncio |
| Integration | `vps/tests/` | Key API flows | FastAPI TestClient |
| Fixtures | `*/tests/fixtures/` | Mock data | JSON files |

### Test Requirements
- All tests must run without real network access or real Modbus devices
- No tests may depend on real external services
- All async code tested with pytest-asyncio
- Time-dependent code must accept injectable timestamps

### Mock Strategy
- **Modbus**: Mock pymodbus AsyncModbusTcpClient, return fixture register data
- **HTTP uploads**: Mock httpx responses (200, 401, 500, timeout)
- **Database**: Mock SQLAlchemy AsyncSession
- **Redis**: Mock Redis client
- **SQLite spool**: Use in-memory SQLite for test isolation

### Time-Dependent Testing

| Feature | Time Dependency | Test Strategy |
|---------|----------------|---------------|
| Poll interval | asyncio.sleep | Mock sleep, verify call count |
| Upload backoff | Exponential timer | Mock sleep, verify doubling |
| Timestamp generation | datetime.now(UTC) | Accept ts parameter, use fixed test timestamps |

**Pattern**: Accept timestamps as parameters. Never call `datetime.now()` directly in business logic. Tests use fixed timestamps from fixtures.

---

## Environment & Secrets

| Variable | Purpose | Component | Required |
|----------|---------|-----------|----------|
| `SUNGROW_HOST` | WiNet-S IP address | Edge | Yes |
| `SUNGROW_PORT` | Modbus TCP port | Edge | No (default: 502) |
| `SUNGROW_SLAVE_ID` | Modbus slave/unit ID | Edge | No (default: 1) |
| `POLL_INTERVAL_S` | Seconds between poll cycles | Edge | No (default: 5) |
| `INTER_REGISTER_DELAY_MS` | Milliseconds between register group reads | Edge | No (default: 20) |
| `VPS_INGEST_URL` | VPS ingest endpoint URL (HTTPS) | Edge | Yes |
| `VPS_DEVICE_TOKEN` | Bearer token for VPS auth | Edge | Yes |
| `DEVICE_ID` | Device identifier | Edge | No (default: sungrow_host) |
| `BATCH_SIZE` | Samples per upload batch | Edge | No (default: 30) |
| `UPLOAD_INTERVAL_S` | Seconds between upload attempts | Edge | No (default: 10) |
| `SPOOL_PATH` | SQLite spool file path | Edge | No (default: /data/spool.db) |
| `DATABASE_URL` | PostgreSQL connection string | VPS | Yes |
| `REDIS_URL` | Redis connection string | VPS | Yes |
| `DEVICE_TOKENS` | Token:device_id pairs | VPS | Yes |
| `CACHE_TTL_S` | Redis cache TTL | VPS | No (default: 5) |

**Security**: All secrets via environment variables, never in code. Edge `.env` file gitignored.

---

## Operational Assumptions

1. **Runtime**: Python 3.12+, Docker 24+, Docker Compose v2
2. **Edge device**: Raspberry Pi 4 (2GB+ RAM), <50MB RSS, LAN access to WiNet-S dongle
3. **Network**: Edge has outbound HTTPS to VPS; WiNet-S on same LAN
4. **VPS**: <200MB RSS per worker, public HTTPS, persistent Docker volumes

---

## Hard Constraints

### HC-001: No Data Loss
**Constraint**: Every polled Modbus reading must eventually reach TimescaleDB, even across outages.

**Rationale**: Solar/battery telemetry gaps prevent accurate analysis.

**Implications**:
- SQLite spool persists before upload
- Delete only after VPS acknowledgment
- Exponential backoff on failure

**Allowed**: Temporary delays in delivery
**Forbidden**: Dropping readings, deleting unacknowledged data

### HC-002: Idempotent Ingestion
**Constraint**: Composite PK `(device_id, ts)` prevents duplicates. `ON CONFLICT DO NOTHING`.

**Rationale**: Batch replay must not corrupt data.

**Implications**:
- Same batch safe to re-send
- VPS returns actual inserted count

**Allowed**: Re-sending acknowledged batches
**Forbidden**: Upsert/overwrite on duplicate keys

### HC-003: HTTPS Only
**Constraint**: All edge↔VPS traffic encrypted with valid certificates.

**Rationale**: Data transits public internet.

**Implications**:
- Reject http:// URLs at startup
- TLS certificate verification always enabled

**Allowed**: TLS 1.2+
**Forbidden**: Plaintext HTTP, disabled cert verification

### HC-004: WiNet-S Stability
**Constraint**: Respect WiNet-S hardware limitations.

**Rationale**: WiNet-S dongle has limited processing power.

**Implications**:
- Minimum 5s poll interval
- 20ms delay between register group reads
- Exponential backoff on connection failures

**Allowed**: Configurable intervals (min 5s)
**Forbidden**: Sub-5s polling, burst reads without delay

---

## Architecture Decision Records (ADRs)

### ADR-001: Monorepo for Edge + VPS
**Status**: Approved
**Date**: 2026-02-14
**Stories**: All

**Context**:
The pipeline has two deployment targets: edge device and VPS. They could be separate repos or a monorepo.

**Decision**:
Use a monorepo with `edge/` and `vps/` directories, same pattern as P1-Edge-VPS.

**Alternatives Considered**:
| Option | Pros | Cons |
|--------|------|------|
| Monorepo | Atomic commits, shared context, proven pattern | Slightly larger repo |
| Separate repos | Independent versioning | Fragmented context, harder to keep in sync |

**Rationale**:
- Proven pattern from P1-Edge-VPS
- Agent can see full context in one repo
- Schema changes coordinated atomically

### ADR-002: HTTPS POST over MQTT
**Status**: Approved
**Date**: 2026-02-14
**Stories**: All

**Context**:
Original project idea specified MQTT over TLS. P1-Edge-VPS successfully uses HTTPS POST instead.

**Decision**:
Use HTTPS POST with Bearer token auth, same as P1-Edge-VPS.

**Alternatives Considered**:
| Option | Pros | Cons |
|--------|------|------|
| HTTPS POST | Simpler, no broker, proven, built-in auth | Slightly higher overhead per request |
| MQTT over TLS | Lower per-message overhead, pub/sub | Requires broker, certificate management, more complexity |

**Rationale**:
- Proven reliable in P1-Edge-VPS (100% complete, production-ready)
- No additional infrastructure (Mosquitto broker) to maintain
- Bearer token auth simpler than client certificates
- Batch upload amortizes HTTPS overhead

### ADR-003: pymodbus for Modbus TCP
**Status**: Approved
**Date**: 2026-02-14
**Stories**: STORY-002, STORY-003

**Context**:
Need an async-capable Python Modbus TCP client to communicate with WiNet-S.

**Decision**:
Use pymodbus AsyncModbusTcpClient.

**Alternatives Considered**:
| Option | Pros | Cons |
|--------|------|------|
| pymodbus | Most mature, async support, well-documented | Large library |
| umodbus | Lightweight | No async support |
| minimalmodbus | Simple API | Serial only, no TCP |

**Rationale**:
- AsyncModbusTcpClient aligns with async architecture
- Well-tested with Sungrow inverters (community references)
- Handles reconnection and error states

---

## Deployment Strategy

### Environments

| Environment | URL | Purpose |
|-------------|-----|---------|
| Development | localhost | Local development with mocked Modbus |
| Production Edge | Raspberry Pi on LAN | Real Modbus polling |
| Production VPS | HTTPS (Caddy auto-cert) | Live API |

### Deployment Method

**Edge**: Docker container on Raspberry Pi
```yaml
# docker-compose.edge.yml
services:
  edge:
    build: ./edge
    volumes: [sungrow_edge_data:/data]
    env_file: .env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "test", "-f", "/data/health.json"]
      interval: 30s
```

**VPS**: Docker Compose with Caddy, FastAPI, TimescaleDB, Redis
```yaml
# vps/docker-compose.yml
services:
  api:
    build: .
    command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000
    depends_on: [postgres, redis]
  postgres:
    image: timescale/timescaledb:latest-pg16
  redis:
    image: redis:7-alpine
  caddy:
    image: caddy:2
    ports: ["80:80", "443:443"]
```

---

## Related Documents

- `CLAUDE.md`: Agent workflow rules and gates (highest authority)
- `docs/BACKLOG.md`: Stories, acceptance criteria, progress tracking
- `SKILL.md`: Security guidelines (VibeSec)
- `docs/Project_idea.md`: Original project concept (broader scope; this repo is Sungrow-only)
