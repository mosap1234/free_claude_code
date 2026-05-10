"""Classification of transient (retryable) provider errors.

Centralises every "this is worth retrying" decision so the retry loop has
one source of truth. Used by :class:`providers.rate_limit.GlobalRateLimiter`
when deciding whether an exception should be retried with backoff.

Two flavours of "transient":

* **Pre-stream** errors (failure before any byte streamed back to client):
  always safe to retry. The client never saw a partial response.
* **Mid-stream** errors (failure after first token): NOT safe to retry —
  retrying would duplicate already-emitted tokens. Caller must decide.

The functions in this module are pure classification — they do not retry,
they only tell the caller "this is/isn't transient".
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx
import openai


# NIM uses Cloudflare in front of the inference layer, so we treat 5xx
# from Cloudflare (520, 522, 524) the same as 502/503/504 — a transient
# upstream error worth retrying. 429 is included so callers that raise
# httpx.HTTPStatusError(429) (rather than openai.RateLimitError) still
# retry; the rate limiter applies its global block as a side effect.
_DEFAULT_RETRYABLE_STATUS_CODES = (408, 429, 502, 503, 504, 520, 522, 524)


def _retryable_status_codes() -> tuple[int, ...]:
    """Read the retryable-status-codes list from env; fall back to defaults."""
    raw = os.environ.get("NIM_RETRY_ON_5XX", "").strip()
    if not raw:
        return _DEFAULT_RETRYABLE_STATUS_CODES
    out: list[int] = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            out.append(int(piece))
        except ValueError:
            continue
    return tuple(out) if out else _DEFAULT_RETRYABLE_STATUS_CODES


# 404s with a body matching this pattern are NIM serverless cold-start
# failures, where the function id has been unloaded and a new one needs
# to be allocated. Retryable after a short pause.
NIM_FUNCTION_NOT_FOUND_MARKERS = (
    '"detail":"Function',
    '"title":"Not Found"',
    "Not found for account",
)


@dataclass(frozen=True, slots=True)
class TransientErrorClassification:
    """Outcome of classifying an exception."""

    is_transient: bool
    cause: str  # short human-readable cause, used in logs


def classify(exc: BaseException) -> TransientErrorClassification:
    """Return whether this exception is retryable, and a short cause label."""
    # OpenAI-SDK transport errors. APITimeoutError is a subclass of
    # APIConnectionError so it must be checked first.
    if isinstance(exc, openai.APITimeoutError):
        return TransientErrorClassification(True, "openai_timeout")
    if isinstance(exc, openai.APIConnectionError):
        return TransientErrorClassification(True, "openai_connect")
    if isinstance(exc, openai.InternalServerError):
        # OpenAI SDK wraps generic 5xx as InternalServerError. Treat as
        # transient — caller already handles the more-specific subclasses
        # (RateLimitError, APIConnectionError) above.
        return TransientErrorClassification(True, "openai_internal_server")

    # Direct httpx exceptions raised by streaming reads
    if isinstance(exc, httpx.ConnectError):
        return TransientErrorClassification(True, "httpx_connect")
    if isinstance(exc, httpx.ConnectTimeout):
        return TransientErrorClassification(True, "httpx_connect_timeout")
    if isinstance(exc, httpx.ReadTimeout):
        return TransientErrorClassification(True, "httpx_read_timeout")
    if isinstance(exc, httpx.WriteError):
        return TransientErrorClassification(True, "httpx_write_error")
    if isinstance(exc, httpx.RemoteProtocolError):
        return TransientErrorClassification(True, "httpx_remote_protocol")
    if isinstance(exc, httpx.PoolTimeout):
        return TransientErrorClassification(True, "httpx_pool_timeout")

    # HTTP status errors — transient only for specific status codes
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        retryable = _retryable_status_codes()
        if status in retryable:
            return TransientErrorClassification(True, f"http_{status}")
        if status == 404 and _is_nim_function_cold_start(exc):
            return TransientErrorClassification(True, "nim_cold_start")
        return TransientErrorClassification(False, f"http_{status}")

    return TransientErrorClassification(False, type(exc).__name__)


def _is_nim_function_cold_start(exc: httpx.HTTPStatusError) -> bool:
    """Return True for NIM 404s that look like a serverless cold-start.

    These are RECOVERABLE — the function id reloads after a short delay.
    Any other 404 (genuinely missing model) is NOT retryable.
    """
    try:
        body = exc.response.text
    except Exception:
        return False
    return any(marker in body for marker in NIM_FUNCTION_NOT_FOUND_MARKERS)
