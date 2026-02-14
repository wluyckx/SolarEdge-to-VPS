# Belgian Energy App — Edge-to-VPS Data Collection Pipeline

## Project Overview

A data collection and forwarding pipeline that reads real-time energy data from two local devices — a **HomeWizard P1 meter** (smart meter reader) and a **Sungrow SH4.0RS hybrid inverter** (via WiNet-S dongle) — on a home LAN, merges and buffers them on an edge device, and pushes them to a remote VPS for storage, analysis, and exposure through the Belgian Energy App API.

### Why Both Sources?

| Aspect | HomeWizard P1 | Sungrow WiNet Modbus |
|---|---|---|
| **Measures at** | Grid connection point (DSMR smart meter) | Behind-the-meter (inverter internals) |
| **Grid import/export** | ✅ Billing-grade, source of truth | ✅ Estimate (use P1 as authority) |
| **Tariff counters (T1/T2)** | ✅ Cumulative kWh per tariff | ❌ |
| **Capaciteitstarief (15-min peak)** | ✅ `average_power_15m_w`, `monthly_power_peak_w` | ❌ |
| **Gas consumption** | ✅ Via external meter on DSMR | ❌ |
| **Voltage / Current per phase** | ✅ | Partial |
| **PV production** | ❌ | ✅ Current W, daily/total kWh, per MPPT |
| **Battery SoC, power, health** | ❌ | ✅ Full battery telemetry |
| **EMS mode / control** | ❌ | ✅ Read and write |
| **Load consumption breakdown** | ❌ | ✅ Inverter-calculated |

The P1 gives billing-accurate grid data; the Sungrow gives the solar/battery decomposition. Together they power the app's core value: real-time transparency into where energy comes from, where it goes, and what it costs.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   HOME LAN                       │
│                                                  │
│  ┌──────────────┐       ┌─────────────────────┐ │
│  │ HomeWizard   │       │ Sungrow SH4.0RS     │ │
│  │ P1 Meter     │       │ (WiNet-S dongle)    │ │
│  │ REST API     │       │ Modbus TCP :502      │ │
│  └──────┬───────┘       └──────────┬──────────┘ │
│         │ HTTP (1s poll)           │ Modbus (5s) │
│         │                          │             │
│  ┌──────▼──────────────────────────▼──────────┐ │
│  │         EDGE DEVICE (Raspberry Pi)          │ │
│  │                                             │ │
│  │  ┌─────────────┐    ┌────────────────────┐  │ │
│  │  │ HW Poller   │    │ Sungrow Poller     │  │ │
│  │  │ (async HTTP)│    │ (pymodbus TCP)     │  │ │
│  │  └──────┬──────┘    └─────────┬──────────┘  │ │
│  │         │                     │              │ │
│  │  ┌──────▼─────────────────────▼──────────┐  │ │
│  │  │        Merger / Timestamper            │  │ │
│  │  └──────────────────┬────────────────────┘  │ │
│  │                     │                        │ │
│  │  ┌──────────────────▼────────────────────┐  │ │
│  │  │     Local Buffer (SQLite ring)         │  │ │
│  │  └──────────────────┬────────────────────┘  │ │
│  │                     │                        │ │
│  │  ┌──────────────────▼────────────────────┐  │ │
│  │  │     Uplink (MQTT over TLS)             │  │ │
│  │  └──────────────────┬────────────────────┘  │ │
│  └─────────────────────┼────────────────────────┘ │
└────────────────────────┼──────────────────────────┘
                         │ internet
┌────────────────────────▼──────────────────────────┐
│                      VPS                           │
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │         Mosquitto MQTT Broker (TLS)           │ │
│  └──────────────────┬───────────────────────────┘ │
│                     │                              │
│  ┌──────────────────▼───────────────────────────┐ │
│  │         Ingestion Worker                      │ │
│  │   - Validates & normalizes                    │ │
│  │   - Writes to TimescaleDB                     │ │
│  │   - Computes derived metrics                  │ │
│  └──────────────────┬───────────────────────────┘ │
│                     │                              │
│  ┌──────────────────▼───────────────────────────┐ │
│  │         TimescaleDB (PostgreSQL)              │ │
│  │   - Raw readings (hypertable, 7-day retain)   │ │
│  │   - Aggregated 1-min, 15-min, hourly, daily   │ │
│  │   - Continuous aggregates for dashboards       │ │
│  └──────────────────┬───────────────────────────┘ │
│                     │                              │
│  ┌──────────────────▼───────────────────────────┐ │
│  │         App API (FastAPI)                     │ │
│  │   - REST endpoints for the Belgian Energy App │ │
│  │   - WebSocket for real-time dashboard         │ │
│  └──────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Edge Device — Hardware & OS

