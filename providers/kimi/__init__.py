"""Kimi (Moonshot) provider exports."""

from providers.base import ProviderConfig
from providers.defaults import KIMI_DEFAULT_BASE
from providers.openai_chat_adapter import CatalogOpenAIChatProvider

__all__ = [
    "KIMI_DEFAULT_BASE",
    "KimiProvider",
]


class KimiProvider(CatalogOpenAIChatProvider):
    """Kimi provider using the OpenAI-compatible chat completions API."""

    def __init__(self, config: ProviderConfig):
        super().__init__("kimi", config)
