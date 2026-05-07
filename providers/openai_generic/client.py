"""Generic OpenAI-compatible provider.

Points at any server that speaks OpenAI's ``POST /chat/completions`` and
``GET /models`` (e.g. SiliconFlow, DashScope, OneAPI, vLLM, LocalAI, LM Studio
OpenAI endpoint, llama.cpp OpenAI endpoint). Configure with ``OPENAI_BASE_URL``
and ``OPENAI_API_KEY``.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from core.anthropic import ReasoningReplayMode, build_base_request_body
from core.anthropic.conversion import OpenAIConversionError
from providers.base import ProviderConfig
from providers.exceptions import InvalidRequestError
from providers.openai_compat import OpenAIChatTransport

OPENAI_GENERIC_DEFAULT_BASE = "https://api.openai.com/v1"


class OpenAIGenericProvider(OpenAIChatTransport):
    """Generic ``/chat/completions`` provider with Anthropic-to-OpenAI conversion."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="OPENAI",
            base_url=config.base_url or OPENAI_GENERIC_DEFAULT_BASE,
            api_key=config.api_key,
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        thinking = self._is_thinking_enabled(request, thinking_enabled)
        logger.debug(
            "OPENAI_REQUEST: conversion start model={} msgs={}",
            getattr(request, "model", "?"),
            len(getattr(request, "messages", [])),
        )
        try:
            body = build_base_request_body(
                request,
                reasoning_replay=ReasoningReplayMode.REASONING_CONTENT,
            )
        except OpenAIConversionError as exc:
            raise InvalidRequestError(str(exc)) from exc

        logger.debug(
            "OPENAI_REQUEST: conversion done model={} msgs={} tools={} thinking={}",
            body.get("model"),
            len(body.get("messages", [])),
            len(body.get("tools", [])),
            thinking,
        )
        return body
