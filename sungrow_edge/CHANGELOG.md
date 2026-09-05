# Changelog

## 0.2.3 — 2026-09-05

- Reject forced charge/discharge when battery state of charge is missing,
  invalid, or at least three configured polling intervals old (15 seconds
  with the default polling interval).
- Revert an active charge/discharge on the next watchdog tick when telemetry
  becomes unavailable. Retry failed reverts through the existing watchdog.
- Measure freshness with a monotonic clock and observe new readings before
  spool/MQTT delivery can delay them.
- Preserve dry-run settings, hold/auto commands, and existing TTL/SOC limits.

Validation: 270 edge tests, 126 VPS tests, lint and formatting checks passed.
The update does not enable live battery control or change add-on options.

For HAOS installations, rollback restores the Supervisor add-on backup made
before updating. This household now uses the standalone Docker service;
its deployment/rollback procedure is in
`docs/stories/wim-action-39-soc-freshness.md`. If
live forced control is enabled, first return the inverter to self-consumption
and verify it through the existing control API. The previous version lacks
the freshness guard; keep forced charge/discharge disabled while investigating.