- **Hardware**: Raspberry Pi 4 (2GB+ RAM) or any small Linux SBC
- **OS**: Raspberry Pi OS Lite or Ubuntu Server (headless)
- **Network**: Ethernet to home router (same LAN as HomeWizard and WiNet-S)
- **Python**: 3.11+

### 2. Edge Poller Service

A single Python async application using `asyncio` with two concurrent polling tasks.

#### 2.1 HomeWizard P1 Poller

**Protocol**: HTTP REST, local API v1 or v2
**Endpoint**: `http://<HW_IP>/api/v1/data` (v1) or `https://<HW_IP>/api/measurement` (v2 with token auth)
**Poll interval**: 1 second (matches DSMR 5.0 update rate)
**Prerequisites**: Enable "Local API" in the HomeWizard Energy app under Settings > Meters > Your meter

**Key fields to capture**:

```python
HOMEWIZARD_FIELDS = {
    # Grid power (real-time)
    "power_w": "Total active power (W), negative = exporting",
    "power_l1_w": "Phase 1 power (W)",
    # Cumulative energy counters (billing-grade)
    "energy_import_t1_kwh": "Import tariff 1 (day) total kWh",
    "energy_import_t2_kwh": "Import tariff 2 (night) total kWh",
    "energy_export_t1_kwh": "Export tariff 1 total kWh",
    "energy_export_t2_kwh": "Export tariff 2 total kWh",
    # Capaciteitstarief (Belgian capacity tariff)
    "average_power_15m_w": "Rolling 15-min average power (W)",
    "monthly_power_peak_w": "Highest 15-min peak this month (W)",
    "monthly_power_peak_timestamp": "When the monthly peak occurred",
    # Voltage quality
    "voltage_l1_v": "Phase 1 voltage",
    "current_l1_a": "Phase 1 current",
    # Gas (if available via external meter)
    "external": "Array of external devices (gas meter, water meter)",
}
```

**Library**: `aiohttp` for async HTTP polling

```python
import aiohttp
import asyncio

async def poll_homewizard(ip: str, interval: float = 1.0):
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(f"http://{ip}/api/v1/data", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    data = await resp.json()
                    yield {"source": "homewizard", "ts": time.time(), "data": data}
            except Exception as e:
                logger.warning(f"HomeWizard poll failed: {e}")
            await asyncio.sleep(interval)
```

#### 2.2 Sungrow Modbus Poller

**Protocol**: Modbus TCP
**Host**: WiNet-S IP address, **port 502**, **slave/unit ID: 1**
**Poll interval**: 5 seconds (WiNet-S needs breathing room; use `sungrow_modbus_wait_milliseconds` of ~20ms between register reads)
**Prerequisites**: Modbus TCP must be enabled on the WiNet-S dongle (access via `http://<WINET_IP>`, login admin/pw8888)

**Key Modbus registers (from Sungrow Hybrid Inverter Communication Protocol)**:

