# Phase 2: VPS Ingestion

**Status**: Not Started
**Stories**: 4
**Completed**: 0
**Depends On**: None (can be developed in parallel with Phase 1)

---

## Phase Completion Criteria

This phase is complete when:
- [ ] All stories have status "done"
- [ ] All tests passing (`pytest vps/tests/`)
- [ ] Lint clean (`ruff check vps/src/`)
- [ ] VPS accepts Sungrow sample batches via HTTPS and stores in TimescaleDB

---

## Stories

<story id="STORY-007" status="pending" complexity="M" tdd="recommended">
  <title>VPS scaffolding and configuration</title>
  <dependencies>None</dependencies>

  <description>
    Set up the vps/ directory with FastAPI application, Docker Compose (TimescaleDB,
    Redis, Caddy), requirements.txt, and configuration loading. Follows the same
    structure as P1-Edge-VPS.
  </description>

  <acceptance_criteria>
    <ac id="AC1">vps/src/ is a valid Python package</ac>
    <ac id="AC2">FastAPI app created in vps/src/api/ with app instance</ac>
    <ac id="AC3">docker-compose.yml defines api, postgres (TimescaleDB), redis, caddy services</ac>
    <ac id="AC4">Environment variables loaded for DATABASE_URL, REDIS_URL, DEVICE_TOKENS</ac>
    <ac id="AC5">vps/tests/ directory exists with conftest.py and app fixture</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>vps/requirements.txt</file>
    <file>vps/Dockerfile</file>
    <file>vps/docker-compose.yml</file>
    <file>vps/Caddyfile</file>
    <file>vps/src/__init__.py</file>
    <file>vps/src/api/__init__.py</file>
    <file>vps/src/api/deps.py</file>
    <file>vps/src/auth/__init__.py</file>
    <file>vps/src/db/__init__.py</file>
    <file>vps/src/db/session.py</file>
    <file>vps/src/services/__init__.py</file>
    <file>vps/src/cache/__init__.py</file>
    <file>vps/src/cache/redis_client.py</file>
    <file>vps/tests/__init__.py</file>
    <file>vps/tests/conftest.py</file>
  </allowed_scope>

  <test_plan>
    - FastAPI app starts without errors
    - Docker Compose config validates
    - conftest.py provides app fixture with mocked DB/Redis
    - pytest vps/tests/ all pass
  </test_plan>

  <notes>
    - Follow P1-Edge-VPS vps/ structure
    - Docker images: timescale/timescaledb:latest-pg16, redis:7-alpine, caddy:2
    - Database name: sungrow (different from P1's db)
    - Bind postgres to 127.0.0.1 only
  </notes>
</story>

---

<story id="STORY-008" status="pending" complexity="L" tdd="required">
  <title>TimescaleDB schema and migrations</title>
  <dependencies>STORY-007</dependencies>

  <description>
    Create Alembic migration for the sungrow_samples hypertable. The table stores
    all normalized Sungrow telemetry with a composite primary key (device_id, ts)
    for idempotent ingestion (HC-002).

    Columns match the SungrowSample model from edge/src/models.py (STORY-004).
  </description>

  <acceptance_criteria>
    <ac id="AC1">Alembic migration creates sungrow_samples table as TimescaleDB hypertable</ac>
    <ac id="AC2">Composite PK on (device_id, ts)</ac>
    <ac id="AC3">Columns: pv_power_w, pv_daily_kwh, battery_power_w, battery_soc_pct, battery_temp_c, load_power_w, export_power_w</ac>
    <ac id="AC4">SQLAlchemy ORM model matches migration schema</ac>
    <ac id="AC5">TimescaleDB extension created if not exists</ac>
    <ac id="AC6">Hypertable with 7-day chunk interval on ts</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>vps/src/db/models.py</file>
    <file>vps/src/db/migrations/__init__.py</file>
    <file>vps/src/db/migrations/env.py</file>
    <file>vps/src/db/migrations/versions/__init__.py</file>
    <file>vps/src/db/migrations/versions/001_initial_schema.py</file>
    <file>vps/tests/test_models.py</file>
  </allowed_scope>

  <test_first>
    <item>Create vps/tests/test_models.py FIRST</item>
    <item>Test: ORM model has all expected columns with correct types</item>
    <item>Test: composite PK on (device_id, ts)</item>
    <item>Test: model can be instantiated with valid data</item>
    <item>Test: model rejects invalid data types</item>
  </test_first>

  <test_plan>
    - ORM model unit tests
    - Migration SQL review (manual)
    - Column types and constraints verified
    - pytest vps/tests/ all pass
  </test_plan>

  <notes>
    - Follow P1-Edge-VPS migration pattern
    - Use op.execute() for TimescaleDB-specific SQL (CREATE EXTENSION, create_hypertable)
    - 7-day chunk interval matches P1 pattern
    - Include sample_count column for future weighted aggregation
  </notes>
</story>

---

<story id="STORY-009" status="pending" complexity="S" tdd="required">
  <title>Bearer token authentication</title>
  <dependencies>STORY-007</dependencies>

  <description>
    Per-device Bearer token authentication. Parse DEVICE_TOKENS environment variable
    in format "tokenA:device-1,tokenB:device-2" into a lookup map. Validate tokens
    using constant-time comparison (secrets.compare_digest) to prevent timing attacks.
  </description>

  <acceptance_criteria>
    <ac id="AC1">DEVICE_TOKENS parsed into {token → device_id} mapping at startup</ac>
    <ac id="AC2">Bearer token validated with secrets.compare_digest (constant-time)</ac>
    <ac id="AC3">Valid token returns device_id string</ac>
    <ac id="AC4">Invalid/missing token returns 401 with error detail</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>vps/src/auth/__init__.py</file>
    <file>vps/src/auth/bearer.py</file>
    <file>vps/tests/test_auth.py</file>
  </allowed_scope>

  <test_first>
    <item>Create vps/tests/test_auth.py FIRST</item>
    <item>Test: valid token returns correct device_id</item>
    <item>Test: invalid token returns 401</item>
    <item>Test: missing Authorization header returns 401</item>
    <item>Test: malformed Authorization header returns 401</item>
    <item>Test: DEVICE_TOKENS with multiple entries parsed correctly</item>
    <item>Test: empty DEVICE_TOKENS handled gracefully</item>
  </test_first>

  <test_plan>
    - Unit tests for token parsing and validation
    - Test all auth failure modes
    - pytest vps/tests/ all pass
  </test_plan>

  <notes>
    - Follow P1-Edge-VPS vps/src/auth/bearer.py exactly
    - Use FastAPI HTTPBearer with auto_error=False for custom error responses
    - Store parsed tokens in module-level dict, initialized at import time
  </notes>
</story>

---

<story id="STORY-010" status="pending" complexity="L" tdd="required">
  <title>Ingest endpoint</title>
  <dependencies>STORY-008, STORY-009</dependencies>

  <description>
    POST /v1/ingest endpoint that accepts a batch of Sungrow samples, validates
    that all sample device_ids match the authenticated device_id, inserts with
    ON CONFLICT DO NOTHING for idempotency (HC-002), returns the count of
    actually inserted rows, and invalidates the Redis realtime cache.
  </description>

  <acceptance_criteria>
    <ac id="AC1">POST /v1/ingest accepts {"samples": [...]} payload</ac>
    <ac id="AC2">All samples.device_id must match authenticated device_id (403 on mismatch)</ac>
    <ac id="AC3">INSERT with ON CONFLICT (device_id, ts) DO NOTHING</ac>
    <ac id="AC4">Returns {"inserted": N} with actual inserted count</ac>
    <ac id="AC5">Invalidates Redis key realtime:{device_id} on success</ac>
    <ac id="AC6">Empty samples list returns {"inserted": 0} (no error)</ac>
    <ac id="AC7">Invalid payload returns 422</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>vps/src/api/ingest.py</file>
    <file>vps/src/services/__init__.py</file>
    <file>vps/src/services/ingestion.py</file>
    <file>vps/tests/test_ingest.py</file>
    <file>vps/tests/fixtures/sample_data.json</file>
  </allowed_scope>

  <test_first>
    <item>Create vps/tests/test_ingest.py FIRST</item>
    <item>Create vps/tests/fixtures/sample_data.json with valid sample batches</item>
    <item>Mock AsyncSession and Redis</item>
    <item>Test: valid batch → 200 with inserted count</item>
    <item>Test: device_id mismatch → 403</item>
    <item>Test: empty samples list → {"inserted": 0}</item>
    <item>Test: duplicate samples (same device_id+ts) → not re-inserted</item>
    <item>Test: invalid payload (missing fields) → 422</item>
    <item>Test: Redis cache key deleted on success</item>
    <item>Test: no auth → 401</item>
  </test_first>

  <test_plan>
    - Integration tests with FastAPI TestClient
    - Mock DB session and Redis client
    - Test success, auth failures, validation failures, duplicates
    - pytest vps/tests/ all pass
  </test_plan>

  <notes>
    - Follow P1-Edge-VPS vps/src/api/ingest.py pattern
    - Use SQLAlchemy insert().on_conflict_do_nothing()
    - Validate each sample's fields before insert
    - Log inserted count at INFO level
  </notes>
</story>

---

## Phase Notes

### Dependencies on Other Phases
- Phase 2 has NO dependencies on Phase 1 — edge and VPS can be developed in parallel
- The ingest endpoint schema must match SungrowSample from Phase 1 (STORY-004)

### Known Risks
- Schema divergence: If SungrowSample model changes during Phase 1, the VPS schema must update. Mitigation: define model in Phase 1 first, then build VPS schema to match.

### Technical Debt
- No rate limiting implemented (see parking lot). Add in future phase if needed.
