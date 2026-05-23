"""HTTP exceptions for provider resolution and gateway auth.

These subclass :class:`fastapi.HTTPException` so responses keep the familiar
``{"detail": ...}`` shape while :mod:`api.dependencies` stays free of ad-hoc
status codes and literal messages.
"""

from __future__ import annotations

from fastapi import HTTPException


class ResolverProviderAuthUnavailable(HTTPException):
    """Provider credentials missing or unusable while resolving through the registry."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=503, detail=detail)


class GatewayMissingApiKey(HTTPException):
    """Proxy ``ANTHROPIC_AUTH_TOKEN`` is set but the client sent no key."""

    def __init__(self) -> None:
        super().__init__(status_code=401, detail="Missing API key")


class GatewayInvalidApiKey(HTTPException):
    """Client key does not match configured ``ANTHROPIC_AUTH_TOKEN``."""

    def __init__(self) -> None:
        super().__init__(status_code=401, detail="Invalid API key")
