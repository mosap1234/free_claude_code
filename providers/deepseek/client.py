"""DeepSeek provider implementation (native Anthropic-compatible Messages)."""

from typing import Any

import httpx

from providers.anthropic_messages import AnthropicMessagesTransport
from providers.base import ProviderConfig
from providers.defaults import DEEPSEEK_ANTHROPIC_DEFAULT_BASE
from providers.native_messages_support import oauth_bearer_model_list_headers

from .request import build_request_body


class DeepSeekProvider(AnthropicMessagesTransport):
    """DeepSeek using ``https://api.deepseek.com/anthropic`` (Anthropic Messages API)."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="DEEPSEEK",
            default_base_url=DEEPSEEK_ANTHROPIC_DEFAULT_BASE,
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        return build_request_body(
            request,
            thinking_enabled=self._is_thinking_enabled(request, thinking_enabled),
        )

    async def _send_model_list_request(self) -> httpx.Response:
        """DeepSeek lists models from the OpenAI-format root, not /anthropic."""
        url = str(
            httpx.URL(self._base_url).copy_with(
                path="/models", query=None, fragment=None
            )
        )
        return await self._client.get(url, headers=self._model_list_headers())

    def _model_list_headers(self) -> dict[str, str]:
        return oauth_bearer_model_list_headers(self._api_key)