```python
SUNGROW_REGISTERS = {
    # Device info (read once at startup)
    5000: {"name": "device_type_code", "type": "U16", "desc": "Model identifier"},
    4990: {"name": "serial_number", "type": "UTF8x10", "desc": "Inverter serial"},

    # PV Production
    5011: {"name": "daily_pv_generation", "type": "U16", "unit": "0.1 kWh"},
    5004: {"name": "total_dc_power", "type": "U32", "unit": "W", "desc": "Current PV power"},
    5017: {"name": "total_pv_generation", "type": "U32", "unit": "0.1 kWh"},
    # MPPT inputs
    5012: {"name": "mppt1_voltage", "type": "U16", "unit": "0.1 V"},
    5013: {"name": "mppt1_current", "type": "U16", "unit": "0.1 A"},
    5014: {"name": "mppt2_voltage", "type": "U16", "unit": "0.1 V"},
    5015: {"name": "mppt2_current", "type": "U16", "unit": "0.1 A"},

    # Grid (inverter-side estimate)
    5083: {"name": "export_power", "type": "S32", "unit": "W", "desc": "Positive=export, Negative=import"},
    13010: {"name": "grid_power", "type": "S32", "unit": "W"},

    # Battery
    13023: {"name": "battery_power", "type": "S16", "unit": "W", "desc": "Positive=charging"},
    13022: {"name": "battery_soc", "type": "U16", "unit": "%"},
    13024: {"name": "battery_temperature", "type": "S16", "unit": "0.1 °C"},
    13026: {"name": "daily_battery_charge", "type": "U16", "unit": "0.1 kWh"},
    13027: {"name": "daily_battery_discharge", "type": "U16", "unit": "0.1 kWh"},

    # Load
    13008: {"name": "load_power", "type": "S32", "unit": "W", "desc": "Total house consumption"},
    13017: {"name": "daily_direct_consumption", "type": "U16", "unit": "0.1 kWh"},

    # EMS / Inverter state
    13000: {"name": "running_state", "type": "U16", "desc": "Bitmask of inverter state"},
    13050: {"name": "ems_mode", "type": "U16", "desc": "0=Self-consumption, 2=Forced, 3=External EMS"},
}
```

**Library**: `pymodbus` (async client)

```python
from pymodbus.client import AsyncModbusTcpClient

async def poll_sungrow(ip: str, port: int = 502, unit: int = 1, interval: float = 5.0):
    client = AsyncModbusTcpClient(ip, port=port, timeout=10)
    await client.connect()
    while True:
        try:
            readings = {}
            # Read input registers in batches (max ~100 per request for WiNet-S stability)
            result = await client.read_input_registers(address=5000, count=20, slave=unit)
            await asyncio.sleep(0.02)  # 20ms wait for WiNet-S stability
            # ... parse result.registers based on SUNGROW_REGISTERS map
            result2 = await client.read_input_registers(address=13000, count=50, slave=unit)
            await asyncio.sleep(0.02)
            # ... parse result2
            yield {"source": "sungrow", "ts": time.time(), "data": readings}
        except Exception as e:
            logger.warning(f"Sungrow poll failed: {e}, reconnecting...")
            await client.connect()
        await asyncio.sleep(interval)
```

**Important WiNet-S notes**:
- WiNet-S can be unstable; implement exponential backoff on connection failures
- Some registers available on the RT series internal LAN port may not be available on RS series via WiNet-S (notably `running_state` has been reported missing on some RS firmware versions)
- Do not poll faster than every 5 seconds; the WiNet-S has limited processing power
- If the WiNet-S becomes unresponsive, a power cycle of the dongle (not the inverter) usually helps

#### 2.3 Merger & Timestamper

Combines readings from both sources into a unified snapshot:

```python
@dataclass
class EnergySnapshot:
    timestamp: datetime          # UTC
    # Grid (from HomeWizard P1 — source of truth)
    grid_power_w: float          # positive=import, negative=export
    grid_import_t1_kwh: float
    grid_import_t2_kwh: float
    grid_export_t1_kwh: float
    grid_export_t2_kwh: float
    grid_avg_15m_w: float        # capaciteitstarief rolling average
    grid_monthly_peak_w: float   # capaciteitstarief monthly peak
    voltage_l1_v: float | None
    gas_total_m3: float | None

    # Solar (from Sungrow)
    pv_power_w: float
    pv_daily_kwh: float
    mppt1_voltage_v: float | None
    mppt1_current_a: float | None

    # Battery (from Sungrow)
    battery_power_w: float       # positive=charging, negative=discharging
    battery_soc_pct: float
    battery_temp_c: float | None
    battery_daily_charge_kwh: float
    battery_daily_discharge_kwh: float

    # Load (from Sungrow)
    load_power_w: float

    # Derived (computed on edge for immediate use)
    self_consumption_w: float    # pv_power - export
    self_sufficiency_pct: float  # (load - import) / load * 100
```

Since the two pollers run at different intervals (1s vs 5s), the merger holds the latest known value from each source and produces a merged snapshot on every P1 tick (1s). Sungrow values are carried forward until the next Sungrow reading arrives.

#### 2.4 Local Buffer (SQLite Ring Buffer)

Purpose: survive network outages and VPS downtime without losing data.

