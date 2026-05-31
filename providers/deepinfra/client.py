"""DeepInfra provider (OpenAI-compatible chat completions)."""

from __future__ import annotations

from typing import Any

from providers.base import ProviderConfig
from providers.defaults import DEEPINFRA_DEFAULT_BASE
from providers.openai_compat import OpenAIChatTransport

from .request import build_request_body


class DeepInfraProvider(OpenAIChatTransport):
    """DeepInfra API at ``https://api.deepinfra.com/v1/openai/chat/completions``."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="DEEPINFRA",
            base_url=config.base_url or DEEPINFRA_DEFAULT_BASE,
            api_key=config.api_key,
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        return build_request_body(
            request,
            thinking_enabled=self._is_thinking_enabled(request, thinking_enabled),
        )
