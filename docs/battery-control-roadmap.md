# Battery Control Roadmap — Dynamic Contract November 2026

Target: by 1 November 2026 (dynamic contract start) the SH4.0RS battery is
controlled by a price-aware planner with a proven-safe enforcement layer.
The capacity tariff (capaciteitstarief) applies **already**, so peak-shaving
value starts as soon as Phase 2 is live.

## Verified hardware facts (2026-07-18, live probe)

- WiNet-S at `192.168.10.127:502`, slave 1 (DHCP; MAC `34:86:5d:50:cb:80` —
  pin via OPNsense ISC dhcpd static mapping, manual UI task).
- Holding-register control block readable (FC03) **and writable** (FC06
  echo-write accepted on 13058).
- Battery limits from registers 33046/33047: max charge **4000 W**, max
  discharge **6600 W**. Pack: 97.0 V LFP ⇒ SBR096, 9.6 kWh nominal,
  ~8.6 kWh usable above the 10% BMS floor.
- Current state: EMS self-consumption (13049=0), force cmd stop (13050=0xCC),
  min/max SOC 10/100%, export limit 4000 W **disabled** (13086=0x55),
  backup mode disabled, backup reserve 0%.

## Control registers (0-based, per mkaiser map, cross-checked live)

| Reg | Purpose | Values |
|-----|---------|--------|
| 13049 | EMS mode | 0=self-consumption, 2=forced, 3=external EMS, 4=VPP |
| 13050 | Forced command | 0xAA=charge, 0xBB=discharge, 0xCC=stop |
| 13051 | Forced power (W) | 0–5000 |
| 13057/13058 | Max/min SOC | ×0.1% |
| 13073/13086 | Export limit W / enable | 0xAA=on, 0x55=off |
| 13074/13099 | Backup enable / reserve SOC | 0xAA/0x55, % |
| 12999 | Inverter start/stop | 0xCF=start, 0xCE=stop |
| 33046/33047 | Max charge/discharge power | ×10 W |

Command recipe: write 13051 (power) → 13049=2 (forced) → 13050 (cmd).
Revert: 13050=0xCC → 13049=0. **The inverter has no forced-mode timeout** —
the enforcement layer's deadman is what makes this safe.

## Architecture: strict chain of command

Single writer: only the edge daemon's `SungrowController` touches Modbus.
Priority: safety guardrails > manual override (HA/Telegram) > planner >
self-consumption default. Every command carries a TTL and an issuer; every
write is audited to `/data/control-audit.jsonl`.

## Phases

### Phase 1 — Enforcement layer (this branch, `feat/battery-control`)
`edge/src/control.py` + `edge/src/control_api.py` in the edge daemon
(single shared Modbus path with the poller, serialized by an asyncio lock).

Acceptance criteria:
- AC1: Commands (charge/discharge/hold/auto) validated, power clamped to
  4000/6600 W, TTL mandatory (60 s–6 h) except for auto.
- AC2: `dry_run=true` by default — full command lifecycle (accept, track,
  expire) with **zero** Modbus writes, everything audited.
- AC3: Live mode writes exactly power→mode→cmd; failed sequences are
  best-effort reverted.
- AC4: Deadman: TTL expiry, SOC floor/ceiling breach, daemon shutdown, and
  orphaned-force-mode-at-startup all revert to self-consumption. Failed
  reverts are retried every watchdog tick.
- AC5: Active command survives daemon restart (state file) and still expires.
- AC6: HTTP API (bearer token, LAN/Tailscale only): POST /control/force,
  POST /control/auto, GET /control/status, GET /control/audit.
- AC7: Poller backoff overflow bug fixed (2**n capped).

### Phase 2 — Deploy + supervised live test (late July / August)
- Sync dev→vendored trees (registers/normalizer reconcile too), bump add-on,
  deploy with `control_enabled=true, control_dry_run=true`.
- Watch dry-run audit for a week; then one supervised live test each of:
  hold, charge 2000 W/15 min, discharge 1000 W/15 min, TTL-expiry revert,
  kill-daemon-mid-force revert.
- HA glue: REST commands + dashboard buttons (Auto/Hold/Charge/Discharge),
  Telegram override via existing bot.
- Peak-guard rule (immediate value): if rolling quarter-hour grid import
  (P1 meter) approaches the monthly peak, force-discharge to shave. This
  runs from HA or a small script against the control API.

### Phase 3 — Planner in shadow mode (September–October)
- Price feed: day-ahead EPEX 15-min slots via entsoe-py (Provider-Tariff-api
  has the dependency and Belgian tariff formulas; supplier contract details
  to be plugged in when the November contract is chosen).
- Inputs: prices + Solcast (HA) + load profile (VPS TimescaleDB) + SOC.
- Start with rules (charge on cheapest N slots / negative prices when PV
  short, discharge into expensive evening slots capped at house load,
  always leave reserve for peak-guard); evaluate EMHASS or a small LP
  (PuLP/HiGHS) once rules have a baseline.
- Grid charging must be **peak-constrained, not just price-driven**:
  charge cap = monthly-peak target − current house load (P1), or a cheap
  night slot can set a new capacity-tariff peak that outweighs the saving.
- The objective must include degradation cost (~€0.02–0.05 per kWh
  cycled) and round-trip losses (~10%) — small spreads are losses.
- Shadow mode all October: planner publishes its schedule + would-be
  commands to the audit log and a dashboard; compare planned vs actual cost
  weekly. No execution.

### Phase 4 — Go live (November)
- Flip planner from shadow to execute (still through every Phase-1 guard).
- Nightly plan-vs-actual report; weekly review of savings.

## Standing risks / open items

- **Warranty check (before November):** read the SBR096 warranty terms for
  an energy-throughput / MWh cap — arbitrage roughly doubles annual
  cycling, which halves the years to any such cap. Confirm operating via
  the inverter's EMS registers keeps warranty conditions intact.
- **SOC ceiling defaults to 95%** (`control_max_soc_pct`) to limit time
  parked at full charge (LFP calendar aging). Raise deliberately only
  ahead of known high-price days.

- WiNet-S firmware updates can break Modbus (openHAB #19057: P035 regression).
  Check WiNet auto-update setting; re-run the read/echo-write probe after any
  firmware change.
- WiNet-S handles ~1 concurrent Modbus client: nothing else may talk to
  port 502 while the daemon runs (mkaiser YAML, scanners, etc.).
- Config registers (13057/13058 SOC limits) likely persist to flash — the
  planner must not write them per-cycle; forced-mode registers only.
- Injection price is low: discharge is capped at house load unless spot
  price genuinely justifies export.
- Supplier/contract choice (October): plug actual €/kWh formula into the
  planner objective.
