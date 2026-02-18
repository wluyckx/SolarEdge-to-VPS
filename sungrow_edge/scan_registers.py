"""
Sungrow WiNet-S register scanner — diagnostic tool.

Reads wide blocks of Modbus input registers (FC04) and holding registers (FC03)
and prints every non-zero address.  Use this to locate live data when documented
register addresses return zeros.

Scanned ranges (configurable via CLI):
  FC04 input registers:  5000-5100, 13000-13060
  FC03 holding registers: 5000-5100, 13000-13060  (pass --holding to enable)

Usage:
    python scan_registers.py --host 192.168.x.x
    python scan_registers.py --host 192.168.x.x --port 502 --slave-id 1 --holding

CHANGELOG:
- 2026-02-18: Initial creation — register scan for SH4.0RS + WiNet-S address mapping
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from pymodbus.client import AsyncModbusTcpClient

# ---------------------------------------------------------------------------
# Scan configuration
# ---------------------------------------------------------------------------

CHUNK = 50          # words per Modbus request (safe for WiNet-S)
DELAY_S = 0.05      # 50 ms between requests (conservative)
TIMEOUT_S = 10.0

# Ranges to scan: (start_address, end_address_inclusive, label)
SCAN_RANGES: list[tuple[int, int, str]] = [
    (5000, 5100, "PV / device info (5000-5100)"),
    (13000, 13060, "Battery / load (13000-13060)"),
]

# Known registers from registers.py for cross-reference
KNOWN_REGISTERS: dict[int, str] = {
    4990: "serial_number[0]",
    5000: "device_type_code",
    5004: "total_dc_power[0]",
    5005: "total_dc_power[1]",
    5011: "daily_pv_generation",
    5012: "mppt1_voltage",
    5013: "mppt1_current",
    5014: "mppt2_voltage",
    5015: "mppt2_current",
    5017: "total_pv_generation[0]",
    5018: "total_pv_generation[1]",
    5083: "export_power[0]",
    5084: "export_power[1]",
    13008: "load_power[0]",
    13009: "load_power[1]",
    13010: "grid_power",
    13017: "daily_direct_consumption",
    13022: "battery_power",
    13023: "battery_soc",
    13024: "battery_temperature",
    13026: "daily_battery_discharge",
    13027: "daily_battery_charge",
}


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


async def scan_range(
    client: AsyncModbusTcpClient,
    *,
    start: int,
    end: int,
    slave_id: int,
    fc03: bool,
    label: str,
) -> list[tuple[int, int]]:
    """Scan a register range and return (address, value) pairs for non-zero words.

    Args:
        client: Connected Modbus client.
        start: First address to scan (inclusive).
        end: Last address to scan (inclusive).
        slave_id: Modbus slave / unit ID.
        fc03: If True, use FC03 (holding registers); otherwise FC04 (input registers).
        label: Human-readable range label for logging.

    Returns:
        List of (address, raw_16bit_value) tuples where value != 0.
    """
    fc_name = "FC03 holding" if fc03 else "FC04 input"
    print(f"\n{'='*70}")
    print(f"  {label}  [{fc_name}]")
    print(f"{'='*70}")

    non_zero: list[tuple[int, int]] = []
    addr = start

    while addr <= end:
        count = min(CHUNK, end - addr + 1)
        try:
            if fc03:
                resp = await client.read_holding_registers(
                    addr, count=count, device_id=slave_id
                )
            else:
                resp = await client.read_input_registers(
                    addr, count=count, device_id=slave_id
                )
        except Exception as exc:
            print(f"  [ERR] {addr}..{addr+count-1}: exception — {exc}")
            addr += count
            await asyncio.sleep(DELAY_S)
            continue

        if resp.isError():
            print(f"  [ERR] {addr}..{addr+count-1}: Modbus error — {resp}")
            addr += count
            await asyncio.sleep(DELAY_S)
            continue

        for i, raw in enumerate(resp.registers):
            abs_addr = addr + i
            if raw != 0:
                name = KNOWN_REGISTERS.get(abs_addr, "")
                tag = f"  <- {name}" if name else ""
                print(f"  addr {abs_addr:5d}  raw {raw:6d}  (0x{raw:04X}){tag}")
                non_zero.append((abs_addr, raw))

        addr += count
        await asyncio.sleep(DELAY_S)

    if not non_zero:
        print("  (all zeros in this range)")
    return non_zero


async def run_scan(
    *,
    host: str,
    port: int,
    slave_id: int,
    include_holding: bool,
) -> None:
    """Connect to the WiNet-S and scan all configured ranges.

    Args:
        host: WiNet-S IP address or hostname.
        port: Modbus TCP port.
        slave_id: Modbus slave / unit ID.
        include_holding: Also scan FC03 holding registers.
    """
    print(f"Connecting to {host}:{port} slave_id={slave_id} ...")
    client = AsyncModbusTcpClient(host, port=port, timeout=TIMEOUT_S)

    try:
        ok = await client.connect()
    except Exception as exc:
        print(f"Connection failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if not ok:
        print("Connection failed (connect() returned False)", file=sys.stderr)
        sys.exit(1)

    print("Connected.\n")

    all_hits: list[tuple[int, int, str]] = []  # (addr, value, fc_label)

    try:
        for start, end, label in SCAN_RANGES:
            hits = await scan_range(
                client,
                start=start,
                end=end,
                slave_id=slave_id,
                fc03=False,
                label=label,
            )
            all_hits.extend((a, v, "FC04") for a, v in hits)

            if include_holding:
                hits_h = await scan_range(
                    client,
                    start=start,
                    end=end,
                    slave_id=slave_id,
                    fc03=True,
                    label=label + " [holding]",
                )
                all_hits.extend((a, v, "FC03") for a, v in hits_h)
    finally:
        client.close()

    # Summary table
    print(f"\n{'='*70}")
    print("  SUMMARY — non-zero addresses")
    print(f"{'='*70}")
    if not all_hits:
        print("  No non-zero values found.")
    else:
        print(f"  {'FC':<6}  {'addr':>5}  {'raw dec':>8}  {'raw hex':>6}  name")
        print(f"  {'-'*6}  {'-----':>5}  {'--------':>8}  {'------':>6}  ----")
        for addr, val, fc in sorted(all_hits, key=lambda x: (x[0], x[2])):
            name = KNOWN_REGISTERS.get(addr, "")
            print(f"  {fc:<6}  {addr:5d}  {val:8d}  0x{val:04X}  {name}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(
        description="Sungrow WiNet-S register scanner — find non-zero addresses"
    )
    p.add_argument("--host", required=True, help="WiNet-S IP address or hostname")
    p.add_argument("--port", type=int, default=502, help="Modbus TCP port (default 502)")
    p.add_argument(
        "--slave-id", type=int, default=1, dest="slave_id",
        help="Modbus slave / unit ID (default 1)"
    )
    p.add_argument(
        "--holding", action="store_true",
        help="Also scan FC03 holding registers (in addition to FC04 input registers)"
    )
    return p.parse_args()


def main() -> None:
    """Synchronous entrypoint."""
    args = parse_args()
    asyncio.run(
        run_scan(
            host=args.host,
            port=args.port,
            slave_id=args.slave_id,
            include_holding=args.holding,
        )
    )


if __name__ == "__main__":
    main()
