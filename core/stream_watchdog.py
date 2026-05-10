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

# Tier-aware silence timeouts. Big models genuinely think for longer
# without emitting tokens, so they get more rope before the watchdog
# trips. Tiers are matched against the model id via substring patterns
# (largest first). Frontier models (Claude/GPT-5/etc.) bypass entirely.
_TIER_SILENCE_TIMEOUTS_S = {
    "xxl": 180.0,    # mistral-large-3-675b, future Qwen3-Max
    "xl": 150.0,     # qwen3-coder-480b, llama-3.1-405b, ring-1t
    "large": 120.0,  # nemotron-ultra-253b, deepseek-v4-pro
    "medium": 90.0,  # nemotron-super-120b, gpt-oss-120b
    "small": 60.0,   # qwen3-next-80b, llama-70b
    "tiny": 45.0,    # nemotron-nano-30b, gpt-oss-20b
}

# Same patterns/order as agent_governor.tiers.TIER_PATTERNS — kept here
# duplicated to keep core/ free of api/ imports per the boundary check.
_TIER_PATTERNS = (
    ("xxl", ("675b", "qwen3-max", "mistral-large-3", "deepseek-r2")),
    ("xl", ("480b", "405b", "qwen3-coder-480b", "llama-3.1-405b",
            "hermes-3-llama-3.1-405b", "ring-2.6-1t")),
    ("large", ("253b", "235b", "236b", "230b", "200b", "ultra-253b",
               "deepseek-v4-pro", "deepseek-v4-flash", "mistral-large-2")),
    ("medium", ("100b", "120b", "150b", "180b",
                "nemotron-super-120b", "gpt-oss-120b",
                "glm-4.6", "glm-4.5", "minimax-m2.5",
                "kimi-k2", "kimi-k2-instruct", "mistral-nemotron")),
    ("small", ("32b", "40b", "49b", "60b", "65b", "70b", "72b", "78b", "80b",
               "qwen3-next-80b", "qwen3-coder-30b", "nemotron-3-super",
               "llama-3.3-70b", "llama-3.1-70b",
               "command-r-plus", "deepseek-coder-v2")),
    ("tiny", ("1b", "2b", "3b", "4b", "5b", "6b", "7b", "8b", "9b",
              "12b", "13b", "14b", "16b", "20b", "22b", "24b", "26b", "28b", "30b",
              "nano-30b", "nano-9b", "nano-12b", "lfm-2.5",
              "gemma-4-31b", "gemma-4-26b", "gpt-oss-20b")),
)


def _tier_for_model(model_id: str) -> str | None:
    lowered = model_id.lower()
    for tier, patterns in _TIER_PATTERNS:
        for pat in patterns:
            if pat in lowered:
                return tier
    return None


def silence_timeout_s(model_id: str | None = None) -> float:
    """Read the configured silence timeout from env, with a safe default.

    If ``model_id`` is supplied, the timeout is tier-aware: bigger models
    get longer headroom before the watchdog trips. Explicit env override
    via ``NIM_STREAM_SILENCE_TIMEOUT_S`` always wins.
    """
    raw = os.environ.get(_SILENCE_TIMEOUT_ENV, "").strip()
    if raw:
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
        return 0.0 if value <= 0 else value

    if model_id:
        tier = _tier_for_model(model_id)
        if tier is not None:
            return _TIER_SILENCE_TIMEOUTS_S[tier]

    return _DEFAULT_SILENCE_TIMEOUT_S


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
