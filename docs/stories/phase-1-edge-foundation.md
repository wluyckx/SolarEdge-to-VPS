# Phase 1: Edge Foundation

**Status**: Done
**Stories**: 6
**Completed**: 6
**Depends On**: None

---

## Phase Completion Criteria

This phase is complete when:
- [x] All stories have status "done"
- [x] All tests passing (`pytest edge/tests/`)
- [x] Lint clean (`ruff check edge/src/`)
- [x] Documentation updated
- [x] Edge daemon can poll Sungrow, normalize, spool, and upload to VPS

---

## Stories

<story id="STORY-001" status="done" complexity="M" tdd="recommended">
  <title>Edge scaffolding and configuration</title>
  <dependencies>None</dependencies>

  <description>
    Set up the edge/ directory structure with requirements.txt, src/ Python package,
    tests/ directory with conftest, and Pydantic Settings config loader. Config loads
    from environment variables for all Sungrow and VPS connection parameters.

    This follows the same pattern proven in P1-Edge-VPS: pydantic-settings BaseSettings
    with required and optional fields, startup validation (HTTPS scheme check), and
    sensible defaults.
  </description>

  <acceptance_criteria>
    <ac id="AC1">edge/src/ is a valid Python package with __init__.py</ac>
    <ac id="AC2">edge/src/config.py loads all required env vars via pydantic-settings</ac>
    <ac id="AC3">Config validates SUNGROW_HOST is required, SUNGROW_PORT defaults to 502</ac>
    <ac id="AC4">Config validates VPS_BASE_URL scheme is HTTPS</ac>
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
    - Config raises on missing required vars (SUNGROW_HOST, VPS_BASE_URL, VPS_DEVICE_TOKEN)
    - Config rejects http:// VPS URL
    - Config defaults SUNGROW_PORT to 502, POLL_INTERVAL_S to 5, BATCH_SIZE to 30
    - pytest edge/tests/ all pass
  </test_plan>

  <notes>
    - Follow P1-Edge-VPS edge/src/config.py pattern
    - Use pydantic-settings BaseSettings with model_config for env prefix
    - Required vars: SUNGROW_HOST, VPS_BASE_URL, VPS_DEVICE_TOKEN
    - Optional with defaults: SUNGROW_PORT(502), SUNGROW_SLAVE_ID(1), POLL_INTERVAL_S(5),
      INTER_REGISTER_DELAY_MS(20), BATCH_SIZE(30), UPLOAD_INTERVAL_S(10), SPOOL_PATH(/data/spool.db),
      DEVICE_ID(defaults to sungrow_host)
  </notes>
</story>

---

<story id="STORY-002" status="done" complexity="M" tdd="required">
  <title>Sungrow Modbus register map</title>
  <dependencies>STORY-001</dependencies>

  <description>
    Create the single source of truth for all Sungrow SH4.0RS Modbus TCP registers.
    This file defines register addresses, data types, scaling factors, units, and
    valid value ranges. Registers are grouped into contiguous ranges for efficient
    batched Modbus reads.

    The register map is derived from the Sungrow Hybrid Inverter Communication Protocol
    and community resources (mkaiser HA integration, SunGather project).

    Key register categories:
    - Device info (read once at startup): device_type_code, serial_number
    - PV production: total_dc_power, daily_pv_generation, total_pv_generation, MPPT voltages/currents
    - Battery: power, SoC, temperature, daily charge/discharge
    - Load: load_power, daily_direct_consumption
    - Grid estimate: export_power, grid_power (note: NOT billing-grade, use P1 for that)
    - Inverter state: running_state, ems_mode
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
    <item>Test: valid range min < max for all registers with ranges</item>
  </test_first>

  <test_plan>
    - Unit tests for register map integrity and consistency
    - Verify register groups are contiguous (no gaps for batched reads)
    - Verify no duplicate addresses
    - Verify all required metadata present
    - pytest edge/tests/ all pass
  </test_plan>

  <notes>
    - Reference: Sungrow Hybrid Inverter Communication Protocol (request from Sungrow support)
    - Reference: https://github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant
    - Reference: https://github.com/bohdan-s/SunGather
    - SH4.0RS via WiNet-S: some registers available on RT series may not work on RS via WiNet-S
    - Use input registers (function code 0x04) by default
    - U32 values span two consecutive registers (high word first)
    - S16 values use two's complement
  </notes>
</story>

---