```sql
CREATE TABLE readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,          -- ISO 8601 UTC
    payload TEXT NOT NULL,            -- JSON of EnergySnapshot
    forwarded INTEGER DEFAULT 0,      -- 0=pending, 1=sent to VPS
    created_at TEXT DEFAULT (datetime('now'))
);

-- Ring buffer: keep max 7 days (~600K rows at 1/s)
-- Periodic cleanup job deletes forwarded rows older than 24h
-- Unforwarded rows are kept up to 7 days for replay
CREATE INDEX idx_readings_pending ON readings(forwarded, timestamp);
```

#### 2.5 Uplink — MQTT over TLS

**Broker**: Mosquitto on VPS, TLS with client certificate authentication
**Topics structure**:

```
energy/{device_id}/realtime      # Full snapshot, every 1s (or throttled to 5s)
energy/{device_id}/grid          # Grid-only data, every 1s
energy/{device_id}/solar         # PV production data, every 5s
energy/{device_id}/battery       # Battery telemetry, every 5s
energy/{device_id}/capacity      # Capaciteitstarief data, every 15min
energy/{device_id}/status        # Edge device health/connectivity
```

**QoS**: Use QoS 1 (at-least-once) for all energy data to ensure delivery.

```python
import aiomqtt

async def uplink(buffer_db, mqtt_host, mqtt_port=8883):
    async with aiomqtt.Client(
        hostname=mqtt_host,
        port=mqtt_port,
        tls_params=aiomqtt.TLSParameters(
            ca_certs="/etc/edge/ca.crt",
            certfile="/etc/edge/client.crt",
            keyfile="/etc/edge/client.key",
        ),
    ) as client:
        while True:
            # Fetch pending readings from buffer
            pending = fetch_pending(buffer_db, limit=50)
            for row in pending:
                await client.publish(
                    f"energy/{DEVICE_ID}/realtime",
                    payload=row.payload,
                    qos=1
                )
                mark_forwarded(buffer_db, row.id)
            await asyncio.sleep(1)
```

### 3. VPS Components

#### 3.1 Mosquitto MQTT Broker

```yaml
# /etc/mosquitto/mosquitto.conf
listener 8883
cafile /etc/mosquitto/certs/ca.crt
certfile /etc/mosquitto/certs/server.crt
keyfile /etc/mosquitto/certs/server.key
require_certificate true
use_identity_as_username true
allow_anonymous false
```

#### 3.2 Ingestion Worker

A Python service subscribing to MQTT topics and writing to TimescaleDB:

```python
async def ingest():
    async with aiomqtt.Client(hostname="localhost", port=8883, ...) as client:
        await client.subscribe("energy/+/realtime")
        async for message in client.messages:
            snapshot = json.loads(message.payload)
            # Validate schema
            # Write to TimescaleDB
            await insert_reading(snapshot)
            # Compute and cache derived metrics
            await update_derived_metrics(snapshot)
```

#### 3.3 TimescaleDB Schema

