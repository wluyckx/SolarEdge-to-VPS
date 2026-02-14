"""
Tests for Modbus TCP poller module.

Verifies the async Modbus TCP poller that connects to the WiNet-S dongle,
reads all register groups with configurable inter-register delays, and returns
raw register values. Tests use a mocked AsyncModbusTcpClient.

CHANGELOG:
- 2026-02-14: Initial creation -- TDD tests written first (STORY-003)

TODO:
- None
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from edge.src.registers import ALL_GROUPS, ALL_REGISTERS

# ---------------------------------------------------------------------------
# Helpers: build a mock pymodbus response object
# ---------------------------------------------------------------------------


def _make_response(registers: list[int], is_error: bool = False) -> MagicMock:
    """Create a mock pymodbus response PDU.

    Args:
        registers: The list of 16-bit register values to return.
        is_error: If True, simulate a Modbus error response.
    """
    resp = MagicMock()
    resp.isError.return_value = is_error
    resp.registers = registers
    return resp


def _build_successful_responses() -> dict[str, list[int]]:
    """Build a mapping of group_name -> register values for all groups.

    Returns fake but plausible 16-bit values for every register word
    in every group defined in ALL_GROUPS.
    """
    group_values: dict[str, list[int]] = {}
    for group in ALL_GROUPS:
        # Fill the entire contiguous read with sequential values starting at 1
        group_values[group.group_name] = list(range(1, group.count + 1))
    return group_values


def _make_mock_client(
    group_values: dict[str, list[int]] | None = None,
    connect_ok: bool = True,
    error_groups: set[str] | None = None,
    raise_on_read: bool = False,
) -> AsyncMock:
    """Create a fully mocked AsyncModbusTcpClient.

    Args:
        group_values: Per-group register values. Defaults to sequential values.
        connect_ok: Whether connect() should return True.
        error_groups: Set of group_names whose reads return Modbus errors.
        raise_on_read: If True, read_input_registers raises an exception.
    """
    if group_values is None:
        group_values = _build_successful_responses()
    if error_groups is None:
        error_groups = set()

    client = AsyncMock()
    client.connect = AsyncMock(return_value=connect_ok)
    client.close = MagicMock()
    client.connected = connect_ok

    # Build a side_effect function that matches the address to a group
    async def _read_input_registers(
        address: int, *, count: int = 1, device_id: int = 1
    ) -> MagicMock:
        if raise_on_read:
            raise Exception("Simulated Modbus transport error")
        for group in ALL_GROUPS:
            if group.start_address == address and group.count == count:
                if group.group_name in error_groups:
                    return _make_response([], is_error=True)
                return _make_response(group_values[group.group_name])
        # Unexpected call -- return error
        return _make_response([], is_error=True)

    client.read_input_registers = AsyncMock(side_effect=_read_input_registers)
    return client


# ===========================================================================
# AC1: Poller connects to WiNet-S via AsyncModbusTcpClient
# ===========================================================================


class TestPollerConnect:
    """AC1: Poller connects to the WiNet-S dongle."""

    @pytest.mark.asyncio
    async def test_creates_client_with_correct_host_and_port(self) -> None:
        """Poller creates an AsyncModbusTcpClient for the configured host/port."""
        from edge.src.poller import poll_registers

        mock_client = _make_mock_client()
        with patch(
            "edge.src.poller.AsyncModbusTcpClient", return_value=mock_client
        ) as mock_cls:
            await poll_registers(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )
            mock_cls.assert_called_once_with("192.168.1.100", port=502, timeout=10)

    @pytest.mark.asyncio
    async def test_calls_connect(self) -> None:
        """Poller calls connect() on the client."""
        from edge.src.poller import poll_registers

        mock_client = _make_mock_client()
        with patch("edge.src.poller.AsyncModbusTcpClient", return_value=mock_client):
            await poll_registers(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )
            mock_client.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_closes_client_after_poll(self) -> None:
        """Poller closes the client connection after a poll cycle."""
        from edge.src.poller import poll_registers

        mock_client = _make_mock_client()
        with patch("edge.src.poller.AsyncModbusTcpClient", return_value=mock_client):
            await poll_registers(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )
            mock_client.close.assert_called_once()


# ===========================================================================
# AC2: Poller reads all register groups defined in registers.py
# ===========================================================================


class TestPollerReadsAllGroups:
    """AC2: Poller reads all register groups and returns raw values."""

    @pytest.mark.asyncio
    async def test_successful_read_returns_dict_with_all_register_names(
        self,
    ) -> None:
        """Successful poll returns a dict keyed by every register name."""
        from edge.src.poller import poll_registers

        mock_client = _make_mock_client()
        with patch("edge.src.poller.AsyncModbusTcpClient", return_value=mock_client):
            result = await poll_registers(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )

        assert result is not None
        expected_names = set(ALL_REGISTERS.keys())
        assert set(result.keys()) == expected_names

    @pytest.mark.asyncio
    async def test_reads_each_group_once(self) -> None:
        """Poller issues exactly one read_input_registers per group."""
        from edge.src.poller import poll_registers

        mock_client = _make_mock_client()
        with patch("edge.src.poller.AsyncModbusTcpClient", return_value=mock_client):
            await poll_registers(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )

        assert mock_client.read_input_registers.await_count == len(ALL_GROUPS)

    @pytest.mark.asyncio
    async def test_reads_with_correct_address_count_and_slave_id(self) -> None:
        """Each read uses the group's start_address, count, and configured slave_id."""
        from edge.src.poller import poll_registers

        mock_client = _make_mock_client()
        with patch("edge.src.poller.AsyncModbusTcpClient", return_value=mock_client):
            await poll_registers(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )

        calls = mock_client.read_input_registers.call_args_list
        for group in ALL_GROUPS:
            matching = [
                c
                for c in calls
                if c.args == (group.start_address,)
                and c.kwargs.get("count") == group.count
                and c.kwargs.get("device_id") == 1
            ]
            assert len(matching) == 1, (
                f"Expected one read for group '{group.group_name}' "
                f"at address {group.start_address} with count {group.count}"
            )

    @pytest.mark.asyncio
    async def test_raw_values_are_lists_of_ints(self) -> None:
        """Each register value in the result dict is a list of raw 16-bit ints."""
        from edge.src.poller import poll_registers

        mock_client = _make_mock_client()
        with patch("edge.src.poller.AsyncModbusTcpClient", return_value=mock_client):
            result = await poll_registers(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )

        assert result is not None
        for name, value in result.items():
            assert isinstance(value, list), (
                f"Register '{name}' should be a list, got {type(value)}"
            )
            for v in value:
                assert isinstance(v, int), (
                    f"Register '{name}' value element should be int, got {type(v)}"
                )

    @pytest.mark.asyncio
    async def test_raw_values_have_correct_word_count(self) -> None:
        """Each register's raw value list has the correct number of words."""
        from edge.src.poller import poll_registers

        mock_client = _make_mock_client()
        with patch("edge.src.poller.AsyncModbusTcpClient", return_value=mock_client):
            result = await poll_registers(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )

        assert result is not None
        for name, value in result.items():
            reg_def = ALL_REGISTERS[name]
            assert len(value) == reg_def.word_count, (
                f"Register '{name}' expected {reg_def.word_count} words, "
                f"got {len(value)}"
            )


