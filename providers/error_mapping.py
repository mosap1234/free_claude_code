"""Provider-specific exception mapping."""

import json

import httpx
import openai

from core.anthropic import get_user_facing_error_message
from providers.exceptions import (
    APIError,
    AuthenticationError,
    InvalidRequestError,
    OverloadedError,
    RateLimitError,
)
from providers.rate_limit import GlobalRateLimiter


def user_visible_message_for_mapped_provider_error(
    mapped: Exception,
    *,
    provider_name: str,
    read_timeout_s: float | None,
    original_exception: Exception | None = None,
) -> str:
    """Return the user-visible string after :func:`map_error` (405 + mapped types).

    When the mapped error is generic (e.g. "Invalid request sent to provider"),
    appends the original provider error details extracted from the exception.
    """
    if getattr(mapped, "status_code", None) == 405:
        return (
            f"Upstream provider {provider_name} rejected the request method "
            "or endpoint (HTTP 405)."
        )

    base = get_user_facing_error_message(mapped, read_timeout_s=read_timeout_s)

    # If the generic message is too vague, enrich it with the provider's actual error
    if original_exception is not None:
        raw = _extract_raw_error_text(original_exception)
        if raw and raw != base:
            # Truncate long provider error responses to avoid exceeding SSE limits
            if len(raw) > 300:
                raw = raw[:297] + "..."
            return f"{base} {raw}"

    return base


def map_error(
    e: Exception, *, rate_limiter: GlobalRateLimiter | None = None
) -> Exception:
    """Map OpenAI or HTTPX exception to specific ProviderError.

    Streaming transports should pass their scoped limiter (``self._global_rate_limiter``)
    so reactive 429 handling applies to the correct provider. Tests may omit
    ``rate_limiter`` to use the process-wide singleton.
    """
    message = get_user_facing_error_message(e)
    limiter = rate_limiter or GlobalRateLimiter.get_instance()

    if isinstance(e, openai.AuthenticationError):
        return AuthenticationError(message, raw_error=str(e))
    if isinstance(e, openai.RateLimitError):
        limiter.set_blocked(60)
        return RateLimitError(message, raw_error=str(e))
    if isinstance(e, openai.BadRequestError):
        return InvalidRequestError(message, raw_error=str(e))
    if isinstance(e, openai.InternalServerError):
        raw_message = str(e)
        sdk_status = getattr(e, "status_code", None)
        if "overloaded" in raw_message.lower() or "capacity" in raw_message.lower():
            return OverloadedError(message, raw_error=raw_message)
        if isinstance(sdk_status, int) and 500 <= sdk_status <= 599:
            stable = APIError("_", status_code=sdk_status)
            return APIError(
                get_user_facing_error_message(stable),
                status_code=sdk_status,
                raw_error=str(e),
            )
        return APIError(message, status_code=500, raw_error=str(e))
    if isinstance(e, openai.APIError):
        return APIError(
            message, status_code=getattr(e, "status_code", 500), raw_error=str(e)
        )

    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status in (401, 403):
            return AuthenticationError(message, raw_error=str(e))
        if status == 429:
            limiter.set_blocked(60)
            return RateLimitError(message, raw_error=str(e))
        if status == 400:
            return InvalidRequestError(message, raw_error=str(e))
        if status >= 500:
            if status in (502, 503, 504):
                return OverloadedError(message, raw_error=str(e))
            return APIError(message, status_code=status, raw_error=str(e))
        return APIError(message, status_code=status, raw_error=str(e))

    return e


def _extract_raw_error_text(e: Exception) -> str:
    """Extract the most descriptive error text from a provider exception.

    Tries ``e.body`` (OpenAI SDK body), ``e.message``, and ``str(e)`` in
    order of usefulness. Returns the first non-empty result.
    """
    if isinstance(e, openai.APIError):
        body = getattr(e, "body", None)
        if isinstance(body, dict) and "error" in body:
            err = body["error"]
            if isinstance(err, dict):
                return json.dumps(err, ensure_ascii=False)
            if isinstance(err, str):
                return err
        if isinstance(body, str) and body.strip():
            return body
        message = getattr(e, "message", None) or getattr(e, "code", None)
        if message:
            return str(message)

    raw = getattr(e, "raw_error", None) or str(e)
    if raw:
        return raw
    return get_user_facing_error_message(e)
