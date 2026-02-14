<backlog>

<metadata>
  <project>Sungrow-to-VPS Pipeline</project>
  <last_updated>2026-02-14</last_updated>
  <total_stories>16</total_stories>
  <done>0</done>
  <progress>0%</progress>
  <changelog>
    <entry date="2026-02-14">Initial backlog creation (16 stories across 4 phases)</entry>
  </changelog>
</metadata>

<!-- ============================================================ -->
<!-- MVP DEFINITION                                                -->
<!-- ============================================================ -->

<mvp>
  <goal>End-to-end pipeline: poll Sungrow inverter via Modbus TCP, buffer locally, upload to VPS, store in TimescaleDB, serve via REST API. No data loss.</goal>

  <scope>
    <item priority="1" story="STORY-001">Edge project scaffolding and configuration</item>
    <item priority="2" story="STORY-002">Modbus register map</item>
    <item priority="3" story="STORY-003">Modbus TCP poller</item>
    <item priority="4" story="STORY-004">Normalizer (registers → SungrowSample)</item>
    <item priority="5" story="STORY-005">SQLite spool buffer</item>
    <item priority="6" story="STORY-006">HTTPS batch uploader</item>
    <item priority="7" story="STORY-007">VPS scaffolding and configuration</item>
    <item priority="8" story="STORY-008">TimescaleDB schema and migrations</item>
    <item priority="9" story="STORY-009">Bearer token authentication</item>
    <item priority="10" story="STORY-010">Ingest endpoint</item>
    <item priority="11" story="STORY-011">Realtime endpoint</item>
    <item priority="12" story="STORY-012">Series endpoint (historical rollups)</item>
  </scope>

  <deliverables>
    <item>Edge daemon polling Sungrow inverter every 5s via Modbus TCP</item>
    <item>Durable SQLite spool with no-data-loss guarantee</item>
    <item>VPS with TimescaleDB, ingest, realtime, and series endpoints</item>
    <item>Bearer token auth on all endpoints</item>
  </deliverables>

  <post_mvp>
    <item>Battery cycle analysis and optimization insights</item>
    <item>EMS mode read/write control via Modbus</item>
    <item>Correlation with P1-Edge-VPS grid data for cross-pipeline analytics</item>
    <item>Alerting on battery health degradation or inverter faults</item>
  </post_mvp>
</mvp>

<!-- ============================================================ -->
<!-- KEY CONSTRAINTS                                               -->
<!-- ============================================================ -->

<constraints>
  <constraint id="HC-001" ref="Architecture.md">No Data Loss — every reading must reach TimescaleDB</constraint>
  <constraint id="HC-002" ref="Architecture.md">Idempotent Ingestion — composite PK (device_id, ts), ON CONFLICT DO NOTHING</constraint>
  <constraint id="HC-003" ref="Architecture.md">HTTPS Only — all edge↔VPS traffic encrypted</constraint>
  <constraint id="HC-004" ref="Architecture.md">WiNet-S Stability — min 5s poll, 20ms inter-register delay</constraint>
</constraints>

<!-- ============================================================ -->
<!-- DEFINITION OF READY                                           -->
<!-- ============================================================ -->

<dor>
  <title>Definition of Ready</title>
  <description>A story is ready for development when ALL conditions are true:</description>
  <checklist>
    <item>Clear description of what needs to be built</item>
    <item>Acceptance criteria are specific and testable</item>
    <item>Dependencies are identified and completed</item>
    <item>Technical approach is understood</item>
    <item>Estimated complexity noted (S/M/L/XL)</item>
    <item>Allowed Scope defined (files/modules)</item>
    <item>Test-First Requirements defined (if TDD-mandated)</item>
    <item>Mock strategy defined for external dependencies</item>
  </checklist>
</dor>

<!-- ============================================================ -->
<!-- DEFINITION OF DONE                                            -->
<!-- ============================================================ -->

<dod>
  <title>Definition of Done</title>
  <description>A story is complete when ALL conditions are true:</description>
  <checklist>
    <item>All acceptance criteria pass</item>
    <item>ruff check passes with zero warnings</item>
    <item>ruff format --check passes</item>
    <item>pytest passes with no failures</item>
    <item>Documentation on all public APIs</item>
    <item>CHANGELOG header updated in modified files</item>
    <item>No undocumented TODOs introduced</item>
    <item>Security checklist passed (per CLAUDE.md section 13)</item>
    <item>Code reviewed (self-review minimum)</item>
  </checklist>
</dod>

<!-- ============================================================ -->
<!-- PRIORITY ORDER                                                -->
<!-- ============================================================ -->

