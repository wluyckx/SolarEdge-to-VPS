# WIM-ACTION-39 — Refuse stale battery SOC

Status: done (source verified; deployment tracked in Hestia action #39)
Authority: Wim, 2026-09-05: "39: fix directly".
Dependencies: existing battery-control Phase 1; no new packages.

## Acceptance criteria

- Track the age of valid SOC observations using an injectable monotonic clock.
- Reject forced charge/discharge when SOC is missing, invalid, or at least
  three configured poll intervals old (15 seconds at the default interval).
- On the next watchdog tick, revert an active charge/discharge to
  self-consumption if its SOC is missing or stale. Retry failed reverts.
- Fresh readings renew the deadline, including unchanged SOC values. Missing
  or invalid readings cannot renew it. Wall-clock changes cannot extend it.
- Keep manual auto, hold, TTL expiry, SOC limits, and dry-run behaviour intact.
- Observe SOC before awaiting spool/MQTT delivery, so downstream latency
  cannot make an old reading appear new.
- Include the same fix in the Home Assistant add-on's vendored source.

## Allowed scope

- edge/src/control.py, edge/src/main.py
- sungrow_edge/edge/src/control.py, sungrow_edge/edge/src/main.py
- edge/tests/test_control.py, edge/tests/test_main.py
- edge/src/mqtt_publisher.py and its vendored copy: formatting only, to
  clear a pre-existing failure in the repository's mandatory format gate.
- This story file

## Test plan / test-first requirements

Use fake monotonic and wall clocks, temporary state/audit files, and mocked
Modbus writes. First reproduce expired observations being accepted and an
active command continuing after telemetry stops. Cover deadline boundaries,
recovery with new telemetry, unchanged and invalid values, clock changes,
restart without telemetry, failed revert retries, dry-run, and hold/auto.
Run edge and VPS suites separately (their test packages share a name), and
ruff lint/format checks. Check vendored file equality.

## Verification — 2026-09-05

- Baseline: 248 edge tests and 126 VPS tests passed in an isolated Python
  3.12 environment using the existing dependency manifests and documented
  test tools. The unmodified format gate failed on control.py and
  mqtt_publisher.py; corrected by formatting only.
- After the fix: 270 edge tests passed (22 additional regression cases).
  The VPS code is unchanged; its 126 tests passed. No hardware was contacted.
- `ruff check edge/src/ vps/src/` passed; `ruff format --check edge/src/
  vps/src/` passed (37 files). `git diff --check` passed.
- Controller, main loop, and MQTT source match their add-on copies exactly.
- Watchdog detection occurs on its next tick (default five-second cadence).
  Physical reversion still depends on Modbus access succeeding; failed
  attempts retain the active command for retry on subsequent ticks.

## Rollback and release

Wim authorized commit, push, and deployment on 2026-09-05. Before any later
rollback on hardware, return the inverter to self-consumption through the
existing control/auto path and verify it. Revert this patch and redeploy the
previous version using the normal add-on release procedure. That restores
the known stale-SOC defect, so keep forced charge/discharge disabled until
the guard is repaired. No schema or state-file migration is introduced.

### Current deployment path (verified 2026-09-05)

HAOS has been replaced by Docker. The running `sungrow-edge` service is
defined in `/home/wlc3xkl/HomeAssistant/docker/docker-compose.yml` and builds
from this repository's `edge/Dockerfile`, with `edge/` as its build context.
Its named volume `docker_sungrow_edge_data` persists the spool and control
state. The HA add-on copy is maintained for packaging compatibility.

Pre-update runtime: `CONTROL_ENABLED=false`, `CONTROL_DRY_RUN=true`,
`POLL_INTERVAL_S=5`. Preserve these settings. Retain the previous image as
`docker-sungrow-edge:pre-soc-guard-20260905` before building. Build only
`sungrow-edge`, then use `docker compose up -d --no-deps --no-build
sungrow-edge` from the deployment directory. Verify source hashes, advancing
poll/upload timestamps, spool drainage, and stable container status.

Docker rollback: retag `docker-sungrow-edge:pre-soc-guard-20260905` as
`docker-sungrow-edge`, then recreate that one service with the same
`--no-deps --no-build` command. Keep the volume and environment unchanged.