```sql
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Raw readings table
CREATE TABLE energy_readings (
    time        TIMESTAMPTZ NOT NULL,
    device_id   TEXT NOT NULL,

    -- Grid (from P1)
    grid_power_w            DOUBLE PRECISION,
    grid_import_t1_kwh      DOUBLE PRECISION,
    grid_import_t2_kwh      DOUBLE PRECISION,
    grid_export_t1_kwh      DOUBLE PRECISION,
    grid_export_t2_kwh      DOUBLE PRECISION,
    grid_avg_15m_w          DOUBLE PRECISION,
    grid_monthly_peak_w     DOUBLE PRECISION,
    voltage_l1_v            DOUBLE PRECISION,
    gas_total_m3            DOUBLE PRECISION,

    -- Solar (from Sungrow)
    pv_power_w              DOUBLE PRECISION,
    pv_daily_kwh            DOUBLE PRECISION,

    -- Battery (from Sungrow)
    battery_power_w         DOUBLE PRECISION,
    battery_soc_pct         DOUBLE PRECISION,
    battery_temp_c          DOUBLE PRECISION,

    -- Load (from Sungrow)
    load_power_w            DOUBLE PRECISION,

    -- Derived
    self_consumption_w      DOUBLE PRECISION,
    self_sufficiency_pct    DOUBLE PRECISION
);

SELECT create_hypertable('energy_readings', 'time');

-- Retention policy: raw data kept for 7 days
SELECT add_retention_policy('energy_readings', INTERVAL '7 days');

-- Continuous aggregates for dashboard queries
CREATE MATERIALIZED VIEW energy_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    device_id,
    AVG(grid_power_w) AS avg_grid_power_w,
    MAX(grid_power_w) AS max_grid_power_w,
    AVG(pv_power_w) AS avg_pv_power_w,
    MAX(pv_power_w) AS max_pv_power_w,
    AVG(battery_soc_pct) AS avg_battery_soc,
    AVG(load_power_w) AS avg_load_power_w,
    AVG(self_sufficiency_pct) AS avg_self_sufficiency,
    LAST(grid_import_t1_kwh, time) AS grid_import_t1_kwh,
    LAST(grid_import_t2_kwh, time) AS grid_import_t2_kwh,
    LAST(grid_export_t1_kwh, time) AS grid_export_t1_kwh,
    LAST(grid_export_t2_kwh, time) AS grid_export_t2_kwh,
    LAST(gas_total_m3, time) AS gas_total_m3
FROM energy_readings
GROUP BY bucket, device_id;

-- 15-minute aggregate (matches capaciteitstarief interval)
CREATE MATERIALIZED VIEW energy_15min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('15 minutes', time) AS bucket,
    device_id,
    AVG(grid_power_w) AS avg_grid_power_w,
    MAX(grid_power_w) AS peak_grid_power_w,
    AVG(pv_power_w) AS avg_pv_power_w,
    AVG(battery_soc_pct) AS avg_battery_soc,
    AVG(load_power_w) AS avg_load_power_w,
    LAST(grid_monthly_peak_w, time) AS grid_monthly_peak_w
FROM energy_readings
GROUP BY bucket, device_id;

-- Hourly aggregate
CREATE MATERIALIZED VIEW energy_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    device_id,
    AVG(grid_power_w) AS avg_grid_power_w,
    AVG(pv_power_w) AS avg_pv_power_w,
    AVG(load_power_w) AS avg_load_power_w,
    LAST(grid_import_t1_kwh, time) - FIRST(grid_import_t1_kwh, time) AS delta_import_t1_kwh,
    LAST(grid_import_t2_kwh, time) - FIRST(grid_import_t2_kwh, time) AS delta_import_t2_kwh,
    LAST(grid_export_t1_kwh, time) - FIRST(grid_export_t1_kwh, time) AS delta_export_t1_kwh,
    LAST(grid_export_t2_kwh, time) - FIRST(grid_export_t2_kwh, time) AS delta_export_t2_kwh,
    AVG(self_sufficiency_pct) AS avg_self_sufficiency
FROM energy_readings
GROUP BY bucket, device_id;

-- Daily aggregate
CREATE MATERIALIZED VIEW energy_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    device_id,
    MAX(grid_monthly_peak_w) AS capacity_tariff_peak_w,
    LAST(pv_daily_kwh, time) AS pv_production_kwh,
    LAST(grid_import_t1_kwh, time) - FIRST(grid_import_t1_kwh, time) AS grid_import_t1_kwh,
    LAST(grid_import_t2_kwh, time) - FIRST(grid_import_t2_kwh, time) AS grid_import_t2_kwh,
    LAST(grid_export_t1_kwh, time) - FIRST(grid_export_t1_kwh, time) AS grid_export_t1_kwh,
    LAST(grid_export_t2_kwh, time) - FIRST(grid_export_t2_kwh, time) AS grid_export_t2_kwh,
    LAST(gas_total_m3, time) - FIRST(gas_total_m3, time) AS gas_consumption_m3,
    AVG(self_sufficiency_pct) AS avg_self_sufficiency
FROM energy_readings
GROUP BY bucket, device_id;
```

#### 3.4 App API (FastAPI)

