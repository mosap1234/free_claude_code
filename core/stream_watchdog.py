"""Async watchdog wrapper that aborts a stream after prolonged silence.

Why: NIM occasionally leaves a stream open with no bytes for very long
periods (we've observed an 8.5h hang). httpx's read_timeout would
eventually fire, but only after default ~5min, and by then the user has
been staring at a blank terminal for minutes.

This wrapper watches the inter-token interval. If no token arrives within
``silence_timeout_s`` (default 90s), it raises :class:`StreamSilentError`
with a clear cause. Callers convert that into a user-visible SSE error
event that explains what happened.

Usage::

    async for chunk in stream_with_silence_watchdog(
        upstream_iterator, silence_timeout_s=90
    ):
        ...

The wrapper is provider-agnostic — it works with any async iterator.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from typing import TypeVar

from loguru import logger


T = TypeVar("T")


_DEFAULT_SILENCE_TIMEOUT_S = 90.0
_SILENCE_TIMEOUT_ENV = "NIM_STREAM_SILENCE_TIMEOUT_S"


def silence_timeout_s() -> float:
    """Read the configured silence timeout from env, with a safe default."""
    raw = os.environ.get(_SILENCE_TIMEOUT_ENV, "").strip()
    if not raw:
        return _DEFAULT_SILENCE_TIMEOUT_S
    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "Invalid {} value: {!r} — using default {}s",
            _SILENCE_TIMEOUT_ENV,
            raw,
            _DEFAULT_SILENCE_TIMEOUT_S,
        )
        return _DEFAULT_SILENCE_TIMEOUT_S
    if value <= 0:
        return 0.0
    return value


class StreamSilentError(Exception):
    """Raised when an upstream stream produced no bytes for too long."""

    def __init__(self, silence_seconds: float, *, request_id: str | None = None):
        self.silence_seconds = silence_seconds
        self.request_id = request_id
        msg = (
            f"upstream stream silent for {silence_seconds:.1f}s "
            f"(request_id={request_id or 'n/a'})"
        )
        super().__init__(msg)


async def stream_with_silence_watchdog(
    upstream: AsyncIterator[T],
    *,
    silence_timeout: float | None = None,
    request_id: str | None = None,
) -> AsyncIterator[T]:
    """Yield from ``upstream``, raising :class:`StreamSilentError` on hangs.

    Each chunk pulled from ``upstream`` is awaited with a timeout of
    ``silence_timeout`` seconds. If the timeout elapses before the next
    chunk arrives, the watchdog raises ``StreamSilentError`` and the
    upstream iterator is closed via its async ``aclose()`` if available.

    A ``silence_timeout`` <= 0 disables the watchdog.
    """
    timeout = silence_timeout if silence_timeout is not None else silence_timeout_s()
    if timeout <= 0:
        async for chunk in upstream:
            yield chunk
        return

    iterator = upstream.__aiter__()
    silence_started = asyncio.get_event_loop().time()
    while True:
        try:
            chunk = await asyncio.wait_for(iterator.__anext__(), timeout=timeout)
        except StopAsyncIteration:
            return
        except asyncio.TimeoutError:
            elapsed = asyncio.get_event_loop().time() - silence_started
            logger.error(
                "NIM_STREAM_SILENT: request_id={} silence_seconds={:.1f} timeout={:.1f}",
                request_id or "n/a",
                elapsed,
                timeout,
            )
            await _safely_close(iterator)
            raise StreamSilentError(elapsed, request_id=request_id)
        silence_started = asyncio.get_event_loop().time()
        yield chunk


async def _safely_close(iterator: AsyncIterator[T]) -> None:
    """Best-effort close of an async iterator after a watchdog trip."""
    aclose = getattr(iterator, "aclose", None)
    if aclose is None:
        return
    try:
        await aclose()
    except Exception:
        # Don't mask the original watchdog error.
        pass
