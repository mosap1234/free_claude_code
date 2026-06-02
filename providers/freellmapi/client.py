"""FreeLLMAPI provider implementation (OpenAI-compatible chat completions)."""

from __future__ import annotations

from typing import Any

from providers.base import ProviderConfig
from providers.defaults import FREELLMAPI_DEFAULT_BASE
from providers.openai_compat import OpenAIChatTransport

from .request import build_request_body


class FreeLLMAPIProvider(OpenAIChatTransport):
    """FreeLLMAPI router using ``/v1/chat/completions`` and ``/v1/models``."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="FREELLMAPI",
            base_url=config.base_url or FREELLMAPI_DEFAULT_BASE,
            api_key=config.api_key,
        )

    async def list_model_ids(self) -> frozenset[str]:
        """Return advertised models and always allow FreeLLMAPI router auto mode."""
        return (await super().list_model_ids()) | frozenset({"auto"})

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        return build_request_body(
            request,
            thinking_enabled=self._is_thinking_enabled(request, thinking_enabled),
        )