```python
from fastapi import FastAPI, WebSocket
from datetime import datetime, timedelta

app = FastAPI(title="Belgian Energy App API")

@app.get("/api/v1/realtime/{device_id}")
async def get_realtime(device_id: str):
    """Latest snapshot for dashboard hero numbers."""
    ...

@app.get("/api/v1/history/{device_id}")
async def get_history(device_id: str, start: datetime, end: datetime, resolution: str = "15min"):
    """Historical data at chosen resolution (1min, 15min, hourly, daily)."""
    ...

@app.get("/api/v1/capacity-tariff/{device_id}")
async def get_capacity_tariff(device_id: str, month: str | None = None):
    """Current month's capacity tariff peak and 15-min averages.
    Returns data for Belgian capaciteitstarief calculation."""
    ...

@app.get("/api/v1/self-sufficiency/{device_id}")
async def get_self_sufficiency(device_id: str, period: str = "today"):
    """Self-sufficiency and self-consumption metrics."""
    ...

@app.get("/api/v1/cost-estimate/{device_id}")
async def get_cost_estimate(device_id: str, supplier: str | None = None):
    """Estimated cost based on actual consumption and configured supplier tariffs."""
    ...

@app.websocket("/ws/v1/realtime/{device_id}")
async def ws_realtime(websocket: WebSocket, device_id: str):
    """WebSocket for real-time dashboard updates (1-5s interval)."""
    await websocket.accept()
    # Subscribe to Redis pub/sub or MQTT and forward to client
    ...
```

---

## Project Structure

```
energy-pipeline/
├── edge/                           # Runs on Raspberry Pi
│   ├── pyproject.toml
│   ├── config.yaml                 # Device IPs, poll intervals, MQTT config
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py                 # asyncio entrypoint, runs all tasks
│   │   ├── pollers/
│   │   │   ├── __init__.py
│   │   │   ├── homewizard.py       # HomeWizard P1 REST poller
│   │   │   └── sungrow.py          # Sungrow Modbus TCP poller
│   │   ├── merger.py               # Combines readings into EnergySnapshot
│   │   ├── buffer.py               # SQLite ring buffer
│   │   ├── uplink.py               # MQTT publisher with TLS
│   │   └── models.py               # Pydantic models for EnergySnapshot
│   ├── certs/                      # TLS client certs (gitignored)
│   ├── systemd/
│   │   └── energy-edge.service     # systemd unit file for auto-start
│   └── tests/
│       ├── test_homewizard.py
│       ├── test_sungrow.py
│       └── test_merger.py
│
├── vps/                            # Runs on VPS
│   ├── pyproject.toml
│   ├── docker-compose.yml          # Mosquitto + TimescaleDB + API + worker
│   ├── mosquitto/
│   │   ├── mosquitto.conf
│   │   └── certs/                  # TLS server certs
│   ├── src/
│   │   ├── __init__.py
│   │   ├── ingestion.py            # MQTT subscriber → TimescaleDB writer
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── main.py             # FastAPI app
│   │   │   ├── routes/
│   │   │   │   ├── realtime.py
│   │   │   │   ├── history.py
│   │   │   │   ├── capacity_tariff.py
│   │   │   │   └── cost_estimate.py
│   │   │   └── models.py
│   │   └── db/
│   │       ├── __init__.py
│   │       ├── schema.sql          # TimescaleDB schema + continuous aggregates
│   │       └── queries.py          # Typed query functions
│   └── tests/
│
├── shared/                         # Shared models and constants
│   ├── models.py                   # EnergySnapshot pydantic model
│   └── registers.py                # Sungrow register map
│
└── README.md
```

---

## Configuration

```yaml
# edge/config.yaml
device_id: "home-halle-vilvoorde-01"

homewizard:
  ip: "192.168.1.50"           # Find via HomeWizard Energy app or mDNS
  poll_interval_s: 1.0
  api_version: "v1"            # v1 (no auth) or v2 (token auth)
  # token: "..."               # Only needed for v2

sungrow:
  ip: "192.168.1.60"           # WiNet-S IP address
  port: 502
  slave_id: 1
  poll_interval_s: 5.0
  inter_register_delay_ms: 20  # Delay between register reads for WiNet-S stability

buffer:
  db_path: "/var/lib/energy-edge/buffer.sqlite"
  max_age_days: 7
  cleanup_interval_h: 1

mqtt:
  host: "your-vps.example.com"
  port: 8883
  tls:
    ca_cert: "/etc/energy-edge/certs/ca.crt"
    client_cert: "/etc/energy-edge/certs/client.crt"
    client_key: "/etc/energy-edge/certs/client.key"
  topic_prefix: "energy"
  qos: 1
```

---

## Deployment

### Edge (Raspberry Pi)

```bash
# Install dependencies
pip install pymodbus aiohttp aiomqtt pydantic aiosqlite

# Install as systemd service
sudo cp systemd/energy-edge.service /etc/systemd/system/
sudo systemctl enable energy-edge
sudo systemctl start energy-edge

# Monitor
journalctl -u energy-edge -f
```

