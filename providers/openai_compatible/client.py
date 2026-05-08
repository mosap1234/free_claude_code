"""Generic OpenAI-compatible provider implementation."""

from typing import Any

from providers.base import ProviderConfig
from providers.defaults import OPENAI_COMPATIBLE_DEFAULT_BASE
from providers.openai_compat import OpenAIChatTransport

from .request import build_request_body


class OpenAICompatibleProvider(OpenAIChatTransport):
    """Provider for local vLLM/SGLang-style OpenAI-compatible chat servers."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="OPENAI_COMPATIBLE",
            base_url=config.base_url or OPENAI_COMPATIBLE_DEFAULT_BASE,
            api_key=config.api_key or "local",
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        return build_request_body(
            request,
            thinking_enabled=self._is_thinking_enabled(request, thinking_enabled),
        )
