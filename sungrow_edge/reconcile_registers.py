"""
Reconcile raw Modbus register values against GoSungrow HA sensor states.

For each iteration: reads a targeted set of Modbus input registers directly
from the WiNet-S dongle AND fetches GoSungrow sensor states from Home Assistant,
then prints them side-by-side so you can spot which register address maps to
which physical quantity.

A ★ marker highlights when a decoded register value is within 10 % of an
HA reference value (pv, battery, load, export).

Usage:
    python reconcile_registers.py --ha-token TOKEN --host 192.168.51.223

    HA_HOST env var overrides the default HA address (http://192.168.51.251:8123).

CHANGELOG:
- 2026-02-18: Fix or-bug in match logic (Python " " is truthy; or short-circuited to first
  result, hiding ×0.1/S16 matches). Replaced with explicit "★"/else comparisons.
  Update labels: 13022=soc(×0.1=%), 13023=voltage(×0.1=V). Confirmed via two-point
  reconcile: raw=138→13.8% at cloud-soc=10.2%; raw=460→46.0% at cloud-soc=44.1%.
  Δ matches charging rate × ~15min GoSungrow cloud lag.
- 2026-02-18: Add MPPT1 voltage (5012) + current (5013) probes; print computed V×I DC PV power
  after each iteration to compare against 5016 and HA pv reference.
- 2026-02-18: Add S32 pair decoding for 13007-8 (load), 13009-10 (grid), 5213-14 (battery)
  based on mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant community register map.
- 2026-02-18: Initial creation — register-vs-HA reconciliation for address mapping
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.request
from datetime import UTC, datetime

from pymodbus.client import AsyncModbusTcpClient

# ---------------------------------------------------------------------------
# Registers to probe (addresses found non-zero in the initial scan)
# ---------------------------------------------------------------------------

# (address, label, word_count)
# word_count=1: display as U16/S16/×0.1
# word_count=2: display as S32 big-endian AND S32 word-swapped (both shown)
PROBE_REGISTERS: list[tuple[int, str, int]] = [
    # MPPT1 voltage + current — V×I gives DC PV power ground truth
    (5012, "5012 mppt1_v(×0.1=V)", 1),
    (5013, "5013 mppt1_a(×0.1=A)", 1),
    # PV power — confirmed at 5016
    (5016, "5016 pv?", 1),
    # Battery power — confirmed at 5213 (S16, scale=-1)
    (5213, "5213-14 bat?(S32)", 2),
    # Battery status block (13022-13027) — confirmed 2026-02-18:
    #   13022 = SOC (×0.1=%), 13023 = voltage (×0.1=V), 13024 = temp (×0.1=°C)
    #   13025 = always 0, 13026 = lifetime discharge (kWh), 13027 = always 0
    (13022, "13022 soc(×0.1=%)", 1),
    (13023, "13023 voltage(×0.1=V)", 1),
    # Load power — community says 13007 (S32)
    (13007, "13007-8 load?(S32)", 2),
    # Grid/export — community says 13009 (S32); 5083 confirmed ILLEGAL on this firmware
    (13009, "13009-10 grid?(S32)", 2),
    # Battery status remainder
    (13024, "13024 temp(×0.1=°C)", 1),
    (13025, "13025(always 0)", 1),
    (13026, "13026 lifetime_dis(×0.1=kWh)", 1),
    (13027, "13027(always 0)", 1),
    # Unknowns that showed non-zero — kept for reference
    (5007, "5007", 1),
    (5086, "5086", 1),
    (13020, "13020(S16?)", 1),
    (13021, "13021", 1),
    (13033, "13033", 1),
]

# Contiguous blocks that cover all probe addresses — read once per iteration.
# Each entry: (start_address, count)
SCAN_BLOCKS: list[tuple[int, int]] = [
    (5007, 10),   # 5007–5016
    (5086, 1),    # 5086
    (5213, 2),    # 5213–5214  (battery S32 — mkaiser)
    (13007, 4),   # 13007–13010 (load S32 + grid S32)
    (13020, 8),   # 13020–13027 (13022=SOC, 13023=voltage, 13024=temp)
    (13033, 1),   # 13033
]

MODBUS_TIMEOUT_S = 10.0
DELAY_BETWEEN_BLOCKS_S = 0.05

# HA GoSungrow entity prefix (from existing reconcile script)
HA_PREFIX = "sensor.gosungrow_virtual_5186512_14_1_1_"
HA_ENTITIES = {
    "pv":     HA_PREFIX + "pv_power",           # kW
    "bat":    HA_PREFIX + "battery_power",       # kW (neg = discharge)
    "soc":    HA_PREFIX + "p13141",              # %
    "load":   HA_PREFIX + "load_power",          # kW
    "export": HA_PREFIX + "pv_to_grid_power",    # kW
    "temp":   HA_PREFIX + "p13143",              # °C
}

MATCH_TOLERANCE = 0.10  # 10 % relative tolerance for ★ match marker


# ---------------------------------------------------------------------------
# HA fetch (synchronous, run in executor)
# ---------------------------------------------------------------------------


def _fetch_ha_states(ha_host: str, ha_token: str) -> dict[str, float | None]:
    """Fetch GoSungrow sensor states from Home Assistant REST API.

    Returns a dict with keys: pv_w, bat_w, soc_pct, load_w, export_w, temp_c
    All power values converted to W.
    """
    url = f"{ha_host}/api/states"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {ha_token}"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
        states = json.loads(resp.read())

    by_id: dict[str, str] = {s["entity_id"]: s["state"] for s in states}

    def get_float(key: str) -> float | None:
        raw = by_id.get(HA_ENTITIES[key])
        if raw is None:
            return None
        try:
            return float(raw)
        except (ValueError, TypeError):
            return None

    pv_kw = get_float("pv")
    bat_kw = get_float("bat")
    load_kw = get_float("load")
    export_kw = get_float("export")

    return {
        "pv_w":     pv_kw * 1000 if pv_kw is not None else None,
        "bat_w":    bat_kw * 1000 if bat_kw is not None else None,
        "soc_pct":  get_float("soc"),
        "load_w":   load_kw * 1000 if load_kw is not None else None,
        "export_w": export_kw * 1000 if export_kw is not None else None,
        "temp_c":   get_float("temp"),
    }


# ---------------------------------------------------------------------------
# Modbus block read
# ---------------------------------------------------------------------------


async def _read_blocks(
    host: str,
    port: int,
    slave_id: int,
) -> dict[int, int] | None:
    """Read all scan blocks and return a flat {address: raw_u16} dict."""
    client = AsyncModbusTcpClient(host, port=port, timeout=MODBUS_TIMEOUT_S)
    try:
        ok = await client.connect()
    except Exception as exc:
        print(f"[modbus] connect failed: {exc}", file=sys.stderr)
        return None
    if not ok:
        print("[modbus] connect returned False", file=sys.stderr)
        return None

    result: dict[int, int] = {}
    try:
        for i, (start, count) in enumerate(SCAN_BLOCKS):
            if i > 0:
                await asyncio.sleep(DELAY_BETWEEN_BLOCKS_S)
            resp = await client.read_input_registers(
                start, count=count, device_id=slave_id
            )
            if resp.isError():
                print(
                    f"[modbus] error reading {start}..{start+count-1}: {resp}",
                    file=sys.stderr,
                )
                continue
            for j, raw in enumerate(resp.registers):
                result[start + j] = raw
    finally:
        client.close()

    return result


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _s16(raw: int) -> int:
    """Reinterpret a 16-bit unsigned value as signed."""
    return raw if raw < 0x8000 else raw - 0x10000


def _s32_be(hi: int, lo: int) -> int:
    """S32 big-endian: high word at lower address (standard Modbus)."""
    val = ((hi & 0xFFFF) << 16) | (lo & 0xFFFF)
    return val if val < 0x80000000 else val - 0x100000000


def _s32_ws(hi: int, lo: int) -> int:
    """S32 word-swapped: low word at lower address (some Sungrow firmware)."""
    val = ((lo & 0xFFFF) << 16) | (hi & 0xFFFF)
    return val if val < 0x80000000 else val - 0x100000000


def _match(decoded: float, ha_val: float | None) -> str:
    """Return ★ if decoded is within MATCH_TOLERANCE of ha_val."""
    if ha_val is None or ha_val == 0:
        return " "
    if abs(decoded - ha_val) / max(abs(ha_val), 1) <= MATCH_TOLERANCE:
        return "★"
    return " "


def _fmt(v: float | None, unit: str = "W", decimals: int = 0) -> str:
    if v is None:
        return "N/A"
    return f"{v:.{decimals}f}{unit}"


# ---------------------------------------------------------------------------
# Single iteration
# ---------------------------------------------------------------------------


async def _run_iteration(
    *,
    host: str,
    port: int,
    slave_id: int,
    ha_host: str,
    ha_token: str,
    loop: asyncio.AbstractEventLoop,
) -> None:
    now = datetime.now().strftime("%H:%M:%S")

    # Run Modbus read and HA fetch concurrently
    modbus_task = asyncio.create_task(
        _read_blocks(host=host, port=port, slave_id=slave_id)
    )
    ha_future = loop.run_in_executor(
        None, _fetch_ha_states, ha_host, ha_token
    )

    raw_map, ha = await asyncio.gather(modbus_task, ha_future)

    pv = ha.get("pv_w")
    bat = ha.get("bat_w")
    soc = ha.get("soc_pct")
    load = ha.get("load_w")
    exp = ha.get("export_w")
    temp = ha.get("temp_c")

    # Header row: HA reference values
    print(
        f"\n{now}  HA reference: "
        f"pv={_fmt(pv)} bat={_fmt(bat)} soc={_fmt(soc,'%',1)} "
        f"load={_fmt(load)} exp={_fmt(exp)} temp={_fmt(temp,'°C',1)}"
    )
    # Two different header formats depending on word_count
    hdr1 = f"  {'addr':<22}  {'w0':>6}  {'×1':>7}  {'×0.1':>7}  {'S16':>7}  {'pv?':>4}  {'bat?':>4}  {'soc?':>4}  {'load?':>5}  {'exp?':>4}"
    hdr2 = f"  {'addr':<22}  {'w0':>6}  {'w1':>6}  {'S32-BE':>9}  {'S32-WS':>9}  {'pv?':>4}  {'bat?':>4}  {'soc?':>4}  {'load?':>5}  {'exp?':>4}"
    print("  " + "-" * 80)

    if raw_map is None:
        print("  (Modbus read failed)")
        return

    last_wc = None
    for addr, label, wc in PROBE_REGISTERS:
        # Print sub-header when switching between 1-word and 2-word sections
        if wc != last_wc:
            print(hdr2 if wc == 2 else hdr1)
            last_wc = wc

        w0 = raw_map.get(addr)
        if w0 is None:
            print(f"  {label:<22}  (no data)")
            continue

        if wc == 2:
            w1 = raw_map.get(addr + 1, 0)
            be = _s32_be(w0, w1)
            ws = _s32_ws(w0, w1)
            m_pv   = "★" if _match(be, pv)   == "★" or _match(ws, pv)   == "★" else " "
            m_bat  = "★" if _match(be, bat)  == "★" or _match(ws, bat)  == "★" else " "
            m_soc  = "★" if _match(be, soc)  == "★" or _match(ws, soc)  == "★" else " "
            m_load = "★" if _match(be, load) == "★" or _match(ws, load) == "★" else " "
            m_exp  = "★" if _match(be, exp)  == "★" or _match(ws, exp)  == "★" else " "
            print(
                f"  {label:<22}  {w0:>6}  {w1:>6}  {be:>+9}  {ws:>+9}"
                f"  {m_pv:>4}  {m_bat:>4}  {m_soc:>4}  {m_load:>5}  {m_exp:>4}"
            )
        else:
            x1  = float(w0)
            x01 = w0 * 0.1
            s16 = float(_s16(w0))
            m_pv   = "★" if any(_match(v, pv)   == "★" for v in (x1, x01, s16)) else " "
            m_bat  = "★" if any(_match(v, bat)  == "★" for v in (x1, x01, s16)) else " "
            m_soc  = "★" if any(_match(v, soc)  == "★" for v in (x1, x01, s16)) else " "
            m_load = "★" if any(_match(v, load) == "★" for v in (x1, x01, s16)) else " "
            m_exp  = "★" if any(_match(v, exp)  == "★" for v in (x1, x01, s16)) else " "
            print(
                f"  {label:<22}  {w0:>6}  {x1:>7.0f}  {x01:>7.1f}  {s16:>+7.0f}"
                f"  {m_pv:>4}  {m_bat:>4}  {m_soc:>4}  {m_load:>5}  {m_exp:>4}"
            )

    # Computed: MPPT1 V×I as DC PV power ground truth
    v_raw = raw_map.get(5012)
    a_raw = raw_map.get(5013)
    if v_raw is not None and a_raw is not None:
        v = v_raw * 0.1
        a = a_raw * 0.1
        dc_w = v * a
        m = _match(dc_w, pv)
        pv16_raw = raw_map.get(5016)
        pv16_str = f"{pv16_raw}W" if pv16_raw is not None else "N/A"
        print(
            f"\n  MPPT1 V×I (DC):        {v:.1f}V × {a:.2f}A = {dc_w:.0f}W  {m}"
            f"  (5016={pv16_str}, HA pv={_fmt(pv)})"
        )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


async def _main(args: argparse.Namespace) -> None:
    ha_host = os.environ.get("HA_HOST", "http://192.168.51.251:8123")
    loop = asyncio.get_running_loop()

    print("Register-vs-HA reconciliation")
    print(f"WiNet-S:  {args.host}:{args.port}  slave_id={args.slave_id}")
    print(f"HA:       {ha_host}")
    print(f"Samples:  {args.iterations}  interval={args.interval}s")
    print()
    print(
        "Legend: ★ = within 10% of HA reference\n"
        "  1-word rows: ×1, ×0.1, S16 interpretations\n"
        "  2-word rows: S32-BE (big-endian, high word first) and S32-WS (word-swapped)\n"
        "  soc? column: matches HA soc_pct value"
    )

    for i in range(args.iterations):
        try:
            await _run_iteration(
                host=args.host,
                port=args.port,
                slave_id=args.slave_id,
                ha_host=ha_host,
                ha_token=args.ha_token,
                loop=loop,
            )
        except Exception as exc:
            print(f"[error] iteration {i+1}: {exc}", file=sys.stderr)

        if i < args.iterations - 1:
            await asyncio.sleep(args.interval)

    print("\nDone.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Reconcile raw Modbus registers against GoSungrow HA sensors"
    )
    p.add_argument("--ha-token", required=True, help="Home Assistant long-lived access token")
    p.add_argument("--host", required=True, help="WiNet-S IP address or hostname")
    p.add_argument("--port", type=int, default=502)
    p.add_argument("--slave-id", type=int, default=1, dest="slave_id")
    p.add_argument("--iterations", type=int, default=10)
    p.add_argument("--interval", type=float, default=5.0, help="Seconds between samples")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(_main(_parse_args()))