<priority_order>
  <tier name="Edge Foundation" description="Edge scaffolding, register map, Modbus poller">
    <entry priority="1" story="STORY-001" title="Edge scaffolding and config" complexity="M" deps="None" />
    <entry priority="2" story="STORY-002" title="Sungrow Modbus register map" complexity="M" deps="STORY-001" />
    <entry priority="3" story="STORY-003" title="Modbus TCP poller" complexity="L" deps="STORY-002" />
    <entry priority="4" story="STORY-004" title="Register normalizer" complexity="M" deps="STORY-002" />
  </tier>

  <tier name="Edge Pipeline" description="Spool, uploader, main daemon">
    <entry priority="5" story="STORY-005" title="SQLite spool buffer" complexity="M" deps="STORY-001" />
    <entry priority="6" story="STORY-006" title="HTTPS batch uploader" complexity="M" deps="STORY-005" />
  </tier>

  <tier name="VPS Foundation" description="VPS scaffolding, database, auth, ingest">
    <entry priority="7" story="STORY-007" title="VPS scaffolding and config" complexity="M" deps="None" />
    <entry priority="8" story="STORY-008" title="TimescaleDB schema" complexity="L" deps="STORY-007" />
    <entry priority="9" story="STORY-009" title="Bearer token auth" complexity="S" deps="STORY-007" />
    <entry priority="10" story="STORY-010" title="Ingest endpoint" complexity="L" deps="STORY-008, STORY-009" />
  </tier>

  <tier name="API Features" description="Read endpoints and continuous aggregates">
    <entry priority="11" story="STORY-011" title="Realtime endpoint" complexity="M" deps="STORY-010" />
    <entry priority="12" story="STORY-012" title="Series endpoint" complexity="L" deps="STORY-010" />
    <entry priority="13" story="STORY-013" title="Continuous aggregates" complexity="M" deps="STORY-008" />
  </tier>

  <tier name="Production" description="Health checks, hardening, edge main loop">
    <entry priority="14" story="STORY-014" title="Edge main loop" complexity="L" deps="STORY-003, STORY-004, STORY-005, STORY-006" />
    <entry priority="15" story="STORY-015" title="Health checks" complexity="S" deps="STORY-007, STORY-014" />
    <entry priority="16" story="STORY-016" title="Production hardening" complexity="M" deps="STORY-015" />
  </tier>
</priority_order>

<!-- ============================================================ -->
<!-- PHASE 1: EDGE FOUNDATION                                      -->
<!-- Story file: docs/stories/phase-1-edge-foundation.md           -->
<!-- ============================================================ -->

<phase id="1" name="Edge Foundation" story_file="docs/stories/phase-1-edge-foundation.md">

<story id="STORY-001" status="pending" complexity="M" tdd="recommended">
  <title>Edge scaffolding and configuration</title>
  <dependencies>None</dependencies>
  <description>
    Set up edge/ directory with pyproject.toml or requirements.txt, src/ package structure,
    tests/ directory, and Pydantic Settings config loading from environment variables.
  </description>
  <acceptance_criteria>
    <ac id="AC1">edge/src/ is a valid Python package with __init__.py</ac>
    <ac id="AC2">edge/src/config.py loads all required env vars via pydantic-settings</ac>
    <ac id="AC3">Config validates SUNGROW_HOST is required, SUNGROW_PORT defaults to 502</ac>
    <ac id="AC4">Config validates VPS_INGEST_URL scheme is HTTPS</ac>
    <ac id="AC5">edge/tests/ directory exists with conftest.py and env fixtures</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>edge/requirements.txt</file>
    <file>edge/src/__init__.py</file>
    <file>edge/src/config.py</file>
    <file>edge/tests/__init__.py</file>
    <file>edge/tests/conftest.py</file>
    <file>edge/tests/test_config.py</file>
  </allowed_scope>
  <test_plan>
    - Config loads valid env vars correctly
    - Config raises on missing required vars
    - Config rejects http:// VPS URL
    - Config defaults SUNGROW_PORT to 502
    - pytest edge/tests/ all pass
  </test_plan>
  <notes>
    - Follow P1-Edge-VPS config.py pattern exactly
    - Use pydantic-settings BaseSettings
  </notes>
</story>

