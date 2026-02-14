"""
HTTPS batch uploader for posting buffered energy samples to the VPS ingest endpoint.

Reads batches from the SQLite spool (STORY-005), POSTs them as JSON to the
VPS ``/v1/ingest`` endpoint with Bearer token authentication, and marks
acknowledged rows in the spool on success. Implements exponential backoff
on failure (1s -> 2s -> 4s -> ... -> MAX_BACKOFF_S max). Validates HTTPS at
startup and always uses TLS certificate verification (HC-003).

Operations:
- upload_batch(spool): Peek rows, POST to VPS, ack on success.
- current_backoff: Current backoff delay in seconds (read-only property).

CHANGELOG:
- 2026-02-14: Initial creation (STORY-006)

TODO:
- None
"""

from __future__ import annotations

import json
import logging

import httpx

logger = logging.getLogger(__name__)

_INITIAL_BACKOFF_S = 1.0
_DEFAULT_MAX_BACKOFF_S = 300.0


class Uploader:
    """HTTPS batch uploader for the VPS ingest endpoint.

    Reads a batch of buffered samples from a :class:`~edge.src.spool.Spool`,
    POSTs them to ``{vps_base_url}/v1/ingest`` with Bearer token
    authentication, and acknowledges the rows in the spool on a 200 response.

    On failure (non-200 status, timeout, connection error), no rows are
    acknowledged and the internal backoff delay doubles (capped at
    ``max_backoff_s``). On success the backoff resets to 1 second.

    The VPS URL must use HTTPS; ``http://`` URLs are rejected at
    construction time (AC7 / HC-003). TLS certificate verification is
    always enabled (AC8).

    Args:
        vps_base_url: Base URL of the VPS ingest service. Must start with
            ``https://``.
        vps_device_token: Per-device bearer token for VPS authentication.
        batch_size: Maximum number of samples to peek from the spool per
            upload cycle.
        max_backoff_s: Maximum backoff delay in seconds (default 300).
            Configurable via ``MAX_BACKOFF_S`` env var at a higher layer.

    Raises:
        ValueError: If *vps_base_url* does not start with ``https://``.

    Usage::

        uploader = Uploader(
            vps_base_url="https://solar.example.com",
            vps_device_token="tok-123",
            batch_size=30,
        )
        async with Spool(path="/data/spool.db") as spool:
            success = await uploader.upload_batch(spool)
    """

    def __init__(
        self,
        vps_base_url: str,
        vps_device_token: str,
        batch_size: int,
        max_backoff_s: float = _DEFAULT_MAX_BACKOFF_S,
    ) -> None:
        if not vps_base_url.lower().startswith("https://"):
            raise ValueError(
                f"VPS base URL must use HTTPS (got: '{vps_base_url}'). "
                "See HC-003: HTTPS Only."
            )
        self._vps_base_url = vps_base_url
        self._vps_device_token = vps_device_token
        self._batch_size = batch_size
        self._max_backoff_s = max_backoff_s
        self._current_backoff = _INITIAL_BACKOFF_S

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def current_backoff(self) -> float:
        """Current backoff delay in seconds.

        Starts at 1s, doubles on each consecutive failure, capped at
        ``max_backoff_s``. Resets to 1s on a successful upload.
        """
        return self._current_backoff

    async def upload_batch(self, spool: object) -> bool:
        """Peek a batch from the spool, POST to VPS, and ack on success.

        Args:
            spool: A :class:`~edge.src.spool.Spool` instance (or any object
                with async ``peek(n)`` and ``ack(rowids)`` methods).

        Returns:
            ``True`` if the batch was uploaded and acknowledged successfully.
            ``False`` if the spool was empty, the upload failed, or the
            server returned a non-200 status.
        """
        rows: list[tuple[int, str]] = await spool.peek(self._batch_size)  # type: ignore[union-attr]

        if not rows:
            logger.debug("Spool empty, skipping upload.")
            return False

        rowids = [rowid for rowid, _ in rows]
        samples = [json.loads(payload) for _, payload in rows]

        try:
            async with httpx.AsyncClient(verify=True) as client:
                response = await client.post(
                    f"{self._vps_base_url}/v1/ingest",
                    json={"samples": samples},
                    headers={"Authorization": f"Bearer {self._vps_device_token}"},
                )
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            logger.warning("Upload failed (network error): %s", exc)
            self._increase_backoff()
            return False

        if response.status_code == 200:
            await spool.ack(rowids)  # type: ignore[union-attr]
            logger.info("Uploaded %d samples, acked rowids %s.", len(samples), rowids)
            self._reset_backoff()
            return True

        logger.warning(
            "Upload failed (HTTP %d), will retry after %.1fs backoff.",
            response.status_code,
            self._current_backoff,
        )
        self._increase_backoff()
        return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _increase_backoff(self) -> None:
        """Double the backoff delay, capped at max_backoff_s."""
        self._current_backoff = min(
            self._current_backoff * 2,
            self._max_backoff_s,
        )

    def _reset_backoff(self) -> None:
        """Reset backoff to the initial value (1s)."""
        self._current_backoff = _INITIAL_BACKOFF_S
