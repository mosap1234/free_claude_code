"""Llama.cpp provider implementation."""

from providers.base import ProviderConfig
from providers.catalog_thin_native_messages import (
    CatalogThinNativeAnthropicMessagesTransport,
)


class LlamaCppProvider(CatalogThinNativeAnthropicMessagesTransport):
    """Llama.cpp provider using native Anthropic Messages endpoint."""

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__("llamacpp", config)
