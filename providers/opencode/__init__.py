"""OpenCode Zen provider exports."""

from providers.base import ProviderConfig
from providers.defaults import OPENCODE_DEFAULT_BASE, OPENCODE_GO_DEFAULT_BASE
from providers.openai_chat_adapter import CatalogOpenAIChatProvider

__all__ = [
    "OPENCODE_DEFAULT_BASE",
    "OPENCODE_GO_DEFAULT_BASE",
    "OpenCodeProvider",
]


class OpenCodeProvider(CatalogOpenAIChatProvider):
    """OpenCode Zen / Go gateways share one request builder keyed by catalog id."""

    def __init__(self, config: ProviderConfig, provider_name: str = "OPENCODE"):
        pid = "opencode_go" if provider_name.upper() == "OPENCODE_GO" else "opencode"
        super().__init__(pid, config)