<story id="STORY-003" status="done" complexity="L" tdd="required">
  <title>Modbus TCP poller</title>
  <dependencies>STORY-002</dependencies>

  <description>
    Async Modbus TCP client that connects to the WiNet-S dongle, reads all register
    groups with configurable inter-register delays, and returns raw register values.

    The poller must be robust against WiNet-S instability:
    - Exponential backoff on connection failures
    - Never crash the poll loop on any error
    - Respect inter-register delay (HC-004)
    - Log warnings on errors but never propagate exceptions to caller
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
    <item>Create edge/tests/fixtures/modbus_responses.json with realistic register values</item>
    <item>Mock pymodbus AsyncModbusTcpClient</item>
    <item>Test: successful read returns dict with all register names from registers.py</item>
    <item>Test: partial Modbus error (one group fails) returns None for entire poll</item>
    <item>Test: full connection failure returns None and triggers backoff</item>
    <item>Test: inter-register delay is called between group reads</item>
    <item>Test: backoff increases exponentially on consecutive failures</item>
    <item>Test: backoff resets after successful read</item>
  </test_first>

  <test_plan>
    - Unit tests with fully mocked pymodbus client
    - Fixture data representing real Sungrow register responses
    - Test happy path, partial failure, full failure, reconnection
    - Test backoff timing
    - pytest edge/tests/ all pass
  </test_plan>

  <notes>
    - Use pymodbus AsyncModbusTcpClient
    - slave_id from config (default 1)
    - Read input registers (read_input_registers, function code 0x04)
    - Read in batches matching register groups from registers.py
    - WiNet-S timeout: 10s per request
    - If WiNet-S becomes unresponsive, it usually needs a dongle power cycle (log this)
  </notes>
</story>

---

