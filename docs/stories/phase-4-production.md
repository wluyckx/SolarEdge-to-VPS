# Phase 4: Production

**Status**: Done
**Stories**: 3
**Completed**: 3
**Depends On**: Phase 1 (edge components), Phase 2 (VPS components)

---

## Phase Completion Criteria

This phase is complete when:
- [x] All stories have status "done"
- [x] All tests passing (`pytest edge/tests/ vps/tests/`)
- [x] Lint clean (`ruff check edge/src/ vps/src/`)
- [x] Edge daemon runs end-to-end: poll → normalize → spool → upload
- [x] VPS runs end-to-end: ingest → store → serve
- [x] Docker builds succeed for both edge and VPS
- [x] Health checks operational

---

## Stories

<story id="STORY-014" status="done" complexity="L" tdd="required">
  <title>Edge main loop</title>
  <dependencies>STORY-003, STORY-004, STORY-005, STORY-006</dependencies>

  <description>
    Main asyncio entrypoint that orchestrates two concurrent async tasks:
    1. Poll loop: poller → normalizer → spool.enqueue (every POLL_INTERVAL_S)
    2. Upload loop: spool.peek → uploader.upload → spool.ack (every UPLOAD_INTERVAL_S)

    Handles graceful shutdown on SIGTERM/SIGINT, flushing pending uploads before exit.
    Uses structured JSON logging throughout.

    Unlike P1-Edge-VPS which uses threads, this uses asyncio since pymodbus provides
    an async client natively.
  </description>

  <acceptance_criteria>
    <ac id="AC1">main.py runs poll loop (poller → normalizer → spool.enqueue) at POLL_INTERVAL_S</ac>
    <ac id="AC2">main.py runs upload loop (spool.peek → uploader → spool.ack) at UPLOAD_INTERVAL_S</ac>
    <ac id="AC3">Both loops run concurrently via asyncio</ac>
    <ac id="AC4">Graceful shutdown on SIGTERM/SIGINT: attempts to flush pending uploads before exit</ac>
    <ac id="AC5">Structured JSON logging for all events (poll success/failure, upload success/failure, startup, shutdown)</ac>
    <ac id="AC6">Health file updated on each poll loop iteration</ac>
    <ac id="AC7">Normalizer returning None (invalid data) does not enqueue to spool</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>edge/src/main.py</file>
    <file>edge/tests/test_main.py</file>
  </allowed_scope>

  <test_first>
    <item>Create edge/tests/test_main.py FIRST</item>
    <item>Mock poller, normalizer, spool, uploader, health</item>
    <item>Test: poll loop calls poller.poll() → normalizer.normalize() → spool.enqueue()</item>
    <item>Test: normalizer returning None skips spool.enqueue()</item>
    <item>Test: upload loop calls spool.peek() → uploader.upload() → spool.ack()</item>
    <item>Test: empty spool (peek returns []) skips upload</item>
    <item>Test: shutdown signal cancels loops gracefully</item>
    <item>Test: health file updated after poll</item>
  </test_first>

  <test_plan>
    - Unit tests with all components mocked
    - Test loop orchestration logic
    - Test shutdown behavior
    - Test error isolation (poll failure doesn't crash upload loop and vice versa)
    - pytest edge/tests/ all pass
  </test_plan>

  <notes>
    - Use asyncio.gather() or TaskGroup for concurrent loops
    - Each loop has its own try/except — one loop crashing should not kill the other
    - Log at startup: config summary (host, port, intervals) but NOT secrets
    - Follow P1-Edge-VPS main.py logic but use async instead of threads
  </notes>
</story>

---

<story id="STORY-015" status="done" complexity="S" tdd="recommended">
  <title>Health checks</title>
  <dependencies>STORY-007, STORY-014</dependencies>

  <description>
    Health monitoring for both edge and VPS components.

    Edge: Write a JSON health file at /data/health.json on each poll loop iteration,
    containing last_poll_ts, last_upload_ts, spool_count, and uptime.

    VPS: GET /health endpoint returning service status (no auth required).

    Docker HEALTHCHECK directives for both containers.
  </description>

  <acceptance_criteria>
    <ac id="AC1">Edge writes /data/health.json with: last_poll_ts, last_upload_ts, spool_count</ac>
    <ac id="AC2">VPS GET /health returns {"status": "ok"} with 200 (no auth required, localhost/Docker-internal only)</ac>
    <ac id="AC3">Edge Dockerfile has HEALTHCHECK testing health.json existence</ac>
    <ac id="AC4">VPS Dockerfile has HEALTHCHECK testing /health endpoint</ac>
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
    - Edge: health.write() creates valid JSON file with expected fields
    - VPS: GET /health returns 200 with {"status": "ok"}
    - Dockerfile HEALTHCHECK directives present
    - pytest all pass
  </test_plan>

  <notes>
    - Follow P1-Edge-VPS health patterns exactly
    - Edge health.py: simple function that writes JSON to configurable path
    - VPS health.py: FastAPI route, no auth dependency
    - /health must NOT be exposed publicly via Caddy; Caddyfile should not proxy /health
    - Docker HEALTHCHECK accesses /health internally (container network), never via public URL
  </notes>
</story>

---

<story id="STORY-016" status="done" complexity="M" tdd="recommended">
  <title>Production hardening</title>
  <dependencies>STORY-015</dependencies>

  <description>
    Final production readiness checks and configuration. Ensure both edge and VPS
    Docker containers build, all services start correctly, and the full pipeline
    is ready for deployment.

    This is the "polish" story — everything should already work before this.
  </description>

  <acceptance_criteria>
    <ac id="AC1">Edge Dockerfile builds successfully</ac>
    <ac id="AC2">VPS docker-compose.yml starts all services (api, postgres, redis, caddy)</ac>
    <ac id="AC3">.env.example documents all required and optional environment variables</ac>
    <ac id="AC4">Restart policies configured (unless-stopped for all services)</ac>
    <ac id="AC5">All logging is structured JSON (no print statements)</ac>
    <ac id="AC6">ruff check passes on full codebase with zero warnings</ac>
    <ac id="AC7">ruff format --check passes on full codebase</ac>
    <ac id="AC8">All tests pass (pytest edge/tests/ vps/tests/)</ac>
    <ac id="AC9">.gitignore covers: __pycache__, .env, *.db, .venv, .pytest_cache, .ruff_cache, .mypy_cache</ac>
    <ac id="AC10">Caddyfile does NOT proxy /health to public internet (internal-only endpoint)</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>edge/Dockerfile</file>
    <file>vps/Dockerfile</file>
    <file>vps/docker-compose.yml</file>
    <file>vps/Caddyfile</file>
    <file>.env.example</file>
    <file>.gitignore</file>
  </allowed_scope>

  <test_plan>
    - Docker build succeeds for edge and VPS
    - docker-compose config validates without errors
    - All tests pass
    - Lint and format clean
    - .env.example contains all documented variables
    - .gitignore covers all sensitive/generated files
  </test_plan>

  <notes>
    - This is the last story — gate for "production ready"
    - Review all previous stories' AC one more time
    - Ensure no hardcoded values leaked through
    - Verify .gitignore includes .env and spool.db
  </notes>
</story>

---

## Phase Notes

### Dependencies on Other Phases
- STORY-014 requires all Phase 1 edge components (STORY-003, 004, 005, 006)
- STORY-015 requires both edge main loop (STORY-014) and VPS scaffolding (STORY-007)
- STORY-016 requires STORY-015 (health checks) as final gate

### Known Risks
- Docker build differences between ARM (Raspberry Pi) and x86 (development). Mitigation: use multi-arch base images, test on both.
- WiNet-S may need firmware-specific register adjustments during real testing. Mitigation: register map is configurable and documented.

### Technical Debt
- No Grafana/monitoring dashboard (parking lot item)
- No alerting system (parking lot item)
- No CI/CD pipeline (future consideration)