<story id="STORY-002" status="pending" complexity="M" tdd="required">
  <title>Sungrow Modbus register map</title>
  <dependencies>STORY-001</dependencies>
  <description>
    Create the register map as a single source of truth for all Sungrow SH4.0RS Modbus registers.
    Define register groups for batched reads, data types (U16, U32, S16, S32), scaling factors,
    units, and valid value ranges. This file drives both the poller and the normalizer.
  </description>
  <acceptance_criteria>
    <ac id="AC1">registers.py defines all PV registers (total_dc_power, daily_pv_generation, total_pv_generation, mppt1/2 voltage/current)</ac>
    <ac id="AC2">registers.py defines all battery registers (battery_power, battery_soc, battery_temperature, daily_charge/discharge)</ac>
    <ac id="AC3">registers.py defines load registers (load_power, daily_direct_consumption)</ac>
    <ac id="AC4">registers.py defines grid estimate registers (export_power, grid_power)</ac>
    <ac id="AC5">registers.py defines device info registers (device_type_code, serial_number)</ac>
    <ac id="AC6">Each register has: address, name, type, unit, scaling factor, valid range</ac>
    <ac id="AC7">Registers are grouped into read batches (contiguous ranges for efficient Modbus reads)</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>edge/src/registers.py</file>
    <file>edge/tests/test_registers.py</file>
  </allowed_scope>
  <test_first>
    <item>Create edge/tests/test_registers.py FIRST</item>
    <item>Test: all register groups have contiguous address ranges</item>
    <item>Test: all registers have required fields (address, name, type, unit, scale)</item>
    <item>Test: no duplicate register addresses</item>
    <item>Test: scaling factors are valid numbers</item>
  </test_first>
  <test_plan>
    - Unit tests for register map integrity
    - Verify register groups are contiguous
    - Verify no duplicate addresses
    - pytest edge/tests/ all pass
  </test_plan>
  <notes>
    - Reference: Sungrow Hybrid Inverter Communication Protocol
    - Reference: mkaiser HA integration register map
    - SH4.0RS via WiNet-S — some registers may not be available; document known limitations
  </notes>
</story>

<story id="STORY-003" status="pending" complexity="L" tdd="required">
  <title>Modbus TCP poller</title>
  <dependencies>STORY-002</dependencies>
  <description>
    Async Modbus TCP client that connects to WiNet-S, reads register groups with
    inter-register delays, and returns raw register values. Handles connection failures
    with exponential backoff. Never crashes the poll loop.
  </description>
  <acceptance_criteria>
    <ac id="AC1">Poller connects to WiNet-S via AsyncModbusTcpClient</ac>
    <ac id="AC2">Poller reads all register groups defined in registers.py</ac>
    <ac id="AC3">Poller waits INTER_REGISTER_DELAY_MS between group reads</ac>
    <ac id="AC4">Poller returns dict of {register_name: raw_value} or None on error</ac>
    <ac id="AC5">Poller logs warning on read errors, never raises to caller</ac>
    <ac id="AC6">Poller implements exponential backoff on connection failures</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>edge/src/poller.py</file>
    <file>edge/tests/test_poller.py</file>
    <file>edge/tests/fixtures/modbus_responses.json</file>
  </allowed_scope>
  <test_first>
    <item>Create edge/tests/test_poller.py FIRST</item>
    <item>Create edge/tests/fixtures/modbus_responses.json with known register data</item>
    <item>Mock AsyncModbusTcpClient</item>
    <item>Test: successful read returns dict with all register names</item>
    <item>Test: Modbus error returns None</item>
    <item>Test: connection failure triggers backoff</item>
    <item>Test: inter-register delay is respected</item>
  </test_first>
  <test_plan>
    - Unit tests with mocked pymodbus client
    - Test happy path, error path, connection failure
    - Test backoff behavior
    - pytest edge/tests/ all pass
  </test_plan>
  <notes>
    - WiNet-S can be unstable; exponential backoff is critical
    - Use slave_id=1 (configurable via config)
    - Read input registers (function code 0x04), not holding registers
  </notes>
</story>