<story id="STORY-004" status="done" complexity="M" tdd="required">
  <title>Register normalizer</title>
  <dependencies>STORY-002</dependencies>

  <description>
    Pure function that takes raw Modbus register values (as returned by the poller)
    and converts them into a validated SungrowSample pydantic model with proper units,
    scaling, and type conversions.

    Must handle:
    - U16: unsigned 16-bit (direct value)
    - U32: unsigned 32-bit (two consecutive U16 registers, high word first)
    - S16: signed 16-bit (two's complement)
    - S32: signed 32-bit (two consecutive registers, two's complement)
    - Scaling: multiply by register's scale factor (e.g., 0.1 kWh)
    - Validation: range checks per register definition

    This is a pure function: no side effects, no I/O, no clock. Device_id and
    timestamp are accepted as parameters.
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
    <item>Test: known register values produce expected SungrowSample field values</item>
    <item>Test: U32 assembly — two registers [0x0001, 0x0000] → 65536</item>
    <item>Test: S16 negative — register 0xFFFF → -1</item>
    <item>Test: scaling — raw 1234 with scale 0.1 → 123.4</item>
    <item>Test: missing required register returns None</item>
    <item>Test: out-of-range value returns None (with warning logged)</item>
    <item>Test: device_id and ts are passed through to SungrowSample</item>
  </test_first>

  <test_plan>
    - Pure function tests with known input/output pairs
    - Test all data type conversions (U16, U32, S16, S32)
    - Test scaling factor application
    - Test validation (range checks, required fields)
    - pytest edge/tests/ all pass
  </test_plan>

  <notes>
    - SungrowSample defined in edge/src/models.py as a pydantic BaseModel
    - Accept device_id: str and ts: datetime as parameters (injected, not computed)
    - Log warnings for out-of-range values with register name and raw value
    - Sungrow convention: battery_power positive = charging, negative = discharging
  </notes>
</story>

---

<story id="STORY-005" status="done" complexity="M" tdd="required">
  <title>SQLite spool buffer</title>
  <dependencies>STORY-001</dependencies>

  <description>
    Async SQLite-based persistent FIFO buffer using WAL mode for crash safety.
    Implements the enqueue/peek/ack pattern proven in P1-Edge-VPS.

    Samples are enqueued after normalization and before upload. They remain in
    the spool until the VPS acknowledges receipt (HC-001: No Data Loss). The
    spool survives process restarts and unclean shutdowns.
  </description>

  <acceptance_criteria>
    <ac id="AC1">Spool creates SQLite database in WAL mode</ac>
    <ac id="AC2">enqueue() inserts a sample row (JSON payload)</ac>
    <ac id="AC3">peek(n) returns up to n oldest unacknowledged rows as list of (rowid, payload)</ac>
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
    <item>Test: enqueue + peek returns same payload</item>
    <item>Test: ack removes rows, subsequent peek skips them</item>
    <item>Test: count reflects only pending (unacked) rows</item>
    <item>Test: FIFO ordering (oldest first in peek)</item>
    <item>Test: WAL mode is enabled (pragma journal_mode)</item>
    <item>Test: empty spool peek returns empty list</item>
    <item>Test: peek(n) respects limit</item>
  </test_first>

  <test_plan>
    - Unit tests with in-memory or temp-file SQLite
    - Test full enqueue/peek/ack lifecycle
    - Test FIFO ordering
    - Test WAL mode
    - Test edge cases (empty spool, large batches)
    - pytest edge/tests/ all pass
  </test_plan>

  <notes>
    - Follow P1-Edge-VPS edge/src/spool.py pattern closely
    - Use aiosqlite for async SQLite
    - WAL mode set via PRAGMA at connection time
    - Store JSON payload as TEXT column
    - Include created_at column for debugging/monitoring
  </notes>
</story>

---

<story id="STORY-006" status="done" complexity="M" tdd="required">
  <title>HTTPS batch uploader</title>
  <dependencies>STORY-005</dependencies>

  <description>
    Reads batches from the SQLite spool, POSTs them to the VPS /v1/ingest endpoint
    with Bearer token authentication, and marks acknowledged rows in the spool.

    Implements exponential backoff on failure (1s → 2s → 4s → ... → 300s max).
    Validates HTTPS at startup. TLS certificate verification always enabled.

    Follows the same pattern as P1-Edge-VPS uploader.py.
  </description>

  <acceptance_criteria>
    <ac id="AC1">Uploader peeks BATCH_SIZE samples from spool</ac>
    <ac id="AC2">Uploader POSTs {"samples": [...]} to VPS_BASE_URL/v1/ingest</ac>
    <ac id="AC3">Uploader includes Bearer token in Authorization header</ac>
    <ac id="AC4">On 200 response: acks rows in spool</ac>
    <ac id="AC5">On failure (non-200, timeout, connection error): exponential backoff</ac>
    <ac id="AC6">Backoff resets to initial value on success</ac>
    <ac id="AC7">Validates VPS URL is HTTPS at startup (rejects http://)</ac>
    <ac id="AC8">TLS certificate verification always enabled (verify=True)</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>edge/src/uploader.py</file>
    <file>edge/tests/test_uploader.py</file>
  </allowed_scope>

  <test_first>
    <item>Create edge/tests/test_uploader.py FIRST</item>
    <item>Mock httpx.AsyncClient</item>
    <item>Test: successful upload (200) acks spool rows</item>
    <item>Test: 401 response does not ack rows, triggers backoff</item>
    <item>Test: 500 response triggers backoff</item>
    <item>Test: connection error triggers backoff</item>
    <item>Test: backoff doubles on consecutive failures (1→2→4→8)</item>
    <item>Test: backoff caps at max (300s)</item>
    <item>Test: backoff resets to initial on success</item>
    <item>Test: http:// URL rejected at construction/startup</item>
    <item>Test: empty batch (no rows in spool) skips upload</item>
  </test_first>

  <test_plan>
    - Unit tests with mocked httpx responses
    - Test success, auth failure, server error, timeout, connection error
    - Test exponential backoff math
    - Test HTTPS-only validation
    - pytest edge/tests/ all pass
  </test_plan>

  <notes>
    - Follow P1-Edge-VPS edge/src/uploader.py pattern
    - Use httpx.AsyncClient with verify=True (always)
    - Max backoff default: 300s, configurable via MAX_BACKOFF_S env var
    - Payload format: {"samples": [{"device_id": "...", "ts": "...", ...}, ...]}
  </notes>
</story>

---

## Phase Notes

### Dependencies on Other Phases
- No dependencies on other phases. Edge foundation is fully self-contained.
- STORY-005 (spool) can start as soon as STORY-001 (scaffolding) is done, parallel with STORY-002.
- STORY-003 (poller) and STORY-004 (normalizer) can run in parallel after STORY-002.

### Known Risks
- WiNet-S firmware differences: Some registers documented for RT series may not be available on RS via WiNet-S. Mitigation: document known gaps, make register map flexible.
- WiNet-S stability: Dongle can become unresponsive under load. Mitigation: inter-register delays, exponential backoff, clear logging for power-cycle guidance.

### Technical Debt
- Register map may need updates as firmware versions change — maintain as living document
