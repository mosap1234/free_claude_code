"""Header and HTTP helpers shared by Anthropic-compatible native messages transports."""

from __future__ import annotations

import inspect
from typing import Any

import httpx

from config.provider_catalog import NativeMessagesHeaderProfile
from providers.exceptions import ModelListResponseError

_ANTHROPIC_MESSAGES_VERSION_HEADER = "2023-06-01"


def build_native_messages_request_headers(
    profile: NativeMessagesHeaderProfile | None,
    api_key: str,
) -> dict[str, str]:
    """Build catalog-driven native ``POST .../messages`` headers."""
    effective = profile or "messages_minimal"
    if effective == "messages_minimal":
        return {"Content-Type": "application/json"}
    if effective == "anthropic_bearer_sse":
        return {
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "anthropic-version": _ANTHROPIC_MESSAGES_VERSION_HEADER,
        }
    if effective == "anthropic_x_api_key_sse":
        return {
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "x-api-key": api_key,
        }
    raise AssertionError(f"unknown native_messages_header_profile={effective!r}")


async def maybe_await_aclose(response: Any) -> None:
    """Call ``aclose`` on httpx-like responses; ignore non-async test doubles."""
    close = getattr(response, "aclose", None)
    if not callable(close):
        return
    result = close()
    if inspect.isawaitable(result):
        await result


def model_list_json(response: httpx.Response, *, provider_name: str) -> Any:
    response.raise_for_status()
    try:
        return response.json()
    except ValueError as exc:
        raise ModelListResponseError(
            f"{provider_name} model-list response is malformed: invalid JSON"
        ) from exc
