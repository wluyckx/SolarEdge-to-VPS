"""
Durable local queue using async SQLite for buffering energy samples before upload.

This is the critical component for HC-001 (No Data Loss). Samples are written
to the spool before any upload attempt. They are only deleted after server
acknowledgment. The spool survives process restarts because it is backed by
a SQLite database file on disk in WAL mode.

Operations:
- enqueue(payload): INSERT a JSON payload row.
- peek(n): SELECT up to n oldest rows with their rowids (FIFO).
- ack(rowids): DELETE only the specified rows (confirmed by server).
- count(): SELECT COUNT(*) of pending samples.
- close(): Close the underlying database connection.

Supports async context manager protocol for clean resource management.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-005)

TODO:
- None
"""

from __future__ import annotations

from pathlib import Path

import aiosqlite

_CREATE_TABLE_SQL = """\
CREATE TABLE IF NOT EXISTS spool (
    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_INSERT_SQL = """\
INSERT INTO spool (payload) VALUES (?);
"""

_PEEK_SQL = """\
SELECT rowid, payload
FROM spool
ORDER BY rowid ASC
LIMIT ?;
"""

_COUNT_SQL = "SELECT COUNT(*) FROM spool;"


class Spool:
    """Durable local async FIFO queue backed by a SQLite database.

    Provides enqueue/peek/ack/count operations for buffering energy
    measurement samples (as JSON payloads) before uploading to the VPS
    ingest endpoint. Uses WAL journal mode for concurrent read/write
    safety and crash durability (HC-001).

    The spool stores payloads as opaque TEXT blobs. The caller is
    responsible for JSON serialization/deserialization.

    Args:
        path: Filesystem path for the SQLite database file.
              Accepts ``str`` or ``pathlib.Path``.

    Usage::

        async with Spool(path="/data/spool.db") as spool:
            await spool.enqueue('{"device_id": "x", "ts": "..."}')
            rows = await spool.peek(10)
            await spool.ack([rowid for rowid, _ in rows])
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._db: aiosqlite.Connection | None = None

    async def open(self) -> None:
        """Open the SQLite connection and initialize the schema.

        Sets WAL journal mode for concurrent read/write safety and
        crash durability. Creates the spool table if it does not exist.
        """
        self._db = await aiosqlite.connect(str(self._path))
        # Enable WAL mode for concurrent read/write (HC-001 durability).
        await self._db.execute("PRAGMA journal_mode=WAL;")
        await self._db.execute(_CREATE_TABLE_SQL)
        await self._db.commit()

    async def close(self) -> None:
        """Close the underlying SQLite connection.

        After calling close, no further operations should be performed
        on this Spool instance.
        """
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def __aenter__(self) -> Spool:
        """Enter async context manager: open the database."""
        await self.open()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit async context manager: close the database."""
        await self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def enqueue(self, payload: str) -> None:
        """Insert a JSON payload into the spool.

        The payload is stored as-is in a TEXT column. The caller is
        responsible for JSON serialization before calling this method.

        Args:
            payload: JSON string to store.
        """
        assert self._db is not None, "Spool not opened. Call open() or use async with."
        await self._db.execute(_INSERT_SQL, (payload,))
        await self._db.commit()

    async def peek(self, n: int) -> list[tuple[int, str]]:
        """Return up to *n* oldest pending payloads without removing them.

        Results are ordered by ``rowid ASC`` (FIFO). Each returned tuple
        contains ``(rowid, payload)`` so the caller can later acknowledge
        specific rows via :meth:`ack`.

        Args:
            n: Maximum number of rows to return.

        Returns:
            List of ``(rowid, payload)`` tuples. Empty list when the
            spool has no pending rows or n < 1.
        """
        assert self._db is not None, "Spool not opened. Call open() or use async with."
        if n < 1:
            return []
        cursor = await self._db.execute(_PEEK_SQL, (n,))
        rows = await cursor.fetchall()
        return [(row[0], row[1]) for row in rows]

    async def ack(self, rowids: list[int]) -> None:
        """Delete confirmed rows from the spool.

        Only rows whose ``rowid`` appears in *rowids* are removed.
        Nonexistent rowids are silently ignored. An empty list is a no-op.

        Uses parameterized placeholders to prevent SQL injection (AC6).

        Args:
            rowids: List of rowid integers to delete.
        """
        assert self._db is not None, "Spool not opened. Call open() or use async with."
        if not rowids:
            return
        # Use parameterized placeholders to prevent SQL injection (SKILL.md).
        placeholders = ",".join("?" for _ in rowids)
        sql = f"DELETE FROM spool WHERE rowid IN ({placeholders});"  # noqa: S608
        await self._db.execute(sql, rowids)
        await self._db.commit()

    async def count(self) -> int:
        """Return the number of pending (unacknowledged) payloads.

        Returns:
            Integer count of rows in the spool table.
        """
        assert self._db is not None, "Spool not opened. Call open() or use async with."
        cursor = await self._db.execute(_COUNT_SQL)
        row = await cursor.fetchone()
        return row[0]
