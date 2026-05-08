"""Custom OpenAI-compatible provider implementation."""

from __future__ import annotations

from typing import Any

from providers.base import ProviderConfig
from providers.exceptions import ServiceUnavailableError
from providers.openai_compat import OpenAIChatTransport

from .request import build_request_body


class CustomProvider(OpenAIChatTransport):
    """Custom provider using the OpenAI-compatible chat completions API."""

    def __init__(self, config: ProviderConfig, *, group: str):
        base_url = (config.base_url or "").strip()
        if not base_url:
            raise ServiceUnavailableError(
                "CUSTOM_PROVIDER_BASE_URL is not set. Add it to your .env file."
            )
        super().__init__(
            config,
            provider_name="CUSTOM",
            base_url=base_url,
            api_key=config.api_key,
        )
        self._group = group.strip()

    async def list_model_ids(self) -> frozenset[str]:
        model_ids = await super().list_model_ids()
        if not self._group:
            return model_ids
        prefix = f"{self._group}/"
        filtered = frozenset(
            model_id for model_id in model_ids if model_id.startswith(prefix)
        )
        return filtered or model_ids

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        return build_request_body(
            request,
            thinking_enabled=self._is_thinking_enabled(request, thinking_enabled),
        )
