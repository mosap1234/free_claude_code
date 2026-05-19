"""Baseten provider implementation."""

from typing import Any

from providers.base import ProviderConfig
from providers.openai_compat import OpenAIChatTransport

from .request import build_request_body

BASETEN_BASE_URL = "https://inference.baseten.co/v1"


class BasetenProvider(OpenAIChatTransport):
    """Baseten provider using OpenAI-compatible chat completions."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="BASETEN",
            base_url=config.base_url or BASETEN_BASE_URL,
            api_key=config.api_key,
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        """Build request body for Baseten."""
        if thinking_enabled is None:
            thinking_enabled = self._is_thinking_enabled(request)
        return build_request_body(
            request,
            thinking_enabled=thinking_enabled,
        )
