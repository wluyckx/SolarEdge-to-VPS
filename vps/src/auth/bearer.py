"""
Bearer token authentication for the VPS API.

Parses device tokens from the DEVICE_TOKENS environment variable and validates
incoming Authorization: Bearer {token} headers. Uses constant-time comparison
via secrets.compare_digest to prevent timing attacks.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-009)

TODO:
- None
"""

import logging
import secrets

from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)


def parse_device_tokens(raw: str) -> dict[str, str]:
    """Parse the DEVICE_TOKENS environment variable into a token-to-device mapping.

    Format: "token1:device1,token2:device2"

    Entries without a colon separator are silently skipped.
    Leading/trailing whitespace is stripped from both tokens and device IDs.

    Args:
        raw: The raw comma-separated token:device_id string.

    Returns:
        dict[str, str]: Mapping of token -> device_id.
    """
    if not raw or not raw.strip():
        return {}

    token_map: dict[str, str] = {}
    for idx, entry in enumerate(raw.split(",")):
        entry = entry.strip()
        if ":" not in entry:
            logger.warning(
                "Skipping malformed DEVICE_TOKENS entry at position %d"
                " (no colon separator)",
                idx,
            )
            continue
        token, device_id = entry.split(":", maxsplit=1)
        token = token.strip()
        device_id = device_id.strip()
        if token and device_id:
            token_map[token] = device_id
    return token_map


def verify_bearer_token(
    token: str,
    token_map: dict[str, str],
) -> str | None:
    """Validate a bearer token against the token map using constant-time comparison.

    Iterates over all configured tokens using secrets.compare_digest to prevent
    timing-based side-channel attacks. Returns the associated device_id if a
    match is found, or None otherwise.

    Args:
        token: The bearer token extracted from the Authorization header.
        token_map: Mapping of valid token -> device_id.

    Returns:
        str | None: The device_id if the token is valid, None otherwise.
    """
    if not token:
        return None

    for registered_token, device_id in token_map.items():
        if secrets.compare_digest(
            token.encode("utf-8"), registered_token.encode("utf-8")
        ):
            return device_id

    return None


class BearerAuth:
    """FastAPI-compatible Bearer token authentication dependency.

    Wraps HTTPBearer for OpenAPI documentation and validates the extracted token
    against the configured token map. Designed to be used with FastAPI's
    Depends() mechanism.

    Attributes:
        token_map: Mapping of valid token -> device_id.
        scheme: FastAPI HTTPBearer security scheme.
    """

    def __init__(self, token_map: dict[str, str]) -> None:
        """Initialise BearerAuth with a token-to-device mapping.

        Args:
            token_map: Mapping of token -> device_id.
        """
        self.token_map = token_map
        self.scheme = HTTPBearer(auto_error=False)

    async def verify(
        self,
        request: Request,
    ) -> str:
        """FastAPI dependency that validates Bearer tokens and returns device_id.

        Extracts the token from the Authorization header via HTTPBearer, then
        validates it against the token map using constant-time comparison.

        Args:
            request: The incoming FastAPI request.

        Returns:
            str: The device_id associated with the valid token.

        Raises:
            HTTPException: 401 Unauthorized if the token is invalid or missing.
        """
        credentials: HTTPAuthorizationCredentials | None = await self.scheme(request)

        if credentials is None:
            raise HTTPException(
                status_code=401,
                detail="Missing authorization credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        device_id = verify_bearer_token(credentials.credentials, self.token_map)

        if device_id is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return device_id
