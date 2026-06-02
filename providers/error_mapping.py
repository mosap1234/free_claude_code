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
    ProviderError,
    RateLimitError,
)
from providers.rate_limit import GlobalRateLimiter

# Attribute used to ferry the upstream provider's *error response body* from the
# transport layer (where it is read off the failed HTTP response) through
# :func:`map_error` to the user-visible formatting. Kept as a private attribute
# on the exception so it never silently disappears. The body is the provider's
# response (e.g. ``{"error":{"message":"max_tokens too large"}}``), NOT the
# client request payload, so it carries no client secrets.
PROVIDER_ERROR_BODY_ATTR = "_fcc_provider_error_body"

# Cap on how much of the upstream reason is surfaced to the client.
_PROVIDER_DETAIL_MAX_CHARS = 300


def provider_error_detail(exc: Exception) -> str | None:
    """Extract a short, human-readable reason from a captured provider error body.

    Returns ``None`` when no body was attached. DeepSeek/Anthropic-style bodies
    look like ``{"type":"error","error":{"type":"...","message":"..."}}``; we
    surface ``error.message`` when present, else the raw (capped) text.
    """
    body = getattr(exc, PROVIDER_ERROR_BODY_ATTR, None)
    if not isinstance(body, str):
        return None
    text = body.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return text[:_PROVIDER_DETAIL_MAX_CHARS]
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict) and isinstance(err.get("message"), str):
            msg = err["message"].strip()
            if msg:
                return msg[:_PROVIDER_DETAIL_MAX_CHARS]
        top = data.get("message")
        if isinstance(top, str) and top.strip():
            return top.strip()[:_PROVIDER_DETAIL_MAX_CHARS]
    return text[:_PROVIDER_DETAIL_MAX_CHARS]


def user_visible_message_for_mapped_provider_error(
    mapped: Exception,
    *,
    provider_name: str,
    read_timeout_s: float | None,
    include_provider_detail: bool = False,
) -> str:
    """Return the user-visible string after :func:`map_error` (405 + mapped types).

    When ``include_provider_detail`` is set (operator opted into verbose errors)
    the upstream reason captured via :data:`PROVIDER_ERROR_BODY_ATTR` is appended
    so opaque ``Invalid request sent to provider.`` errors become diagnosable.
    """
    if getattr(mapped, "status_code", None) == 405:
        return (
            f"Upstream provider {provider_name} rejected the request method "
            "or endpoint (HTTP 405)."
        )
    base = get_user_facing_error_message(mapped, read_timeout_s=read_timeout_s)
    if include_provider_detail:
        detail = provider_error_detail(mapped)
        if detail and detail.lower() not in base.lower():
            return f"{base} (provider: {detail})"
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

    def _carry(mapped: Exception) -> Exception:
        """Ferry the captured upstream error body onto the mapped exception."""
        body = getattr(e, PROVIDER_ERROR_BODY_ATTR, None)
        if body is not None and isinstance(mapped, ProviderError):
            setattr(mapped, PROVIDER_ERROR_BODY_ATTR, body)
        return mapped

    if isinstance(e, openai.AuthenticationError):
        return _carry(AuthenticationError(message, raw_error=str(e)))
    if isinstance(e, openai.RateLimitError):
        limiter.set_blocked(60)
        return _carry(RateLimitError(message, raw_error=str(e)))
    if isinstance(e, openai.BadRequestError):
        return _carry(InvalidRequestError(message, raw_error=str(e)))
    if isinstance(e, openai.InternalServerError):
        raw_message = str(e)
        sdk_status = getattr(e, "status_code", None)
        if "overloaded" in raw_message.lower() or "capacity" in raw_message.lower():
            return _carry(OverloadedError(message, raw_error=raw_message))
        if isinstance(sdk_status, int) and 500 <= sdk_status <= 599:
            stable = APIError("_", status_code=sdk_status)
            return _carry(
                APIError(
                    get_user_facing_error_message(stable),
                    status_code=sdk_status,
                    raw_error=str(e),
                )
            )
        return _carry(APIError(message, status_code=500, raw_error=str(e)))
    if isinstance(e, openai.APIError):
        return _carry(
            APIError(
                message, status_code=getattr(e, "status_code", 500), raw_error=str(e)
            )
        )

    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status in (401, 403):
            return _carry(AuthenticationError(message, raw_error=str(e)))
        if status == 429:
            limiter.set_blocked(60)
            return _carry(RateLimitError(message, raw_error=str(e)))
        if status == 400:
            return _carry(InvalidRequestError(message, raw_error=str(e)))
        if status >= 500:
            if status in (502, 503, 504):
                return _carry(OverloadedError(message, raw_error=str(e)))
            return _carry(APIError(message, status_code=status, raw_error=str(e)))
        return _carry(APIError(message, status_code=status, raw_error=str(e)))

    return e
