# Phase 3: API Features

**Status**: Not Started
**Stories**: 3
**Completed**: 0
**Depends On**: Phase 2 (STORY-010 ingest endpoint must exist)

---

## Phase Completion Criteria

This phase is complete when:
- [ ] All stories have status "done"
- [ ] All tests passing (`pytest vps/tests/`)
- [ ] Lint clean (`ruff check vps/src/`)
- [ ] VPS serves realtime and historical Sungrow data via REST API

---

## Stories

<story id="STORY-011" status="pending" complexity="M" tdd="required">
  <title>Realtime endpoint</title>
  <dependencies>STORY-010</dependencies>

  <description>
    GET /v1/realtime endpoint that returns the most recent SungrowSample for a device.
    Uses Redis cache with configurable TTL to minimize database queries. Requires
    Bearer token auth with device_id validation.
  </description>

  <acceptance_criteria>
    <ac id="AC1">GET /v1/realtime?device_id=X requires Bearer auth</ac>
    <ac id="AC2">Query device_id must match auth token's device_id (403 on mismatch)</ac>
    <ac id="AC3">Returns latest sample from sungrow_samples ORDER BY ts DESC LIMIT 1</ac>
    <ac id="AC4">Redis cache with CACHE_TTL_S TTL (default 5s)</ac>
    <ac id="AC5">404 if no data exists for device</ac>
    <ac id="AC6">Response includes all SungrowSample fields</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>vps/src/api/realtime.py</file>
    <file>vps/tests/test_realtime.py</file>
  </allowed_scope>

  <test_first>
    <item>Create vps/tests/test_realtime.py FIRST</item>
    <item>Mock AsyncSession and Redis</item>
    <item>Test: returns latest sample with all fields</item>
    <item>Test: Redis cache hit returns cached data (no DB query)</item>
    <item>Test: Redis cache miss queries DB and caches result</item>
    <item>Test: device_id mismatch returns 403</item>
    <item>Test: no data returns 404</item>
    <item>Test: no auth returns 401</item>
  </test_first>

  <test_plan>
    - Integration tests with FastAPI TestClient
    - Mock DB and Redis
    - Test cache hit/miss behavior
    - Test auth validation
    - pytest vps/tests/ all pass
  </test_plan>

  <notes>
    - Follow P1-Edge-VPS vps/src/api/realtime.py pattern
    - Cache key format: realtime:{device_id}
    - Cache value: JSON-serialized sample
  </notes>
</story>

---

<story id="STORY-012" status="pending" complexity="L" tdd="required">
  <title>Series endpoint (historical rollups)</title>
  <dependencies>STORY-010</dependencies>

  <description>
    GET /v1/series endpoint returning time-bucketed historical data at different
    resolutions. Queries continuous aggregates (STORY-013) when available, falls
    back to raw table with time_bucket for development.

    Supported frames:
    - day: hourly buckets for current day
    - month: daily buckets for current month
    - year: monthly buckets for current year
    - all: monthly buckets all-time

    Each bucket includes averaged PV, battery, load, and SoC metrics.
  </description>

  <acceptance_criteria>
    <ac id="AC1">GET /v1/series?device_id=X&amp;frame=day returns hourly buckets for today</ac>
    <ac id="AC2">frame=month returns daily buckets for current month</ac>
    <ac id="AC3">frame=year returns monthly buckets for current year</ac>
    <ac id="AC4">frame=all returns monthly buckets all-time</ac>
    <ac id="AC5">Each bucket: avg_pv_power_w, max_pv_power_w, avg_battery_power_w, avg_battery_soc_pct, avg_load_power_w, avg_export_power_w, sample_count</ac>
    <ac id="AC6">Bearer auth with device_id validation (403 on mismatch)</ac>
    <ac id="AC7">Invalid frame returns 422</ac>
    <ac id="AC8">Empty result returns empty series list</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>vps/src/api/series.py</file>
    <file>vps/src/services/aggregation.py</file>
    <file>vps/tests/test_series.py</file>
  </allowed_scope>

  <test_first>
    <item>Create vps/tests/test_series.py FIRST</item>
    <item>Mock AsyncSession</item>
    <item>Test: frame=day returns hourly-bucketed data</item>
    <item>Test: frame=month returns daily-bucketed data</item>
    <item>Test: frame=year returns monthly-bucketed data</item>
    <item>Test: frame=all returns monthly-bucketed data</item>
    <item>Test: invalid frame returns 422</item>
    <item>Test: empty result returns {"series": []}</item>
    <item>Test: auth validation (401/403)</item>
  </test_first>

  <test_plan>
    - Integration tests with FastAPI TestClient
    - Mock DB queries returning fixture data
    - Test each frame type
    - Test auth and validation
    - pytest vps/tests/ all pass
  </test_plan>

  <notes>
    - Follow P1-Edge-VPS series.py + aggregation.py pattern
    - Use FRAME_CONFIG dict mapping frame → (source_view, bucket_size, time_range)
    - For development: query raw table with time_bucket()
    - For production: query continuous aggregate views (STORY-013)
  </notes>
</story>

---

<story id="STORY-013" status="done" complexity="M" tdd="recommended">
  <title>Continuous aggregates</title>
  <dependencies>STORY-008</dependencies>

  <description>
    Alembic migration adding TimescaleDB continuous aggregate materialized views
    for automated rollups. Three views: hourly, daily, monthly.

    Each view aggregates PV power, battery power/SoC, load power, and export power
    with automatic refresh policies.
  </description>

  <acceptance_criteria>
    <ac id="AC1">sungrow_hourly continuous aggregate with time_bucket('1 hour')</ac>
    <ac id="AC2">sungrow_daily continuous aggregate with time_bucket('1 day')</ac>
    <ac id="AC3">sungrow_monthly continuous aggregate with time_bucket('1 month')</ac>
    <ac id="AC4">All aggregates include: avg_pv_power_w, max_pv_power_w, avg_battery_power_w, avg_battery_soc_pct, avg_load_power_w, avg_export_power_w, sample_count</ac>
    <ac id="AC5">Auto-refresh policies configured for each aggregate</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>vps/src/db/migrations/versions/002_continuous_aggregates.py</file>
  </allowed_scope>

  <test_plan>
    - Migration SQL review
    - Aggregate view column definitions match expected schema
    - Refresh policy intervals are reasonable (hourly: 1h, daily: 1d, monthly: 1d)
    - Migration applies cleanly (tested against fresh DB)
  </test_plan>

  <notes>
    - Follow P1-Edge-VPS 002_continuous_aggregates.py pattern
    - Include sample_count for weighted averaging in aggregation service
    - Refresh policies:
      - Hourly: start_offset 3h, end_offset 1h, schedule 1h
      - Daily: start_offset 3 days, end_offset 1 day, schedule 1 day
      - Monthly: start_offset 3 months, end_offset 1 month, schedule 1 day
  </notes>
</story>

---

## Phase Notes

### Dependencies on Other Phases
- Phase 2 STORY-010 (ingest) must be complete — read endpoints need data to query
- STORY-013 (continuous aggregates) depends only on STORY-008 (schema), not on STORY-010

### Known Risks
- Continuous aggregate performance depends on data volume. At 5s poll interval, expect ~17K samples/day per device. This is well within TimescaleDB capabilities.

### Technical Debt
- No WebSocket support for live streaming (see parking lot). REST polling is sufficient for MVP.
