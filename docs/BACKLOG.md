<backlog>

<metadata>
  <project>Sungrow-to-VPS Pipeline</project>
  <last_updated>2026-02-15</last_updated>
  <total_stories>18</total_stories>
  <done>16</done>
  <progress>89%</progress>
  <changelog>
    <entry date="2026-02-15">Added Phase 5 (Documentation): STORY-017 OpenAPI reference, STORY-018 functional docs (Docusaurus)</entry>
    <entry date="2026-02-14">Doc harmonization: BACKLOG.md is now summary-only; phase story files are single source of truth for AC, allowed scope, test plans</entry>
    <entry date="2026-02-14">Initial backlog creation (16 stories across 4 phases)</entry>
  </changelog>
</metadata>

<!--
  SOURCE-OF-TRUTH RULE:
  This file tracks story STATUS, PRIORITY, and DEPENDENCIES only.
  Full story definitions (AC, allowed scope, test plans, test-first, notes) live
  exclusively in the phase story files under docs/stories/.
  The Coding Agent loads the phase story file, NOT this file, when implementing.
  If this file and a phase story file ever conflict, the phase story file wins.
-->

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
    <item>Auth hardening — token rotation, revocation, expiry (security story)</item>
    <item>Rate limiting — per-IP and per-token throttling on auth + ingest endpoints</item>
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

  <tier name="Documentation" description="API reference and functional docs (Docusaurus)">
    <entry priority="17" story="STORY-017" title="OpenAPI reference documentation" complexity="M" deps="STORY-010, STORY-011, STORY-012, STORY-016" />
    <entry priority="18" story="STORY-018" title="Functional documentation" complexity="M" deps="STORY-017" />
  </tier>
</priority_order>

<!-- ============================================================ -->
<!-- PHASE STORY SUMMARIES (status tracking only)                  -->
<!-- Full definitions in docs/stories/ files                       -->
<!-- ============================================================ -->

<phase id="1" name="Edge Foundation" story_file="docs/stories/phase-1-edge-foundation.md">
  <story id="STORY-001" status="done" complexity="M" tdd="recommended" />
  <story id="STORY-002" status="done" complexity="M" tdd="required" />
  <story id="STORY-003" status="done" complexity="L" tdd="required" />
  <story id="STORY-004" status="done" complexity="M" tdd="required" />
  <story id="STORY-005" status="done" complexity="M" tdd="required" />
  <story id="STORY-006" status="done" complexity="M" tdd="required" />
</phase>

<phase id="2" name="VPS Ingestion" story_file="docs/stories/phase-2-vps-ingestion.md">
  <story id="STORY-007" status="done" complexity="M" tdd="recommended" />
  <story id="STORY-008" status="done" complexity="L" tdd="required" />
  <story id="STORY-009" status="done" complexity="S" tdd="required" />
  <story id="STORY-010" status="done" complexity="L" tdd="required" />
</phase>

<phase id="3" name="API Features" story_file="docs/stories/phase-3-api-features.md">
  <story id="STORY-011" status="done" complexity="M" tdd="required" />
  <story id="STORY-012" status="done" complexity="L" tdd="required" />
  <story id="STORY-013" status="done" complexity="M" tdd="recommended" />
</phase>

<phase id="4" name="Production" story_file="docs/stories/phase-4-production.md">
  <story id="STORY-014" status="done" complexity="L" tdd="required" />
  <story id="STORY-015" status="done" complexity="S" tdd="recommended" />
  <story id="STORY-016" status="done" complexity="M" tdd="recommended" />
</phase>

<phase id="5" name="Documentation" story_file="docs/stories/phase-5-documentation.md">
  <story id="STORY-017" status="pending" complexity="M" tdd="not-applicable" />
  <story id="STORY-018" status="pending" complexity="M" tdd="not-applicable" />
</phase>

<!-- ============================================================ -->
<!-- PROGRESS OVERVIEW                                             -->
<!-- ============================================================ -->

<progress>
  <phase_summary>
    <phase id="1" name="Edge Foundation" stories="6" done="6" progress="100%" link="stories/phase-1-edge-foundation.md" />
    <phase id="2" name="VPS Ingestion" stories="4" done="4" progress="100%" link="stories/phase-2-vps-ingestion.md" />
    <phase id="3" name="API Features" stories="3" done="3" progress="100%" link="stories/phase-3-api-features.md" />
    <phase id="4" name="Production" stories="3" done="3" progress="100%" link="stories/phase-4-production.md" />
    <phase id="5" name="Documentation" stories="2" done="0" progress="0%" link="stories/phase-5-documentation.md" />
  </phase_summary>
  <total stories="18" done="16" progress="89%" />
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

Phase 5 (Documentation):
STORY-010 + STORY-011 + STORY-012 + STORY-016 → STORY-017 (OpenAPI reference docs)
STORY-017 → STORY-018 (Functional docs)

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
  <idea>Auth hardening — token rotation/revocation/expiry, consider JWT migration</idea>
  <idea>Rate limiting — per-IP and per-token throttling (Caddy rate_limit or middleware)</idea>
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
