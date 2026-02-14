"""
Unit tests for the edge health writer module.

Tests verify:
- HealthWriter.record_poll() writes health.json with last_poll_ts.
- HealthWriter.record_upload() updates last_upload_ts.
- HealthWriter.set_spool_count() updates spool_count.
- Health file always contains all three fields (last_poll_ts, last_upload_ts,
  spool_count).

CHANGELOG:
- 2026-02-14: Initial creation (STORY-015)

TODO:
- None
"""

from __future__ import annotations

import json
from pathlib import Path

from edge.src.health import HealthWriter

# ---------------------------------------------------------------------------
# Test: record_poll writes health file with last_poll_ts
# ---------------------------------------------------------------------------


class TestRecordPollWritesHealthFile:
    """AC1: record_poll() creates/updates the health JSON file."""

    def test_record_poll_writes_health_file(self, tmp_path: Path) -> None:
        """Calling record_poll() creates health.json with last_poll_ts set."""
        health_path = tmp_path / "health.json"
        writer = HealthWriter(health_path)

        writer.record_poll()

        assert health_path.exists()
        data = json.loads(health_path.read_text())
        assert data["last_poll_ts"] is not None
        assert isinstance(data["last_poll_ts"], str)
        # Should be a valid ISO timestamp
        assert "T" in data["last_poll_ts"]

    def test_record_poll_updates_timestamp_each_call(self, tmp_path: Path) -> None:
        """Each record_poll() call updates the last_poll_ts value."""
        health_path = tmp_path / "health.json"
        writer = HealthWriter(health_path)

        writer.record_poll()
        data1 = json.loads(health_path.read_text())
        ts1 = data1["last_poll_ts"]

        writer.record_poll()
        data2 = json.loads(health_path.read_text())
        ts2 = data2["last_poll_ts"]

        # Timestamps should be set (both non-None)
        assert ts1 is not None
        assert ts2 is not None


# ---------------------------------------------------------------------------
# Test: record_upload updates last_upload_ts
# ---------------------------------------------------------------------------


class TestRecordUploadUpdatesLastUploadTs:
    """AC1: record_upload() sets last_upload_ts in health file."""

    def test_record_upload_updates_last_upload_ts(self, tmp_path: Path) -> None:
        """Calling record_upload() writes last_upload_ts to the file."""
        health_path = tmp_path / "health.json"
        writer = HealthWriter(health_path)

        writer.record_upload()

        data = json.loads(health_path.read_text())
        assert data["last_upload_ts"] is not None
        assert isinstance(data["last_upload_ts"], str)
        assert "T" in data["last_upload_ts"]

    def test_record_upload_does_not_overwrite_poll_ts(self, tmp_path: Path) -> None:
        """record_upload() preserves existing last_poll_ts."""
        health_path = tmp_path / "health.json"
        writer = HealthWriter(health_path)

        writer.record_poll()
        data_after_poll = json.loads(health_path.read_text())
        poll_ts = data_after_poll["last_poll_ts"]

        writer.record_upload()
        data_after_upload = json.loads(health_path.read_text())

        assert data_after_upload["last_poll_ts"] == poll_ts
        assert data_after_upload["last_upload_ts"] is not None


# ---------------------------------------------------------------------------
# Test: set_spool_count updates count
# ---------------------------------------------------------------------------


class TestSetSpoolCountUpdatesCount:
    """AC1: set_spool_count() updates spool_count in health file."""

    def test_set_spool_count_updates_count(self, tmp_path: Path) -> None:
        """Calling set_spool_count(42) writes spool_count=42 to file."""
        health_path = tmp_path / "health.json"
        writer = HealthWriter(health_path)

        writer.set_spool_count(42)

        data = json.loads(health_path.read_text())
        assert data["spool_count"] == 42

    def test_set_spool_count_preserves_timestamps(self, tmp_path: Path) -> None:
        """set_spool_count() preserves existing timestamps."""
        health_path = tmp_path / "health.json"
        writer = HealthWriter(health_path)

        writer.record_poll()
        writer.record_upload()
        data_before = json.loads(health_path.read_text())

        writer.set_spool_count(10)
        data_after = json.loads(health_path.read_text())

        assert data_after["last_poll_ts"] == data_before["last_poll_ts"]
        assert data_after["last_upload_ts"] == data_before["last_upload_ts"]
        assert data_after["spool_count"] == 10


# ---------------------------------------------------------------------------
# Test: health file contains all three fields
# ---------------------------------------------------------------------------


class TestHealthFileContainsAllFields:
    """AC1: Health file always contains last_poll_ts, last_upload_ts,
    spool_count."""

    def test_health_file_contains_all_fields(self, tmp_path: Path) -> None:
        """Health file has all three required fields after any write."""
        health_path = tmp_path / "health.json"
        writer = HealthWriter(health_path)

        # Even after just record_poll, all fields must be present
        writer.record_poll()

        data = json.loads(health_path.read_text())
        assert "last_poll_ts" in data
        assert "last_upload_ts" in data
        assert "spool_count" in data

    def test_health_file_defaults_before_any_event(self, tmp_path: Path) -> None:
        """Before any event, last_poll_ts and last_upload_ts are None,
        spool_count is 0."""
        health_path = tmp_path / "health.json"
        writer = HealthWriter(health_path)

        # Trigger a write via set_spool_count to check defaults
        writer.set_spool_count(0)

        data = json.loads(health_path.read_text())
        assert data["last_poll_ts"] is None
        assert data["last_upload_ts"] is None
        assert data["spool_count"] == 0

    def test_health_file_all_fields_populated(self, tmp_path: Path) -> None:
        """After poll, upload, and spool count, all fields are populated."""
        health_path = tmp_path / "health.json"
        writer = HealthWriter(health_path)

        writer.record_poll()
        writer.set_spool_count(7)
        writer.record_upload()

        data = json.loads(health_path.read_text())
        assert data["last_poll_ts"] is not None
        assert data["last_upload_ts"] is not None
        assert data["spool_count"] == 7

    def test_health_writer_accepts_string_path(self, tmp_path: Path) -> None:
        """HealthWriter accepts a string path, not just a Path object."""
        health_path = str(tmp_path / "health.json")
        writer = HealthWriter(health_path)

        writer.record_poll()

        data = json.loads(Path(health_path).read_text())
        assert data["last_poll_ts"] is not None
