"""Request builder for Telepub Voyage (OpenAI-compatible chat completions)."""

from typing import Any

from loguru import logger

from core.anthropic import ReasoningReplayMode, build_base_request_body
from core.anthropic.conversion import OpenAIConversionError
from providers.exceptions import InvalidRequestError


def _strip_system_messages(body: dict[str, Any]) -> None:
    """Telepub Voyage rejects ``role='system'``; merge system content into user messages."""
    messages = body.get("messages")
    if not isinstance(messages, list):
        return

    system_parts: list[str] = []
    filtered: list[dict[str, Any]] = []

    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "system":
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                system_parts.append(content.strip())
        else:
            filtered.append(msg)

    if not system_parts:
        body["messages"] = filtered
        return

    system_text = "\n\n".join(system_parts)

    # Prepend system text to the first user message
    for msg in filtered:
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, str):
                msg["content"] = f"{system_text}\n\n{content}"
            elif isinstance(content, list):
                # Multimodal content: prepend a text block
                msg["content"] = [{"type": "text", "text": system_text}, *content]
            break
    else:
        # No user message found; create one
        filtered.insert(0, {"role": "user", "content": system_text})

    body["messages"] = filtered


def build_request_body(request_data: Any, *, thinking_enabled: bool) -> dict:
    """Build OpenAI-format request body from an Anthropic Messages request."""
    logger.debug(
        "TELEPUB_VOYAGE_REQUEST: conversion start model={} msgs={}",
        getattr(request_data, "model", "?"),
        len(getattr(request_data, "messages", [])),
    )
    try:
        body = build_base_request_body(
            request_data,
            reasoning_replay=ReasoningReplayMode.REASONING_CONTENT,
        )
    except OpenAIConversionError as exc:
        raise InvalidRequestError(str(exc)) from exc

    _strip_system_messages(body)

    logger.debug(
        "TELEPUB_VOYAGE_REQUEST: conversion done model={} msgs={} tools={}",
        body.get("model"),
        len(body.get("messages", [])),
        len(body.get("tools", [])),
    )
    return body
