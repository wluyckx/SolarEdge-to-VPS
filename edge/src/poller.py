"""
Async Modbus TCP poller for Sungrow SH4.0RS via WiNet-S dongle.

Connects to the WiNet-S Modbus TCP dongle, reads all register groups defined
in registers.py with configurable inter-register delays, and returns raw
register values as a dict.  Designed to be robust:

- Exponential backoff on connection failures (capped at MAX_BACKOFF_S).
- Never crashes the poll loop on any error.
- Respects inter-register delay (HC-004: minimum 20 ms between group reads).
- Logs warnings on errors but never propagates exceptions to the caller.

CHANGELOG:
- 2026-02-14: Allow polling to continue when optional export group is unsupported
- 2026-02-14: Initial creation (STORY-003)

TODO:
- None
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from edge.src.registers import ALL_GROUPS
from pymodbus.client import AsyncModbusTcpClient

if TYPE_CHECKING:
    from edge.src.registers import RegisterGroup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_BACKOFF_S: float = 1.0
"""Initial backoff delay in seconds after the first connection failure."""

MAX_BACKOFF_S: float = 60.0
"""Maximum backoff delay in seconds (cap for exponential growth)."""

MODBUS_TIMEOUT_S: float = 10.0
"""Timeout per Modbus TCP request in seconds (WiNet-S guideline)."""


# ---------------------------------------------------------------------------
# Stateless single-poll function
# ---------------------------------------------------------------------------


async def poll_registers(
    *,
    host: str,
    port: int = 502,
    slave_id: int = 1,
    inter_register_delay_ms: int = 20,
) -> dict[str, list[int]] | None:
    """Execute a single Modbus poll cycle and return raw register values.

    Creates a new AsyncModbusTcpClient, connects, reads every register group
    defined in :data:`~edge.src.registers.ALL_GROUPS`, and returns a flat dict
    mapping each register name to its raw 16-bit word list.

    Args:
        host: WiNet-S dongle IP address or hostname.
        port: Modbus TCP port (default 502).
        slave_id: Modbus slave / unit ID (default 1).
        inter_register_delay_ms: Milliseconds to wait between group reads
            (HC-004).  Set to 0 to skip delays.

    Returns:
        A dict of ``{register_name: [raw_word, ...]}`` on success,
        or ``None`` on any error.
    """
    client = AsyncModbusTcpClient(host, port=port, timeout=MODBUS_TIMEOUT_S)
    try:
        return await _do_poll(
            client,
            slave_id=slave_id,
            inter_register_delay_ms=inter_register_delay_ms,
        )
    except Exception:
        logger.warning(
            "Unexpected error during Modbus poll to %s:%d",
            host,
            port,
            exc_info=True,
        )
        return None
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Stateful poller with exponential backoff
# ---------------------------------------------------------------------------


class Poller:
    """Stateful Modbus TCP poller with exponential backoff.

    Maintains a failure counter so that consecutive connection failures
    cause an exponentially growing sleep before the next attempt.  The
    backoff resets to zero after any successful poll.

    Args:
        host: WiNet-S dongle IP address or hostname.
        port: Modbus TCP port (default 502).
        slave_id: Modbus slave / unit ID (default 1).
        inter_register_delay_ms: Milliseconds between group reads (HC-004).
    """

    def __init__(
        self,
        *,
        host: str,
        port: int = 502,
        slave_id: int = 1,
        inter_register_delay_ms: int = 20,
    ) -> None:
        self._host = host
        self._port = port
        self._slave_id = slave_id
        self._inter_register_delay_ms = inter_register_delay_ms
        self._consecutive_failures: int = 0

    async def poll(self) -> dict[str, list[int]] | None:
        """Execute a single poll cycle with backoff on failure.

        If there have been previous consecutive failures, sleeps for an
        exponentially increasing duration before attempting the next poll.
        On success the backoff resets to zero.

        Returns:
            A dict of ``{register_name: [raw_word, ...]}`` on success,
            or ``None`` on any error.
        """
        # Apply backoff sleep before retrying after previous failures.
        if self._consecutive_failures > 0:
            delay = min(
                BASE_BACKOFF_S * (2 ** (self._consecutive_failures - 1)),
                MAX_BACKOFF_S,
            )
            logger.warning(
                "Backoff: sleeping %.1fs before retry (consecutive failures: %d)",
                delay,
                self._consecutive_failures,
            )
            await asyncio.sleep(delay)

        client = AsyncModbusTcpClient(
            self._host,
            port=self._port,
            timeout=MODBUS_TIMEOUT_S,
        )
        try:
            result = await _do_poll(
                client,
                slave_id=self._slave_id,
                inter_register_delay_ms=self._inter_register_delay_ms,
            )
        except Exception:
            logger.warning(
                "Unexpected error during Modbus poll to %s:%d",
                self._host,
                self._port,
                exc_info=True,
            )
            result = None
        finally:
            client.close()

        if result is not None:
            self._consecutive_failures = 0
        else:
            self._consecutive_failures += 1

        return result


# ---------------------------------------------------------------------------
# Internal poll logic shared by both the stateless function and Poller
# ---------------------------------------------------------------------------


async def _do_poll(
    client: AsyncModbusTcpClient,
    *,
    slave_id: int,
    inter_register_delay_ms: int,
) -> dict[str, list[int]] | None:
    """Execute the actual poll sequence on an already-created client.

    Args:
        client: An AsyncModbusTcpClient instance (not yet connected).
        slave_id: Modbus slave / unit ID to pass as ``device_id``.
        inter_register_delay_ms: Inter-group delay in milliseconds.

    Returns:
        Complete register dict on success, or ``None`` on any error.
    """
    # -- Connect --
    try:
        ok = await client.connect()
    except Exception:
        logger.warning(
            "Failed to connect to Modbus device",
            exc_info=True,
        )
        return None

    if not ok:
        logger.warning("Failed to connect to Modbus device (connect returned False)")
        return None

    # -- Read all groups --
    delay_s = inter_register_delay_ms / 1000.0
    result: dict[str, list[int]] = {}

    for idx, group in enumerate(ALL_GROUPS):
        # Inter-register delay between groups (not before the first read)
        if idx > 0 and delay_s > 0:
            await asyncio.sleep(delay_s)

        response = await client.read_input_registers(
            group.start_address,
            count=group.count,
            device_id=slave_id,
        )

        if response.isError():
            if group.group_name == "export":
                logger.warning(
                    "Modbus error reading optional group '%s' "
                    "(address=%d, count=%d), continuing without export register",
                    group.group_name,
                    group.start_address,
                    group.count,
                )
                continue
            logger.warning(
                "Modbus error reading group '%s' (address=%d, count=%d)",
                group.group_name,
                group.start_address,
                group.count,
            )
            return None

        # Extract per-register raw word slices from the group response
        _extract_register_values(group, response.registers, result)

    return result


def _extract_register_values(
    group: RegisterGroup,
    raw_words: list[int],
    out: dict[str, list[int]],
) -> None:
    """Slice group-level raw words into per-register word lists.

    Each register's words are determined by its address offset within the
    group and its ``word_count``.

    Args:
        group: The register group definition.
        raw_words: Full list of 16-bit words returned for the group read.
        out: Output dict to populate with ``{name: [word, ...]}``.
    """
    for reg in group.registers:
        offset = reg.address - group.start_address
        out[reg.name] = raw_words[offset : offset + reg.word_count]