<story id="STORY-004" status="pending" complexity="M" tdd="required">
  <title>Register normalizer</title>
  <dependencies>STORY-002</dependencies>
  <description>
    Pure function that takes raw Modbus register values and converts them to a validated
    SungrowSample with proper units, scaling, and type conversions. Handles U16, U32,
    S16, S32 types and applies scaling factors from registers.py.
  </description>
  <acceptance_criteria>
    <ac id="AC1">Normalizer is a pure function: no side effects, no I/O, no clock</ac>
    <ac id="AC2">Normalizer applies correct scaling factors (e.g., 0.1 kWh → kWh)</ac>
    <ac id="AC3">Normalizer handles U32 assembly from two U16 registers</ac>
    <ac id="AC4">Normalizer handles S16 signed values (two's complement)</ac>
    <ac id="AC5">Normalizer returns validated SungrowSample pydantic model or None on invalid data</ac>
    <ac id="AC6">SungrowSample includes: device_id, ts, pv_power_w, pv_daily_kwh, battery_power_w, battery_soc_pct, battery_temp_c, load_power_w, export_power_w</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>edge/src/normalizer.py</file>
    <file>edge/src/models.py</file>
    <file>edge/tests/test_normalizer.py</file>
  </allowed_scope>
  <test_first>
    <item>Create edge/tests/test_normalizer.py FIRST</item>
    <item>Test: known register values produce expected SungrowSample</item>
    <item>Test: U32 assembly from two U16 registers</item>
    <item>Test: S16 negative values handled correctly</item>
    <item>Test: scaling factors applied (e.g., raw 1234 with scale 0.1 → 123.4)</item>
    <item>Test: missing required fields returns None</item>
    <item>Test: out-of-range values returns None</item>
  </test_first>
  <test_plan>
    - Pure function tests with fixture register data
    - Test type conversions (U16, U32, S16, S32)
    - Test scaling
    - Test validation (range checks, required fields)
    - pytest edge/tests/ all pass
  </test_plan>
  <notes>
    - This must be a pure function for testability
    - Accept device_id and ts as parameters
    - Separate models.py for SungrowSample pydantic model
  </notes>
</story>

<story id="STORY-005" status="pending" complexity="M" tdd="required">
  <title>SQLite spool buffer</title>
  <dependencies>STORY-001</dependencies>
  <description>
    Async SQLite-based persistent FIFO buffer using WAL mode. Follows the same
    enqueue/peek/ack pattern proven in P1-Edge-VPS. Survives process and host restarts.
  </description>
  <acceptance_criteria>
    <ac id="AC1">Spool creates SQLite database in WAL mode</ac>
    <ac id="AC2">enqueue() inserts a sample row</ac>
    <ac id="AC3">peek(n) returns up to n oldest unacknowledged rows</ac>
    <ac id="AC4">ack(rowids) deletes acknowledged rows</ac>
    <ac id="AC5">count() returns number of pending rows</ac>
    <ac id="AC6">All queries use parameterized SQL (no SQL injection)</ac>
    <ac id="AC7">Spool handles concurrent read/write without corruption</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>edge/src/spool.py</file>
    <file>edge/tests/test_spool.py</file>
  </allowed_scope>
  <test_first>
    <item>Create edge/tests/test_spool.py FIRST</item>
    <item>Test: enqueue + peek returns same data</item>
    <item>Test: ack removes rows from peek results</item>
    <item>Test: count reflects pending rows</item>
    <item>Test: FIFO ordering (oldest first)</item>
    <item>Test: WAL mode is enabled</item>
  </test_first>
  <test_plan>
    - Unit tests with in-memory SQLite
    - Test enqueue/peek/ack lifecycle
    - Test FIFO ordering
    - Test WAL mode enabled
    - pytest edge/tests/ all pass
  </test_plan>
  <notes>
    - Follow P1-Edge-VPS spool.py pattern closely
    - Use aiosqlite for async
    - WAL mode set at connection time
  </notes>
</story>

<story id="STORY-006" status="pending" complexity="M" tdd="required">
  <title>HTTPS batch uploader</title>
  <dependencies>STORY-005</dependencies>
  <description>
    Reads batches from spool, POSTs to VPS /v1/ingest with Bearer token, marks
    acknowledged rows. Implements exponential backoff on failure. Validates HTTPS
    at startup.
  </description>
  <acceptance_criteria>
    <ac id="AC1">Uploader peeks BATCH_SIZE samples from spool</ac>
    <ac id="AC2">Uploader POSTs {"samples": [...]} to VPS_INGEST_URL/v1/ingest</ac>
    <ac id="AC3">Uploader includes Bearer token in Authorization header</ac>
    <ac id="AC4">On 200 response: acks rows in spool</ac>
    <ac id="AC5">On failure (non-200, timeout, connection error): exponential backoff</ac>
    <ac id="AC6">Backoff resets to initial value on success</ac>
    <ac id="AC7">Validates VPS URL is HTTPS at startup (rejects http://)</ac>
    <ac id="AC8">TLS certificate verification always enabled</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>edge/src/uploader.py</file>
    <file>edge/tests/test_uploader.py</file>
  </allowed_scope>
  <test_first>
    <item>Create edge/tests/test_uploader.py FIRST</item>
    <item>Mock httpx client responses</item>
    <item>Test: successful upload acks spool rows</item>
    <item>Test: 401 response does not ack rows</item>
    <item>Test: connection error triggers backoff</item>
    <item>Test: backoff doubles on consecutive failures</item>
    <item>Test: backoff resets on success</item>
    <item>Test: http:// URL rejected at startup</item>
  </test_first>
  <test_plan>
    - Unit tests with mocked httpx
    - Test success, auth failure, server error, timeout
    - Test exponential backoff behavior
    - Test HTTPS validation
    - pytest edge/tests/ all pass
  </test_plan>
  <notes>
    - Follow P1-Edge-VPS uploader.py pattern
    - Max backoff configurable (default 300s)
  </notes>
</story>

</phase>

<!-- ============================================================ -->
<!-- PHASE 2: VPS INGESTION                                        -->
<!-- Story file: docs/stories/phase-2-vps-ingestion.md             -->
<!-- ============================================================ -->

<phase id="2" name="VPS Ingestion" story_file="docs/stories/phase-2-vps-ingestion.md">

<story id="STORY-007" status="pending" complexity="M" tdd="recommended">
  <title>VPS scaffolding and configuration</title>
  <dependencies>None</dependencies>
  <description>
    Set up vps/ directory with FastAPI app, Docker Compose, Caddy config,
    requirements.txt, and configuration loading.
  </description>
  <acceptance_criteria>
    <ac id="AC1">vps/src/ is a valid Python package</ac>
    <ac id="AC2">FastAPI app created in vps/src/api/</ac>
    <ac id="AC3">docker-compose.yml defines api, postgres (TimescaleDB), redis, caddy services</ac>
    <ac id="AC4">Environment variables loaded for DATABASE_URL, REDIS_URL, DEVICE_TOKENS</ac>
    <ac id="AC5">vps/tests/ directory exists with conftest.py</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>vps/requirements.txt</file>
    <file>vps/Dockerfile</file>
    <file>vps/docker-compose.yml</file>
    <file>vps/Caddyfile</file>
    <file>vps/src/__init__.py</file>
    <file>vps/src/api/__init__.py</file>
    <file>vps/src/api/deps.py</file>
    <file>vps/src/db/__init__.py</file>
    <file>vps/src/db/session.py</file>
    <file>vps/src/cache/redis_client.py</file>
    <file>vps/tests/__init__.py</file>
    <file>vps/tests/conftest.py</file>
  </allowed_scope>
  <test_plan>
    - FastAPI app starts without errors
    - Docker Compose validates
    - pytest vps/tests/ all pass
  </test_plan>
  <notes>
    - Follow P1-Edge-VPS vps/ structure closely
    - Use timescale/timescaledb:latest-pg16 image
  </notes>
</story>

<story id="STORY-008" status="pending" complexity="L" tdd="required">
  <title>TimescaleDB schema and migrations</title>
  <dependencies>STORY-007</dependencies>
  <description>
    Create Alembic migration for sungrow_samples hypertable with columns for all
    SungrowSample fields. Composite PK (device_id, ts) for idempotency.
  </description>
  <acceptance_criteria>
    <ac id="AC1">Alembic migration creates sungrow_samples table as TimescaleDB hypertable</ac>
    <ac id="AC2">Composite PK on (device_id, ts)</ac>
    <ac id="AC3">Columns for: pv_power_w, pv_daily_kwh, battery_power_w, battery_soc_pct, battery_temp_c, load_power_w, export_power_w</ac>
    <ac id="AC4">SQLAlchemy ORM model matches migration</ac>
    <ac id="AC5">TimescaleDB extension created if not exists</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>vps/src/db/models.py</file>
    <file>vps/src/db/migrations/env.py</file>
    <file>vps/src/db/migrations/versions/001_initial_schema.py</file>
    <file>vps/tests/test_models.py</file>
  </allowed_scope>
  <test_first>
    <item>Create vps/tests/test_models.py FIRST</item>
    <item>Test: ORM model has all expected columns</item>
    <item>Test: composite PK on (device_id, ts)</item>
    <item>Test: model validates data types</item>
  </test_first>
  <test_plan>
    - ORM model unit tests
    - Migration SQL review
    - pytest vps/tests/ all pass
  </test_plan>
  <notes>
    - Follow P1-Edge-VPS migration pattern
    - hypertable on ts column with 7-day chunks
  </notes>
</story>

<story id="STORY-009" status="pending" complexity="S" tdd="required">
  <title>Bearer token authentication</title>
  <dependencies>STORY-007</dependencies>
  <description>
    Per-device Bearer token auth. Parse DEVICE_TOKENS env var ("tokenA:device-1,tokenB:device-2"),
    validate with constant-time comparison.
  </description>
  <acceptance_criteria>
    <ac id="AC1">DEVICE_TOKENS parsed into token→device_id mapping at startup</ac>
    <ac id="AC2">Bearer token validated with secrets.compare_digest (constant-time)</ac>
    <ac id="AC3">Valid token returns device_id</ac>
    <ac id="AC4">Invalid/missing token returns 401</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>vps/src/auth/bearer.py</file>
    <file>vps/tests/test_auth.py</file>
  </allowed_scope>
  <test_first>
    <item>Create vps/tests/test_auth.py FIRST</item>
    <item>Test: valid token returns correct device_id</item>
    <item>Test: invalid token returns 401</item>
    <item>Test: missing token returns 401</item>
    <item>Test: DEVICE_TOKENS parsing</item>
  </test_first>
  <test_plan>
    - Unit tests for token parsing and validation
    - pytest vps/tests/ all pass
  </test_plan>
  <notes>
    - Follow P1-Edge-VPS bearer.py pattern exactly
  </notes>
</story>

<story id="STORY-010" status="pending" complexity="L" tdd="required">
  <title>Ingest endpoint</title>
  <dependencies>STORY-008, STORY-009</dependencies>
  <description>
    POST /v1/ingest endpoint that accepts batch of SungrowSamples, validates device_id
    matches auth token, inserts with ON CONFLICT DO NOTHING, returns inserted count.
    Invalidates realtime cache.
  </description>
  <acceptance_criteria>
    <ac id="AC1">POST /v1/ingest accepts {"samples": [...]}</ac>
    <ac id="AC2">All samples.device_id must match authenticated device_id (403 on mismatch)</ac>
    <ac id="AC3">INSERT ON CONFLICT (device_id, ts) DO NOTHING</ac>
    <ac id="AC4">Returns {"inserted": N}</ac>
    <ac id="AC5">Invalidates Redis key realtime:{device_id} on success</ac>
    <ac id="AC6">Empty batch returns {"inserted": 0}</ac>
    <ac id="AC7">Invalid payload returns 422</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>vps/src/api/ingest.py</file>
    <file>vps/src/services/ingestion.py</file>
    <file>vps/tests/test_ingest.py</file>
  </allowed_scope>
  <test_first>
    <item>Create vps/tests/test_ingest.py FIRST</item>
    <item>Mock AsyncSession and Redis</item>
    <item>Test: valid batch returns inserted count</item>
    <item>Test: device_id mismatch returns 403</item>
    <item>Test: empty batch returns 0</item>
    <item>Test: duplicate samples not re-inserted</item>
    <item>Test: invalid payload returns 422</item>
    <item>Test: Redis cache invalidated</item>
  </test_first>
  <test_plan>
    - Integration tests with FastAPI TestClient
    - Mock DB session and Redis
    - pytest vps/tests/ all pass
  </test_plan>
  <notes>
    - Follow P1-Edge-VPS ingest.py pattern
    - Validate all sample fields before insert
  </notes>
</story>

</phase>

<!-- ============================================================ -->
<!-- PHASE 3: API FEATURES                                         -->
<!-- Story file: docs/stories/phase-3-api-features.md              -->
<!-- ============================================================ -->

<phase id="3" name="API Features" story_file="docs/stories/phase-3-api-features.md">

<story id="STORY-011" status="pending" complexity="M" tdd="required">
  <title>Realtime endpoint</title>
  <dependencies>STORY-010</dependencies>
  <description>
    GET /v1/realtime endpoint that returns the latest SungrowSample for a device.
    Uses Redis cache with configurable TTL.
  </description>
  <acceptance_criteria>
    <ac id="AC1">GET /v1/realtime?device_id=X requires Bearer auth</ac>
    <ac id="AC2">device_id must match auth token (403 on mismatch)</ac>
    <ac id="AC3">Returns latest sample from sungrow_samples</ac>
    <ac id="AC4">Redis cache with CACHE_TTL_S TTL</ac>
    <ac id="AC5">404 if no data for device</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>vps/src/api/realtime.py</file>
    <file>vps/tests/test_realtime.py</file>
  </allowed_scope>
  <test_first>
    <item>Create vps/tests/test_realtime.py FIRST</item>
    <item>Test: returns latest sample</item>
    <item>Test: Redis cache hit</item>
    <item>Test: device_id mismatch returns 403</item>
    <item>Test: no data returns 404</item>
  </test_first>
  <test_plan>
    - Integration tests with TestClient
    - Mock DB and Redis
    - pytest vps/tests/ all pass
  </test_plan>
  <notes>
    - Follow P1-Edge-VPS realtime.py pattern
  </notes>
</story>

<story id="STORY-012" status="pending" complexity="L" tdd="required">
  <title>Series endpoint (historical rollups)</title>
  <dependencies>STORY-010</dependencies>
  <description>
    GET /v1/series endpoint returning time-bucketed historical data. Supports
    frames: day (hourly), month (daily), year (monthly), all (monthly).
    Queries continuous aggregates.
  </description>
  <acceptance_criteria>
    <ac id="AC1">GET /v1/series?device_id=X&amp;frame=day returns hourly buckets for today</ac>
    <ac id="AC2">frame=month returns daily buckets for current month</ac>
    <ac id="AC3">frame=year returns monthly buckets for current year</ac>
    <ac id="AC4">frame=all returns monthly buckets all-time</ac>
    <ac id="AC5">Each bucket includes: avg_pv_power_w, avg_battery_power_w, avg_load_power_w, avg_battery_soc_pct</ac>
    <ac id="AC6">Bearer auth with device_id validation</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>vps/src/api/series.py</file>
    <file>vps/src/services/aggregation.py</file>
    <file>vps/tests/test_series.py</file>
  </allowed_scope>
  <test_first>
    <item>Create vps/tests/test_series.py FIRST</item>
    <item>Test: each frame returns correct time buckets</item>
    <item>Test: empty data returns empty series</item>
    <item>Test: invalid frame returns 422</item>
    <item>Test: auth validation</item>
  </test_first>
  <test_plan>
    - Integration tests with TestClient
    - Mock DB queries
    - pytest vps/tests/ all pass
  </test_plan>
  <notes>
    - Follow P1-Edge-VPS series.py + aggregation.py pattern
    - Depends on continuous aggregates (STORY-013) for production performance
  </notes>
</story>

<story id="STORY-013" status="pending" complexity="M" tdd="recommended">
  <title>Continuous aggregates</title>
  <dependencies>STORY-008</dependencies>
  <description>
    Alembic migration adding TimescaleDB continuous aggregate views for hourly,
    daily, and monthly rollups of sungrow_samples.
  </description>
  <acceptance_criteria>
    <ac id="AC1">sungrow_hourly continuous aggregate: time_bucket 1 hour</ac>
    <ac id="AC2">sungrow_daily continuous aggregate: time_bucket 1 day</ac>
    <ac id="AC3">sungrow_monthly continuous aggregate: time_bucket 1 month</ac>
    <ac id="AC4">All aggregates include: avg/max pv_power_w, avg battery_soc_pct, avg load_power_w, sample_count</ac>
    <ac id="AC5">Auto-refresh policies configured</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>vps/src/db/migrations/versions/002_continuous_aggregates.py</file>
  </allowed_scope>
  <test_plan>
    - Migration SQL review
    - Aggregate view definitions match schema
    - Refresh policies configured
  </test_plan>
  <notes>
    - Follow P1-Edge-VPS continuous aggregates pattern
    - Include sample_count for weighted averaging
  </notes>
</story>

</phase>

<!-- ============================================================ -->
<!-- PHASE 4: PRODUCTION                                           -->
<!-- Story file: docs/stories/phase-4-production.md                -->
<!-- ============================================================ -->

<phase id="4" name="Production" story_file="docs/stories/phase-4-production.md">

<story id="STORY-014" status="pending" complexity="L" tdd="required">
  <title>Edge main loop</title>
  <dependencies>STORY-003, STORY-004, STORY-005, STORY-006</dependencies>
  <description>
    Main asyncio entrypoint that runs poll loop and upload loop concurrently.
    Graceful shutdown on SIGTERM/SIGINT. Structured JSON logging.
  </description>
  <acceptance_criteria>
    <ac id="AC1">main.py runs poll loop (poller → normalizer → spool) at POLL_INTERVAL_S</ac>
    <ac id="AC2">main.py runs upload loop (spool → uploader) at UPLOAD_INTERVAL_S</ac>
    <ac id="AC3">Graceful shutdown on SIGTERM/SIGINT: flushes pending before exit</ac>
    <ac id="AC4">Structured JSON logging throughout</ac>
    <ac id="AC5">Health file written on each loop iteration</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>edge/src/main.py</file>
    <file>edge/tests/test_main.py</file>
  </allowed_scope>
  <test_first>
    <item>Create edge/tests/test_main.py FIRST</item>
    <item>Mock poller, normalizer, spool, uploader</item>
    <item>Test: poll loop calls poller → normalizer → spool.enqueue</item>
    <item>Test: upload loop calls spool.peek → uploader → spool.ack</item>
    <item>Test: shutdown signal triggers graceful exit</item>
  </test_first>
  <test_plan>
    - Unit tests with all components mocked
    - Test loop orchestration
    - Test shutdown behavior
    - pytest edge/tests/ all pass
  </test_plan>
  <notes>
    - Follow P1-Edge-VPS main.py pattern
    - Use asyncio (not threads) since pymodbus is async
  </notes>
</story>

<story id="STORY-015" status="pending" complexity="S" tdd="recommended">
  <title>Health checks</title>
  <dependencies>STORY-007, STORY-014</dependencies>
  <description>
    Health endpoints for both edge and VPS. Edge writes health.json file.
    VPS exposes GET /health.
  </description>
  <acceptance_criteria>
    <ac id="AC1">Edge writes /data/health.json with last_poll_ts, last_upload_ts, spool_count</ac>
    <ac id="AC2">VPS GET /health returns {"status": "ok"} (no auth required)</ac>
    <ac id="AC3">Docker HEALTHCHECK configured for both edge and VPS</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>edge/src/health.py</file>
    <file>edge/tests/test_health.py</file>
    <file>vps/src/api/health.py</file>
    <file>vps/tests/test_health.py</file>
    <file>edge/Dockerfile</file>
    <file>vps/Dockerfile</file>
  </allowed_scope>
  <test_plan>
    - Edge health file written with correct fields
    - VPS health endpoint returns 200
    - pytest all pass
  </test_plan>
  <notes>
    - Follow P1-Edge-VPS health patterns
  </notes>
</story>

<story id="STORY-016" status="pending" complexity="M" tdd="recommended">
  <title>Production hardening</title>
  <dependencies>STORY-015</dependencies>
  <description>
    Final production readiness: Dockerfiles, .env.example, structured logging,
    restart policies, graceful shutdown verification.
  </description>
  <acceptance_criteria>
    <ac id="AC1">Edge Dockerfile builds and runs</ac>
    <ac id="AC2">VPS docker-compose.yml starts all services</ac>
    <ac id="AC3">.env.example documents all required variables</ac>
    <ac id="AC4">Restart policies configured (unless-stopped)</ac>
    <ac id="AC5">All logs are structured JSON</ac>
    <ac id="AC6">ruff check and ruff format pass on full codebase</ac>
    <ac id="AC7">All tests pass</ac>
  </acceptance_criteria>
  <allowed_scope>
    <file>edge/Dockerfile</file>
    <file>vps/Dockerfile</file>
    <file>vps/docker-compose.yml</file>
    <file>.env.example</file>
    <file>.gitignore</file>
  </allowed_scope>
  <test_plan>
    - Docker build succeeds
    - docker-compose config validates
    - All tests pass
    - Lint and format clean
  </test_plan>
  <notes>
    - Final story — everything should be working before this
  </notes>
</story>

</phase>

<!-- ============================================================ -->
<!-- PROGRESS OVERVIEW                                             -->
<!-- ============================================================ -->

<progress>
  <phase_summary>
    <phase id="1" name="Edge Foundation" stories="6" done="0" progress="0%" link="stories/phase-1-edge-foundation.md" />
    <phase id="2" name="VPS Ingestion" stories="4" done="0" progress="0%" link="stories/phase-2-vps-ingestion.md" />
    <phase id="3" name="API Features" stories="3" done="0" progress="0%" link="stories/phase-3-api-features.md" />
    <phase id="4" name="Production" stories="3" done="0" progress="0%" link="stories/phase-4-production.md" />
  </phase_summary>
  <total stories="16" done="0" progress="0%" />
</progress>

<!-- ============================================================ -->
<!-- DEPENDENCY GRAPH                                              -->
<!-- ============================================================ -->

<dependency_graph>
<!--
Phase 1 (Edge):
STORY-001 (Edge scaffolding)
├── STORY-002 (Register map)
│   ├── STORY-003 (Modbus poller)
│   └── STORY-004 (Normalizer)
├── STORY-005 (SQLite spool)
│   └── STORY-006 (HTTPS uploader)

Phase 2 (VPS):
STORY-007 (VPS scaffolding)
├── STORY-008 (TimescaleDB schema)
│   ├── STORY-010 (Ingest endpoint) [also needs STORY-009]
│   └── STORY-013 (Continuous aggregates)
└── STORY-009 (Bearer auth)
    └── STORY-010 (Ingest endpoint)

Phase 3 (API):
STORY-010 (Ingest)
├── STORY-011 (Realtime)
└── STORY-012 (Series)

Phase 4 (Production):
STORY-003 + STORY-004 + STORY-005 + STORY-006 → STORY-014 (Edge main loop)
STORY-007 + STORY-014 → STORY-015 (Health checks)
STORY-015 → STORY-016 (Production hardening)

Parallelizable:
- STORY-001 and STORY-007 (edge and VPS scaffolding) can run in parallel
- STORY-003 and STORY-004 (poller and normalizer) can run in parallel after STORY-002
- STORY-005 can start as soon as STORY-001 is done (parallel with STORY-002)
- STORY-008 and STORY-009 can run in parallel after STORY-007
- STORY-011 and STORY-012 can run in parallel after STORY-010
-->
</dependency_graph>

<!-- ============================================================ -->
<!-- BLOCKED STORIES                                               -->
<!-- ============================================================ -->

<blocked>
</blocked>

<!-- ============================================================ -->
<!-- PARKING LOT                                                   -->
<!-- ============================================================ -->

<parking_lot>
  <idea>Battery cycle analysis — charge/discharge patterns, degradation tracking</idea>
  <idea>EMS mode control — read/write Sungrow EMS registers via Modbus</idea>
  <idea>Cross-pipeline correlation — merge P1 grid data with Sungrow solar/battery for full energy picture</idea>
  <idea>Alerting — battery health degradation, inverter faults, communication failures</idea>
  <idea>MPPT performance tracking — per-string monitoring and shading detection</idea>
  <idea>Grafana dashboard for operational visibility</idea>
</parking_lot>

<!-- ============================================================ -->
<!-- LABELS REFERENCE                                              -->
<!-- ============================================================ -->

<labels>
  <label name="foundation">Core infrastructure and scaffolding</label>
  <label name="edge">Edge device component</label>
  <label name="vps">VPS component</label>
  <label name="modbus">Modbus TCP communication</label>
  <label name="api">API endpoint</label>
  <label name="mvp">Required for MVP</label>
  <label name="post-mvp">Post-MVP feature</label>
</labels>

</backlog>
