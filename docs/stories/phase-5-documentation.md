# Phase 5: Documentation

**Status**: Not Started
**Stories**: 2
**Completed**: 0
**Depends On**: Phase 3 (API endpoints), Phase 4 (production readiness)

---

## Phase Completion Criteria

This phase is complete when:
- [ ] All stories have status "done"
- [ ] Docusaurus site builds without errors
- [ ] OpenAPI spec matches implemented endpoints
- [ ] All API endpoints have request/response examples
- [ ] Functional documentation covers full pipeline architecture

---

## Stories

<story id="STORY-017" status="pending" complexity="M" tdd="not-applicable">
  <title>OpenAPI reference documentation (Docusaurus)</title>
  <dependencies>STORY-010, STORY-011, STORY-012, STORY-016</dependencies>

  <description>
    Create a Docusaurus documentation site with auto-generated API reference
    from the FastAPI OpenAPI spec. Covers all four VPS endpoints:
    POST /v1/ingest, GET /v1/realtime, GET /v1/series, GET /health.

    Includes request/response examples, authentication instructions,
    error code reference, and rate/size limits. The OpenAPI schema is
    extracted from the running FastAPI app and rendered via a Docusaurus
    OpenAPI plugin.
  </description>

  <acceptance_criteria>
    <ac id="AC1">Docusaurus project scaffolded in docs/site/ with build passing (`npm run build`)</ac>
    <ac id="AC2">OpenAPI spec exported from FastAPI app and saved as docs/site/static/openapi.json</ac>
    <ac id="AC3">API reference page renders all endpoints with method, path, parameters, request body, and responses</ac>
    <ac id="AC4">POST /v1/ingest documented with: payload schema, batch size limit (MAX_SAMPLES_PER_REQUEST), body size limit (MAX_REQUEST_BYTES), ON CONFLICT DO NOTHING idempotency, example request/response</ac>
    <ac id="AC5">GET /v1/realtime documented with: query params, Redis caching behaviour (CACHE_TTL_S), all SungrowSample response fields, example request/response</ac>
    <ac id="AC6">GET /v1/series documented with: frame parameter (day/month/year/all), source views per frame, bucket field schema, example request/response</ac>
    <ac id="AC7">Authentication section: Bearer token format, 401/403 error semantics, DEVICE_TOKENS configuration</ac>
    <ac id="AC8">Error reference page: 400, 401, 403, 404, 413, 422 with descriptions and example bodies</ac>
    <ac id="AC9">GET /health documented as internal-only (not proxied via Caddy)</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>docs/site/**</file>
    <file>docs/site/package.json</file>
    <file>docs/site/docusaurus.config.js</file>
    <file>docs/site/sidebars.js</file>
    <file>docs/site/static/openapi.json</file>
    <file>docs/site/docs/api/**</file>
  </allowed_scope>

  <test_plan>
    - `npm run build` in docs/site/ succeeds without errors
    - openapi.json contains all 4 endpoints with correct methods and paths
    - Each endpoint doc page includes at least one request and one response example
    - Authentication section references Bearer token format
    - Error reference covers all documented HTTP status codes
  </test_plan>

  <notes>
    - Use `docusaurus-plugin-openapi-docs` or `redocusaurus` for OpenAPI rendering
    - Extract OpenAPI spec via: `python -c "from src.api.main import app; import json; print(json.dumps(app.openapi()))"` from vps/
    - FastAPI already generates OpenAPI 3.1 schema; Pydantic models provide field descriptions
    - Consider enriching FastAPI route decorators with `summary`, `description`, and `response_model` if current output lacks detail — but do NOT change endpoint behaviour
    - The OpenAPI spec is a static export, not a live proxy — regenerate when endpoints change
    - Docusaurus version: use latest 3.x
  </notes>
</story>

---

<story id="STORY-018" status="pending" complexity="M" tdd="not-applicable">
  <title>Functional documentation (Docusaurus)</title>
  <dependencies>STORY-017</dependencies>

  <description>
    Extend the Docusaurus site with functional documentation covering
    the full Sungrow-to-VPS pipeline architecture, deployment guide,
    configuration reference, and operational runbook.

    This is the "how it works and how to run it" companion to the API
    reference from STORY-017. Target audience: operators deploying the
    pipeline on a Raspberry Pi (edge) and VPS (server).
  </description>

  <acceptance_criteria>
    <ac id="AC1">Architecture overview page with data flow diagram: Sungrow inverter -> WiNet-S -> Edge (Modbus TCP) -> SQLite spool -> HTTPS upload -> VPS (FastAPI) -> TimescaleDB -> API consumers</ac>
    <ac id="AC2">Edge daemon page: poll loop, upload loop, graceful shutdown, health file, structured logging, retry/backoff strategy</ac>
    <ac id="AC3">VPS server page: FastAPI app structure, TimescaleDB schema, continuous aggregates (hourly/daily/monthly), Redis caching layer</ac>
    <ac id="AC4">Configuration reference page: all environment variables for edge and VPS (from .env.example), grouped by component, with types, defaults, and validation rules</ac>
    <ac id="AC5">Deployment guide: Docker build instructions for edge (ARM + x86), docker-compose up for VPS, Caddy TLS setup, DEVICE_TOKENS provisioning</ac>
    <ac id="AC6">Operational runbook: health check interpretation, common failure modes (Modbus timeout, spool growth, Redis unavailability, DB connection loss), troubleshooting steps</ac>
    <ac id="AC7">Data model page: SungrowSample fields with units, Modbus register map reference (register names, addresses, data types, scaling factors)</ac>
    <ac id="AC8">Security page: HTTPS-only boundary, Bearer auth model, Caddy /health exclusion, non-root containers, idempotent ingestion as DoS mitigation</ac>
    <ac id="AC9">`npm run build` passes, sidebar navigation is logical (Getting Started > Architecture > Edge > VPS > API Reference > Deployment > Operations)</ac>
  </acceptance_criteria>

  <allowed_scope>
    <file>docs/site/docs/**</file>
    <file>docs/site/sidebars.js</file>
    <file>docs/site/static/img/**</file>
    <file>docs/site/src/**</file>
  </allowed_scope>

  <test_plan>
    - `npm run build` in docs/site/ succeeds without errors or broken links
    - All sidebar sections render and navigate correctly
    - Architecture diagram is present and legible
    - Configuration reference covers all variables from .env.example
    - Deployment guide has step-by-step instructions for both edge and VPS
    - No placeholder "TODO" sections remain in published pages
  </test_plan>

  <notes>
    - Use Mermaid diagrams (Docusaurus supports them natively) for architecture and data flow
    - Pull configuration variable documentation from .env.example to avoid drift
    - Reference register map from edge/src/registers.py for the data model page
    - Deployment guide should mention multi-arch Docker builds for Raspberry Pi (ARM64)
    - Keep language concise and operator-focused — this is a runbook, not a tutorial
    - Sidebar order: Introduction, Architecture, Edge Daemon, VPS Server, API Reference (from STORY-017), Configuration, Deployment, Operations, Security
  </notes>
</story>

---

## Phase Notes

### Dependencies on Other Phases
- STORY-017 requires all API endpoints to be implemented (Phase 3) and production hardening complete (Phase 4)
- STORY-018 depends on STORY-017 (extends the same Docusaurus site)

### Scope Boundaries
- Documentation only — no changes to application code (edge/src/, vps/src/)
- Exception: FastAPI route decorators may be enriched with descriptions/summaries to improve OpenAPI output, but endpoint behaviour must not change
- No new Python tests required (TDD not applicable for docs)

### Known Risks
- OpenAPI spec may lack detail if Pydantic models don't have field descriptions. Mitigation: enrich models with `Field(description=...)` if needed.
- Docusaurus OpenAPI plugins may have compatibility issues with OpenAPI 3.1 (FastAPI default). Mitigation: test plugin compatibility early, downgrade spec to 3.0 if needed.
