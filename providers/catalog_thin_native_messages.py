"""Catalog-parameterized thin native Anthropic Messages transports."""

from config.provider_catalog import PROVIDER_CATALOG
from providers.anthropic_messages import AnthropicMessagesTransport
from providers.base import ProviderConfig


class CatalogThinNativeAnthropicMessagesTransport(AnthropicMessagesTransport):
    """Native ``/messages`` adapter whose defaults come from ``PROVIDER_CATALOG``."""

    def __init__(self, catalog_provider_id: str, config: ProviderConfig) -> None:
        desc = PROVIDER_CATALOG[catalog_provider_id]
        base = desc.default_base_url
        if not base:
            msg = (
                f"provider_catalog[{catalog_provider_id!r}] missing "
                "default_base_url for thin native shell"
            )
            raise AssertionError(msg)
        super().__init__(
            config,
            provider_name=catalog_provider_id.upper(),
            default_base_url=base,
        )
