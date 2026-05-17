"""Llama.cpp provider implementation."""

from providers.anthropic_messages import AnthropicMessagesTransport
from providers.base import ProviderConfig
from providers.defaults import LLAMACPP_DEFAULT_BASE


class LlamaCppProvider(AnthropicMessagesTransport):
    """Llama.cpp provider using native Anthropic Messages endpoint."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="LLAMACPP",
            default_base_url=LLAMACPP_DEFAULT_BASE,
        )
        self._api_key = config.api_key or "llamacpp"

    def _request_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key and self._api_key != "llamacpp":
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _model_list_headers(self) -> dict[str, str]:
        if self._api_key and self._api_key != "llamacpp":
            return {"Authorization": f"Bearer {self._api_key}"}
        return {}
