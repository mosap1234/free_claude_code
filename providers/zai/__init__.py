"""Z.ai provider exports."""

from providers.base import ProviderConfig
from providers.defaults import ZAI_DEFAULT_BASE
from providers.openai_chat_adapter import CatalogOpenAIChatProvider

__all__ = [
    "ZAI_DEFAULT_BASE",
    "ZaiProvider",
]


class ZaiProvider(CatalogOpenAIChatProvider):
    """Z.ai using OpenAI-compatible Coding Plan API."""

    def __init__(self, config: ProviderConfig):
        super().__init__("zai", config)