# ===========================================================================
# AC3: Poller waits INTER_REGISTER_DELAY_MS between group reads
# ===========================================================================


class TestInterRegisterDelay:
    """AC3: Poller respects inter-register delay between group reads."""

    @pytest.mark.asyncio
    async def test_delay_called_between_group_reads(self) -> None:
        """asyncio.sleep is called between group reads with the correct delay."""
        from edge.src.poller import poll_registers

        mock_client = _make_mock_client()
        sleep_patch = patch("edge.src.poller.asyncio.sleep", new_callable=AsyncMock)
        with (
            patch(
                "edge.src.poller.AsyncModbusTcpClient",
                return_value=mock_client,
            ),
            sleep_patch as mock_sleep,
        ):
            await poll_registers(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=50,
            )

        # Sleep should be called between groups, i.e., (N-1) times for N groups
        num_groups = len(ALL_GROUPS)
        assert mock_sleep.await_count == num_groups - 1
        # Each call should use delay_seconds = 50 / 1000 = 0.05
        for call in mock_sleep.call_args_list:
            assert call.args[0] == pytest.approx(0.05)

    @pytest.mark.asyncio
    async def test_no_delay_with_zero_ms(self) -> None:
        """When inter_register_delay_ms is 0, asyncio.sleep is not called."""
        from edge.src.poller import poll_registers

        mock_client = _make_mock_client()
        sleep_patch = patch("edge.src.poller.asyncio.sleep", new_callable=AsyncMock)
        with (
            patch(
                "edge.src.poller.AsyncModbusTcpClient",
                return_value=mock_client,
            ),
            sleep_patch as mock_sleep,
        ):
            await poll_registers(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )

        mock_sleep.assert_not_awaited()


