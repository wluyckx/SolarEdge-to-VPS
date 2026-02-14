"""
Unit tests for the async SQLite spool (local buffer) module.

Tests verify:
- Spool creates SQLite DB with WAL mode at configurable path.
- enqueue(payload) inserts a JSON payload row.
- peek(n) returns up to n oldest unacknowledged rows as list of (rowid, payload).
- ack(rowids) deletes only the specified rows.
- count() returns number of pending samples.
- FIFO ordering (oldest first in peek).
- WAL mode is enabled (pragma journal_mode).
- Empty spool peek returns empty list.
- peek(n) respects limit.
- Concurrent read/write without corruption.
- Persistence across close/reopen.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-005)

TODO:
- None
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from edge.src.spool import Spool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_payload(
    device_id: str = "sungrow-test",
    ts: str = "2026-02-14T10:00:00Z",
    pv_power_w: int = 3500,
    battery_soc_pct: float = 72.5,
) -> str:
    """Return a valid JSON payload string matching the spool use case."""
    return json.dumps(
        {
            "device_id": device_id,
            "ts": ts,
            "pv_power_w": pv_power_w,
            "battery_soc_pct": battery_soc_pct,
        }
    )


# ---------------------------------------------------------------------------
# WAL mode and DB creation (AC1)
# ---------------------------------------------------------------------------


class TestSpoolCreation:
    """Spool creates a SQLite database with WAL journal mode."""

    @pytest.mark.asyncio
    async def test_creates_db_file_at_configured_path(self, tmp_path: Path) -> None:
        """AC1: spool creates SQLite DB at configurable path."""
        db_path = tmp_path / "test_spool.db"
        spool = Spool(path=db_path)
        await spool.open()

        assert db_path.exists()
        await spool.close()

    @pytest.mark.asyncio
    async def test_wal_mode_enabled(self, tmp_path: Path) -> None:
        """AC1: WAL journal mode is set on the database."""
        import aiosqlite

        db_path = tmp_path / "wal_test.db"
        spool = Spool(path=db_path)
        await spool.open()

        # Verify WAL mode via a separate connection.
        async with aiosqlite.connect(str(db_path)) as conn:
            cursor = await conn.execute("PRAGMA journal_mode;")
            row = await cursor.fetchone()
            journal_mode = row[0]

        assert journal_mode == "wal"
        await spool.close()

    @pytest.mark.asyncio
    async def test_accepts_string_path(self, tmp_path: Path) -> None:
        """Constructor accepts both str and Path objects."""
        db_path = str(tmp_path / "str_path.db")
        spool = Spool(path=db_path)
        await spool.open()

        assert Path(db_path).exists()
        await spool.close()

    @pytest.mark.asyncio
    async def test_accepts_path_object(self, tmp_path: Path) -> None:
        """Constructor accepts pathlib.Path objects."""
        db_path = tmp_path / "path_obj.db"
        spool = Spool(path=db_path)
        await spool.open()

        assert db_path.exists()
        await spool.close()

    @pytest.mark.asyncio
    async def test_async_context_manager(self, tmp_path: Path) -> None:
        """Spool supports async context manager protocol."""
        db_path = tmp_path / "ctx_mgr.db"
        async with Spool(path=db_path) as spool:
            assert db_path.exists()
            await spool.enqueue(_make_payload())

        # After exiting, the spool should have been closed.
        assert db_path.exists()


# ---------------------------------------------------------------------------
# enqueue + peek (AC2 + AC3)
# ---------------------------------------------------------------------------


class TestEnqueueAndPeek:
    """enqueue inserts JSON payloads; peek returns them with rowids."""

    @pytest.mark.asyncio
    async def test_enqueue_peek_returns_same_payload(self, tmp_path: Path) -> None:
        """AC2 + AC3: enqueue inserts a row and peek returns it with correct payload."""
        async with Spool(path=tmp_path / "spool.db") as spool:
            payload = _make_payload()
            await spool.enqueue(payload)

            rows = await spool.peek(10)

            assert len(rows) == 1
            rowid, returned_payload = rows[0]
            assert isinstance(rowid, int)
            assert returned_payload == payload

    @pytest.mark.asyncio
    async def test_enqueue_stores_valid_json(self, tmp_path: Path) -> None:
        """AC2: enqueue stores a valid JSON string that can be parsed back."""
        async with Spool(path=tmp_path / "spool.db") as spool:
            original = {
                "device_id": "test",
                "ts": "2026-02-14T12:00:00Z",
                "pv_power_w": 1500,
            }
            payload = json.dumps(original)
            await spool.enqueue(payload)

            rows = await spool.peek(1)
            _, returned_payload = rows[0]
            parsed = json.loads(returned_payload)

            assert parsed == original

    @pytest.mark.asyncio
    async def test_peek_on_empty_spool_returns_empty_list(self, tmp_path: Path) -> None:
        """AC3: peek on empty spool returns an empty list."""
        async with Spool(path=tmp_path / "spool.db") as spool:
            rows = await spool.peek(10)
            assert rows == []

    @pytest.mark.asyncio
    async def test_peek_limits_returned_rows(self, tmp_path: Path) -> None:
        """AC3: peek(n) returns at most n rows."""
        async with Spool(path=tmp_path / "spool.db") as spool:
            for i in range(5):
                await spool.enqueue(_make_payload(ts=f"2026-02-14T10:00:0{i}Z"))

            rows = await spool.peek(3)
            assert len(rows) == 3

    @pytest.mark.asyncio
    async def test_peek_with_zero_returns_empty(self, tmp_path: Path) -> None:
        """peek(0) returns empty list."""
        async with Spool(path=tmp_path / "spool.db") as spool:
            await spool.enqueue(_make_payload())
            rows = await spool.peek(0)
            assert rows == []


# ---------------------------------------------------------------------------
# FIFO ordering (AC3)
# ---------------------------------------------------------------------------


class TestFIFOOrdering:
    """peek returns oldest samples first, preserving insertion order."""

    @pytest.mark.asyncio
    async def test_peek_returns_oldest_first(self, tmp_path: Path) -> None:
        """AC3: peek returns oldest (lowest rowid) first."""
        async with Spool(path=tmp_path / "spool.db") as spool:
            payloads = [
                _make_payload(ts="2026-02-14T10:00:00Z"),
                _make_payload(ts="2026-02-14T10:00:01Z"),
                _make_payload(ts="2026-02-14T10:00:02Z"),
            ]
            for p in payloads:
                await spool.enqueue(p)

            rows = await spool.peek(3)

            assert [payload for _, payload in rows] == payloads

    @pytest.mark.asyncio
    async def test_multiple_enqueues_maintain_insertion_order(
        self, tmp_path: Path
    ) -> None:
        """Multiple enqueues maintain insertion order; rowids increase."""
        async with Spool(path=tmp_path / "spool.db") as spool:
            devices = ["dev-1", "dev-2", "dev-3", "dev-4", "dev-5"]
            for dev in devices:
                await spool.enqueue(_make_payload(device_id=dev))

            rows = await spool.peek(10)

            # Payloads should come back in insertion order.
            returned_devices = [json.loads(payload)["device_id"] for _, payload in rows]
            assert returned_devices == devices

            # Rowids must be monotonically increasing.
            rowids = [rowid for rowid, _ in rows]
            assert rowids == sorted(rowids)


# ---------------------------------------------------------------------------
# ack (AC4)
# ---------------------------------------------------------------------------


class TestAck:
    """ack(rowids) deletes only the specified rows."""

    @pytest.mark.asyncio
    async def test_ack_removes_specified_rows(self, tmp_path: Path) -> None:
        """AC4: ack deletes the acknowledged rows."""
        async with Spool(path=tmp_path / "spool.db") as spool:
            for i in range(3):
                await spool.enqueue(_make_payload(ts=f"2026-02-14T10:00:0{i}Z"))

            rows = await spool.peek(3)
            # Ack the first two rows.
            await spool.ack([rows[0][0], rows[1][0]])

            remaining = await spool.peek(10)
            assert len(remaining) == 1
            # The remaining row should be the third one.
            remaining_payload = json.loads(remaining[0][1])
            assert remaining_payload["ts"] == "2026-02-14T10:00:02Z"

    @pytest.mark.asyncio
    async def test_ack_leaves_unspecified_rows(self, tmp_path: Path) -> None:
        """AC4: ack does not touch rows that are not in the rowids list."""
        async with Spool(path=tmp_path / "spool.db") as spool:
            await spool.enqueue(_make_payload(device_id="keep-1"))
            await spool.enqueue(_make_payload(device_id="remove"))
            await spool.enqueue(_make_payload(device_id="keep-2"))

            rows = await spool.peek(3)
            remove_rowid = [
                rowid
                for rowid, payload in rows
                if json.loads(payload)["device_id"] == "remove"
            ]
            await spool.ack(remove_rowid)

            remaining = await spool.peek(10)
            remaining_devices = [
                json.loads(payload)["device_id"] for _, payload in remaining
            ]
            assert "keep-1" in remaining_devices
            assert "keep-2" in remaining_devices
            assert "remove" not in remaining_devices

    @pytest.mark.asyncio
    async def test_ack_empty_list_does_nothing(self, tmp_path: Path) -> None:
        """ack([]) does not raise and does not delete anything."""
        async with Spool(path=tmp_path / "spool.db") as spool:
            await spool.enqueue(_make_payload())

            await spool.ack([])

            assert await spool.count() == 1

    @pytest.mark.asyncio
    async def test_ack_nonexistent_rowids_does_not_raise(self, tmp_path: Path) -> None:
        """ack with nonexistent rowids completes without error."""
        async with Spool(path=tmp_path / "spool.db") as spool:
            await spool.enqueue(_make_payload())

            await spool.ack([9999, 8888])

            assert await spool.count() == 1

    @pytest.mark.asyncio
    async def test_ack_then_peek_skips_acked_rows(self, tmp_path: Path) -> None:
        """AC4: after ack, subsequent peek does not return acked rows."""
        async with Spool(path=tmp_path / "spool.db") as spool:
            await spool.enqueue(_make_payload(ts="2026-02-14T10:00:00Z"))
            await spool.enqueue(_make_payload(ts="2026-02-14T10:00:01Z"))

            rows = await spool.peek(1)
            await spool.ack([rows[0][0]])

            remaining = await spool.peek(10)
            assert len(remaining) == 1
            assert json.loads(remaining[0][1])["ts"] == "2026-02-14T10:00:01Z"


# ---------------------------------------------------------------------------
# count (AC5)
# ---------------------------------------------------------------------------


class TestCount:
    """count() returns the number of pending samples."""

    @pytest.mark.asyncio
    async def test_count_empty_spool(self, tmp_path: Path) -> None:
        """AC5: count is 0 on a freshly created spool."""
        async with Spool(path=tmp_path / "spool.db") as spool:
            assert await spool.count() == 0

    @pytest.mark.asyncio
    async def test_count_after_enqueue(self, tmp_path: Path) -> None:
        """AC5: count reflects number of enqueued samples."""
        async with Spool(path=tmp_path / "spool.db") as spool:
            await spool.enqueue(_make_payload(ts="2026-02-14T10:00:00Z"))
            await spool.enqueue(_make_payload(ts="2026-02-14T10:00:01Z"))
            await spool.enqueue(_make_payload(ts="2026-02-14T10:00:02Z"))

            assert await spool.count() == 3

    @pytest.mark.asyncio
    async def test_count_after_ack(self, tmp_path: Path) -> None:
        """AC5: count decreases after ack."""
        async with Spool(path=tmp_path / "spool.db") as spool:
            await spool.enqueue(_make_payload(ts="2026-02-14T10:00:00Z"))
            await spool.enqueue(_make_payload(ts="2026-02-14T10:00:01Z"))

            rows = await spool.peek(2)
            await spool.ack([rows[0][0]])

            assert await spool.count() == 1

    @pytest.mark.asyncio
    async def test_count_reflects_only_pending(self, tmp_path: Path) -> None:
        """AC5: count is accurate after mixed enqueue/ack operations."""
        async with Spool(path=tmp_path / "spool.db") as spool:
            # Enqueue 5.
            for i in range(5):
                await spool.enqueue(_make_payload(ts=f"2026-02-14T10:00:0{i}Z"))
            assert await spool.count() == 5

            # Ack 2.
            rows = await spool.peek(2)
            await spool.ack([r[0] for r in rows])
            assert await spool.count() == 3

            # Enqueue 1 more.
            await spool.enqueue(_make_payload(ts="2026-02-14T10:00:05Z"))
            assert await spool.count() == 4


# ---------------------------------------------------------------------------
# Parameterized SQL (AC6)
# ---------------------------------------------------------------------------


class TestParameterizedSQL:
    """All queries use parameterized SQL to prevent SQL injection."""

    @pytest.mark.asyncio
    async def test_payload_with_sql_injection_attempt(self, tmp_path: Path) -> None:
        """AC6: SQL injection in payload is safely stored and retrieved."""
        async with Spool(path=tmp_path / "spool.db") as spool:
            malicious_payload = "'; DROP TABLE spool; --"
            await spool.enqueue(malicious_payload)

            # Spool should still work.
            assert await spool.count() == 1
            rows = await spool.peek(1)
            _, returned = rows[0]
            assert returned == malicious_payload


# ---------------------------------------------------------------------------
# Concurrent read/write (AC7)
# ---------------------------------------------------------------------------


class TestConcurrency:
    """Spool handles concurrent read/write without corruption."""

    @pytest.mark.asyncio
    async def test_concurrent_enqueue_operations(self, tmp_path: Path) -> None:
        """AC7: concurrent enqueue calls do not corrupt the database."""
        async with Spool(path=tmp_path / "spool.db") as spool:
            # Launch 20 concurrent enqueue operations.
            tasks = [
                spool.enqueue(_make_payload(ts=f"2026-02-14T10:00:{i:02d}Z"))
                for i in range(20)
            ]
            await asyncio.gather(*tasks)

            assert await spool.count() == 20

    @pytest.mark.asyncio
    async def test_concurrent_enqueue_and_peek(self, tmp_path: Path) -> None:
        """AC7: concurrent enqueue and peek do not corrupt each other."""
        async with Spool(path=tmp_path / "spool.db") as spool:
            # Seed some data.
            for i in range(5):
                await spool.enqueue(_make_payload(ts=f"2026-02-14T10:00:0{i}Z"))

            # Run concurrent peeks and enqueues.
            async def do_enqueue() -> None:
                for i in range(5, 10):
                    await spool.enqueue(_make_payload(ts=f"2026-02-14T10:00:0{i}Z"))

            async def do_peek() -> list:
                return await spool.peek(20)

            await asyncio.gather(do_enqueue(), do_peek())
            # All 5 seeded + 5 enqueued = 10, no deletes occurred.
            final_count = await spool.count()
            assert final_count == 10


# ---------------------------------------------------------------------------
# Persistence across restarts
# ---------------------------------------------------------------------------


class TestPersistence:
    """Spool DB file persists data across process restarts (re-instantiation)."""

    @pytest.mark.asyncio
    async def test_data_persists_after_close_and_reopen(self, tmp_path: Path) -> None:
        """Samples survive closing and reopening the spool."""
        db_path = tmp_path / "persist.db"

        # First "process".
        async with Spool(path=db_path) as spool1:
            await spool1.enqueue(
                _make_payload(device_id="persist-test", ts="2026-02-14T10:00:00Z")
            )
            await spool1.enqueue(
                _make_payload(device_id="persist-test", ts="2026-02-14T10:00:01Z")
            )

        # Second "process" -- simulates restart.
        async with Spool(path=db_path) as spool2:
            assert await spool2.count() == 2

            rows = await spool2.peek(10)
            assert len(rows) == 2
            first = json.loads(rows[0][1])
            second = json.loads(rows[1][1])
            assert first["device_id"] == "persist-test"
            assert first["ts"] == "2026-02-14T10:00:00Z"
            assert second["ts"] == "2026-02-14T10:00:01Z"

    @pytest.mark.asyncio
    async def test_ack_persists_after_close_and_reopen(self, tmp_path: Path) -> None:
        """Acknowledged (deleted) rows stay deleted after restart."""
        db_path = tmp_path / "ack_persist.db"

        # First process: enqueue 3, ack 1.
        async with Spool(path=db_path) as spool1:
            for i in range(3):
                await spool1.enqueue(_make_payload(ts=f"2026-02-14T10:00:0{i}Z"))
            rows = await spool1.peek(1)
            await spool1.ack([rows[0][0]])

        # Second process: only 2 should remain.
        async with Spool(path=db_path) as spool2:
            assert await spool2.count() == 2
            remaining = await spool2.peek(10)
            first = json.loads(remaining[0][1])
            assert first["ts"] == "2026-02-14T10:00:01Z"


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


class TestSchema:
    """Table schema matches specification."""

    @pytest.mark.asyncio
    async def test_table_has_expected_columns(self, tmp_path: Path) -> None:
        """Spool table has payload and created_at columns with correct types."""
        import aiosqlite

        db_path = tmp_path / "schema_test.db"
        async with Spool(path=db_path):
            pass

        async with aiosqlite.connect(str(db_path)) as conn:
            cursor = await conn.execute("PRAGMA table_info(spool);")
            columns = {row[1]: row[2] for row in await cursor.fetchall()}

        assert "payload" in columns
        assert "created_at" in columns
        assert columns["payload"] == "TEXT"
        assert columns["created_at"] == "TEXT"

    @pytest.mark.asyncio
    async def test_rowid_is_autoincrement(self, tmp_path: Path) -> None:
        """rowid uses AUTOINCREMENT (never reused after deletion)."""
        async with Spool(path=tmp_path / "autoincrement.db") as spool:
            await spool.enqueue(_make_payload(ts="2026-02-14T10:00:00Z"))
            await spool.enqueue(_make_payload(ts="2026-02-14T10:00:01Z"))
            rows = await spool.peek(2)
            first_rowid = rows[0][0]
            second_rowid = rows[1][0]

            # Delete the first row.
            await spool.ack([first_rowid])

            # Insert a new row -- its rowid should be higher than the second.
            await spool.enqueue(_make_payload(ts="2026-02-14T10:00:02Z"))
            all_rows = await spool.peek(10)
            new_rowid = all_rows[-1][0]

            assert new_rowid > second_rowid

    @pytest.mark.asyncio
    async def test_created_at_is_auto_populated(self, tmp_path: Path) -> None:
        """created_at column is automatically populated."""
        import aiosqlite

        db_path = tmp_path / "created_at.db"
        async with Spool(path=db_path) as spool:
            await spool.enqueue(_make_payload())

        async with aiosqlite.connect(str(db_path)) as conn:
            cursor = await conn.execute("SELECT created_at FROM spool LIMIT 1;")
            row = await cursor.fetchone()

        assert row is not None
        assert isinstance(row[0], str)
        assert len(row[0]) > 0
