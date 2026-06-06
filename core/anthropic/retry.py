"""Retry utilities for HTTP requests to upstream providers."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Callable
from typing import Any

import httpx
import openai
from loguru import logger

DEFAULT_MAX_RETRIES = 4
DEFAULT_BACKOFF_MULTIPLIER = 2.0
DEFAULT_MIN_DELAY_SECONDS = 1.0
DEFAULT_MAX_DELAY_SECONDS = 30.0

_RETRYABLE_BASE_EXCEPTIONS = (
    TimeoutError,
    httpx.TimeoutException,
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
    httpx.ConnectError,
    json.JSONDecodeError,
)

RETRYABLE_EXCEPTIONS = (
    *_RETRYABLE_BASE_EXCEPTIONS,
    openai.InternalServerError,
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.RateLimitError,
)


async def execute_with_retry(
    func: Callable[..., Any],
    *args: Any,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
    min_delay_seconds: float = DEFAULT_MIN_DELAY_SECONDS,
    max_delay_seconds: float = DEFAULT_MAX_DELAY_SECONDS,
    retryable_exceptions: tuple = RETRYABLE_EXCEPTIONS,
    on_retry: Callable[[int, Exception], Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Execute an async function with retry logic for transient errors.

    Args:
        max_retries: Maximum number of retry attempts after the first failure.
                    Total attempts = 1 + max_retries.
    """
    total_attempts = 1 + max_retries
    last_error: BaseException | None = None
    delay = min_delay_seconds

    for attempt in range(total_attempts):
        try:
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        except retryable_exceptions as e:
            last_error = e

            attempt_no = attempt + 1
            if attempt >= max_retries:
                logger.warning(
                    "Request failed after {} attempts (retries exhausted): exc_type={} message={}",
                    total_attempts,
                    type(e).__name__,
                    str(e)[:200],
                )
                raise

            logger.warning(
                "Request failed (attempt {}/{}): exc_type={} message={:.200}. Retrying in {:.1f}s",
                attempt_no,
                total_attempts,
                type(e).__name__,
                str(e),
                delay,
            )

            if on_retry:
                on_retry(attempt_no, e)

            await asyncio.sleep(delay)
            delay = min(delay * backoff_multiplier, max_delay_seconds)

    if last_error:
        raise last_error
    raise RuntimeError("Retry logic error: no exception raised")