# ===========================================================================
# AC4: Poller returns dict on success or None on error
# ===========================================================================


class TestPollerReturnValues:
    """AC4: Poller returns dict of {register_name: raw_value} or None on error."""

    @pytest.mark.asyncio
    async def test_partial_modbus_error_returns_none(self) -> None:
        """If one group read returns an error, the entire poll returns None."""
        from edge.src.poller import poll_registers

        mock_client = _make_mock_client(error_groups={"pv"})
        with patch("edge.src.poller.AsyncModbusTcpClient", return_value=mock_client):
            result = await poll_registers(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_connection_failure_returns_none(self) -> None:
        """If connect() returns False, poll returns None."""
        from edge.src.poller import poll_registers

        mock_client = _make_mock_client(connect_ok=False)
        with patch("edge.src.poller.AsyncModbusTcpClient", return_value=mock_client):
            result = await poll_registers(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_exception_during_read_returns_none(self) -> None:
        """If read_input_registers raises, poll returns None (never propagates)."""
        from edge.src.poller import poll_registers

        mock_client = _make_mock_client(raise_on_read=True)
        with patch("edge.src.poller.AsyncModbusTcpClient", return_value=mock_client):
            result = await poll_registers(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_connect_raises_exception_returns_none(self) -> None:
        """If connect() raises an exception, poll returns None."""
        from edge.src.poller import poll_registers

        mock_client = _make_mock_client()
        mock_client.connect = AsyncMock(side_effect=OSError("Connection refused"))
        with patch("edge.src.poller.AsyncModbusTcpClient", return_value=mock_client):
            result = await poll_registers(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )

        assert result is None


# ===========================================================================
# AC5: Poller logs warnings on errors, never raises to caller
# ===========================================================================


class TestPollerLogging:
    """AC5: Poller logs warning on read errors, never raises to caller."""

    @pytest.mark.asyncio
    async def test_logs_warning_on_modbus_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A Modbus error response triggers a warning log."""
        from edge.src.poller import poll_registers

        mock_client = _make_mock_client(error_groups={"battery"})
        with (
            patch(
                "edge.src.poller.AsyncModbusTcpClient",
                return_value=mock_client,
            ),
            caplog.at_level(logging.WARNING),
        ):
            await poll_registers(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )

        assert any("battery" in msg.lower() for msg in caplog.messages)

    @pytest.mark.asyncio
    async def test_logs_warning_on_connection_failure(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A connection failure triggers a warning log."""
        from edge.src.poller import poll_registers

        mock_client = _make_mock_client(connect_ok=False)
        with (
            patch(
                "edge.src.poller.AsyncModbusTcpClient",
                return_value=mock_client,
            ),
            caplog.at_level(logging.WARNING),
        ):
            await poll_registers(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )

        assert any("connect" in msg.lower() for msg in caplog.messages)

    @pytest.mark.asyncio
    async def test_logs_warning_on_exception(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """An exception during read triggers a warning log."""
        from edge.src.poller import poll_registers

        mock_client = _make_mock_client(raise_on_read=True)
        with (
            patch(
                "edge.src.poller.AsyncModbusTcpClient",
                return_value=mock_client,
            ),
            caplog.at_level(logging.WARNING),
        ):
            await poll_registers(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )

        assert len(caplog.messages) > 0

    @pytest.mark.asyncio
    async def test_never_raises_to_caller(self) -> None:
        """No matter the failure mode, poll_registers never raises."""
        from edge.src.poller import poll_registers

        # Test with various failure modes -- none should raise
        for kwargs in [
            {"connect_ok": False},
            {"raise_on_read": True},
            {"error_groups": {"device", "pv", "export", "load", "battery"}},
        ]:
            mock_client = _make_mock_client(**kwargs)
            with patch(
                "edge.src.poller.AsyncModbusTcpClient",
                return_value=mock_client,
            ):
                # Should not raise
                result = await poll_registers(
                    host="192.168.1.100",
                    port=502,
                    slave_id=1,
                    inter_register_delay_ms=0,
                )
                assert result is None


# ===========================================================================
# AC6: Poller implements exponential backoff on connection failures
# ===========================================================================


class TestExponentialBackoff:
    """AC6: Poller implements exponential backoff on connection failures."""

    @pytest.mark.asyncio
    async def test_backoff_increases_exponentially_on_consecutive_failures(
        self,
    ) -> None:
        """Consecutive connection failures increase backoff exponentially."""
        from edge.src.poller import Poller

        mock_client = _make_mock_client(connect_ok=False)

        sleep_patch = patch("edge.src.poller.asyncio.sleep", new_callable=AsyncMock)
        with (
            patch(
                "edge.src.poller.AsyncModbusTcpClient",
                return_value=mock_client,
            ),
            sleep_patch as mock_sleep,
        ):
            poller = Poller(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )

            # Poll multiple times, each should fail and increase backoff
            for _ in range(4):
                await poller.poll()

        # Collect the sleep durations used for backoff
        # First poll: no backoff sleep before first attempt
        # Second poll: backoff sleep with base delay
        # Third poll: backoff sleep with 2x base delay
        # Fourth poll: backoff sleep with 4x base delay
        sleep_calls = mock_sleep.call_args_list
        backoff_delays = [c.args[0] for c in sleep_calls]

        # There should be at least 3 backoff delays (polls 2, 3, 4)
        assert len(backoff_delays) >= 3
        # Backoff should be increasing
        for i in range(1, len(backoff_delays)):
            assert backoff_delays[i] >= backoff_delays[i - 1]

    @pytest.mark.asyncio
    async def test_backoff_resets_after_successful_read(self) -> None:
        """After a successful poll, backoff delay resets to zero."""
        from edge.src.poller import Poller

        call_count = 0

        def _make_client_factory(*args, **kwargs):
            """Return alternating failing/succeeding clients."""
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return _make_mock_client(connect_ok=False)
            return _make_mock_client(connect_ok=True)

        sleep_patch = patch("edge.src.poller.asyncio.sleep", new_callable=AsyncMock)
        with (
            patch(
                "edge.src.poller.AsyncModbusTcpClient",
                side_effect=_make_client_factory,
            ),
            sleep_patch,
        ):
            poller = Poller(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )

            # Two failures
            await poller.poll()
            await poller.poll()

            # One success -- should reset backoff
            result = await poller.poll()
            assert result is not None

            # After success, internal backoff counter should be reset.
            # Verify by checking the _consecutive_failures attribute.
            assert poller._consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_backoff_has_maximum_cap(self) -> None:
        """Backoff delay is capped at a maximum value."""
        from edge.src.poller import MAX_BACKOFF_S, Poller

        mock_client = _make_mock_client(connect_ok=False)

        sleep_patch = patch("edge.src.poller.asyncio.sleep", new_callable=AsyncMock)
        with (
            patch(
                "edge.src.poller.AsyncModbusTcpClient",
                return_value=mock_client,
            ),
            sleep_patch as mock_sleep,
        ):
            poller = Poller(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )

            # Poll many times to exceed the cap
            for _ in range(20):
                await poller.poll()

        backoff_delays = [c.args[0] for c in mock_sleep.call_args_list]
        for delay in backoff_delays:
            assert delay <= MAX_BACKOFF_S

    @pytest.mark.asyncio
    async def test_first_poll_has_no_backoff_delay(self) -> None:
        """The very first poll attempt does not sleep for backoff."""
        from edge.src.poller import Poller

        mock_client = _make_mock_client(connect_ok=False)

        sleep_patch = patch("edge.src.poller.asyncio.sleep", new_callable=AsyncMock)
        with (
            patch(
                "edge.src.poller.AsyncModbusTcpClient",
                return_value=mock_client,
            ),
            sleep_patch as mock_sleep,
        ):
            poller = Poller(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )

            # First poll -- should not have a backoff sleep
            await poller.poll()

        # No sleep calls for the first poll (no backoff yet)
        mock_sleep.assert_not_awaited()


# ===========================================================================
# Integration-like: Poller class usage
# ===========================================================================


class TestPollerClass:
    """Integration tests for the Poller class workflow."""

    @pytest.mark.asyncio
    async def test_poller_poll_returns_dict_on_success(self) -> None:
        """Poller.poll() returns a complete register dict on success."""
        from edge.src.poller import Poller

        mock_client = _make_mock_client()
        with patch("edge.src.poller.AsyncModbusTcpClient", return_value=mock_client):
            poller = Poller(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )
            result = await poller.poll()

        assert result is not None
        assert set(result.keys()) == set(ALL_REGISTERS.keys())

    @pytest.mark.asyncio
    async def test_poller_poll_returns_none_on_failure(self) -> None:
        """Poller.poll() returns None when connection fails."""
        from edge.src.poller import Poller

        mock_client = _make_mock_client(connect_ok=False)
        with patch("edge.src.poller.AsyncModbusTcpClient", return_value=mock_client):
            poller = Poller(
                host="192.168.1.100",
                port=502,
                slave_id=1,
                inter_register_delay_ms=0,
            )
            result = await poller.poll()

        assert result is None

    @pytest.mark.asyncio
    async def test_poller_uses_configured_slave_id(self) -> None:
        """Poller passes the configured slave_id as device_id to reads."""
        from edge.src.poller import Poller

        group_values = _build_successful_responses()

        # Custom mock that accepts any device_id
        client = AsyncMock()
        client.connect = AsyncMock(return_value=True)
        client.close = MagicMock()
        client.connected = True

        async def _read(address: int, *, count: int = 1, device_id: int = 1):
            for group in ALL_GROUPS:
                if group.start_address == address and group.count == count:
                    return _make_response(group_values[group.group_name])
            return _make_response([], is_error=True)

        client.read_input_registers = AsyncMock(side_effect=_read)

        with patch("edge.src.poller.AsyncModbusTcpClient", return_value=client):
            poller = Poller(
                host="192.168.1.100",
                port=502,
                slave_id=7,
                inter_register_delay_ms=0,
            )
            await poller.poll()

        # Verify all reads used device_id=7
        for call in client.read_input_registers.call_args_list:
            assert call.kwargs.get("device_id") == 7
