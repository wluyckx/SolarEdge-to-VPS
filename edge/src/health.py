"""
Health file writer for the edge daemon.

Writes a JSON health file at a configurable path with three fields:
- last_poll_ts: ISO timestamp of the most recent poll event.
- last_upload_ts: ISO timestamp of the most recent successful upload.
- spool_count: Number of pending samples in the local spool.

The file is overwritten atomically on every state change, providing a
simple liveness signal that Docker HEALTHCHECK or monitoring can inspect.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-015)

TODO:
- None
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


class HealthWriter:
    """Writes edge health status to a JSON file.

    Each mutating method updates the in-memory state and immediately
    rewrites the health file so it always reflects the latest status.

    Args:
        path: Filesystem path for the health JSON file. Accepts str or Path.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._last_poll_ts: str | None = None
        self._last_upload_ts: str | None = None
        self._spool_count: int = 0

    def record_poll(self) -> None:
        """Record a poll event and write health file."""
        self._last_poll_ts = datetime.now(tz=UTC).isoformat()
        self._write()

    def record_upload(self) -> None:
        """Record an upload event and write health file."""
        self._last_upload_ts = datetime.now(tz=UTC).isoformat()
        self._write()

    def set_spool_count(self, count: int) -> None:
        """Update the spool count and write health file.

        Args:
            count: Current number of pending samples in the spool.
        """
        self._spool_count = count
        self._write()

    def _write(self) -> None:
        """Write the health JSON file with current state."""
        data = {
            "last_poll_ts": self._last_poll_ts,
            "last_upload_ts": self._last_upload_ts,
            "spool_count": self._spool_count,
        }
        self.path.write_text(json.dumps(data))