```ini
# systemd/energy-edge.service
[Unit]
Description=Energy Edge Data Collector
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/energy-edge
ExecStart=/opt/energy-edge/.venv/bin/python -m src.main
Restart=always
RestartSec=10
WatchdogSec=60

[Install]
WantedBy=multi-user.target
```

### VPS (Docker Compose)

```yaml
# vps/docker-compose.yml
version: "3.8"

services:
  mosquitto:
    image: eclipse-mosquitto:2
    ports:
      - "8883:8883"
    volumes:
      - ./mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf
      - ./mosquitto/certs:/mosquitto/certs
      - mosquitto_data:/mosquitto/data

  timescaledb:
    image: timescale/timescaledb:latest-pg16
    environment:
      POSTGRES_DB: energy
      POSTGRES_USER: energy
      POSTGRES_PASSWORD: "${DB_PASSWORD}"
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - timescale_data:/var/lib/postgresql/data
      - ./src/db/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql

  ingestion:
    build: .
    command: python -m src.ingestion
    depends_on:
      - mosquitto
      - timescaledb
    environment:
      DATABASE_URL: "postgresql://energy:${DB_PASSWORD}@timescaledb:5432/energy"
      MQTT_HOST: mosquitto
    restart: always

  api:
    build: .
    command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000
    ports:
      - "127.0.0.1:8000:8000"
    depends_on:
      - timescaledb
    environment:
      DATABASE_URL: "postgresql://energy:${DB_PASSWORD}@timescaledb:5432/energy"
    restart: always

volumes:
  mosquitto_data:
  timescale_data:
```

---

## Key Belgian Energy App Features This Enables

1. **Real-time power flow visualization**: PV → Battery → Home → Grid, all from Sungrow; grid-accurate from P1
2. **Capaciteitstarief monitoring**: 15-min rolling average and monthly peak from P1, with warnings when approaching thresholds
3. **Self-sufficiency tracking**: Computed from both sources (PV production vs grid import)
4. **Cost calculation**: Apply real supplier tariffs (ENGIE, Eneco, TotalEnergies etc.) to actual T1/T2 counters
5. **Battery optimization insights**: When battery charged/discharged vs grid prices
6. **Historical analysis**: Compare days, weeks, months at multiple resolutions

---

## Development Priorities

### Phase 1: MVP Edge Poller
- [ ] HomeWizard P1 poller (async HTTP)
- [ ] Sungrow Modbus poller (pymodbus async)
- [ ] Merger producing EnergySnapshot
- [ ] SQLite buffer
- [ ] Console output for local testing (no VPS yet)

### Phase 2: VPS Ingestion
- [ ] Mosquitto setup with TLS
- [ ] MQTT uplink from edge
- [ ] Ingestion worker → TimescaleDB
- [ ] Basic schema + raw hypertable

### Phase 3: API & Aggregates
- [ ] Continuous aggregates (1min, 15min, hourly, daily)
- [ ] FastAPI endpoints (realtime, history, capacity-tariff)
- [ ] WebSocket for live dashboard

### Phase 4: Resilience & Ops
- [ ] Edge buffer replay on reconnect
- [ ] Systemd watchdog
- [ ] Health monitoring (edge heartbeat, VPS alerting)
- [ ] Grafana dashboard for ops visibility

---

## Dependencies

### Edge
```
pymodbus>=3.6
aiohttp>=3.9
aiomqtt>=2.0
aiosqlite>=0.19
pydantic>=2.0
pyyaml>=6.0
```

### VPS
```
fastapi>=0.110
uvicorn>=0.29
asyncpg>=0.29
aiomqtt>=2.0
pydantic>=2.0
```

---

## References

- HomeWizard Local API docs: https://api-documentation.homewizard.com/
- Sungrow Modbus Protocol: Request from Sungrow support or see community versions at https://github.com/bohdan-s/SunGather/issues/36
- mkaiser HA integration (register reference): https://github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant
- SunGather project: https://github.com/bohdan-s/SunGather
- SungrowInverter Python lib: https://github.com/mvandersteen/SungrowInverter
- TimescaleDB continuous aggregates: https://docs.timescale.com/use-timescale/continuous-aggregates/
- Belgian capaciteitstarief info: https://www.vreg.be/nl/capaciteitstarief
