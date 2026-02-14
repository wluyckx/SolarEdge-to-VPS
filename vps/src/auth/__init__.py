"""
Authentication package.

Exports the BearerAuth dependency class and token parsing utilities
for use by FastAPI route handlers.

CHANGELOG:
- 2026-02-14: Export BearerAuth, parse_device_tokens, verify_bearer_token (STORY-009)
- 2026-02-14: Initial creation (STORY-007)

TODO:
- None
"""

from src.auth.bearer import BearerAuth, parse_device_tokens, verify_bearer_token

__all__ = ["BearerAuth", "parse_device_tokens", "verify_bearer_token"]
