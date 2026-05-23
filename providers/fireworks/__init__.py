"""Fireworks AI provider exports."""

from config.provider_catalog import FIREWORKS_DEFAULT_BASE
from providers.base import ProviderConfig
from providers.openai_chat_adapter import CatalogOpenAIChatProvider

FIREWORKS_BASE_URL = FIREWORKS_DEFAULT_BASE

__all__ = ["FIREWORKS_BASE_URL", "FireworksProvider"]


class FireworksProvider(CatalogOpenAIChatProvider):
    """Fireworks AI provider using OpenAI-compatible chat completions."""

    def __init__(self, config: ProviderConfig):
        super().__init__("fireworks", config)
