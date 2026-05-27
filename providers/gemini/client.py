"""Google AI Studio Gemini provider (OpenAI-compatible chat completions)."""

from __future__ import annotations

from typing import Any

from providers.base import ProviderConfig
from providers.defaults import GEMINI_DEFAULT_BASE
from providers.model_listing import ProviderModelInfo
from providers.openai_compat import OpenAIChatTransport

from .request import build_request_body


class GeminiProvider(OpenAIChatTransport):
    """Gemini API using ``https://generativelanguage.googleapis.com/v1beta/openai/``."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="GEMINI",
            base_url=config.base_url or GEMINI_DEFAULT_BASE,
            api_key=config.api_key,
        )

    async def list_model_infos(self) -> frozenset[ProviderModelInfo]:
        """Return model infos, stripping the 'models/' prefix Gemini adds to IDs."""
        infos = await super().list_model_infos()
        return frozenset(
            ProviderModelInfo(
                model_id=info.model_id.removeprefix("models/"),
                supports_thinking=info.supports_thinking,
            )
            for info in infos
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        return build_request_body(
            request,
            thinking_enabled=self._is_thinking_enabled(request, thinking_enabled),
        )
