"""Generic native Anthropic Messages provider.

Points at any server that speaks Anthropic's ``POST /v1/messages`` SSE protocol
(Anthropic itself, DeepSeek's ``/anthropic`` endpoint, LM Studio's Anthropic
mode, etc). Configure with ``ANTHROPIC_UPSTREAM_BASE_URL`` and
``ANTHROPIC_UPSTREAM_API_KEY``.
"""

from __future__ import annotations

from providers.anthropic_messages import AnthropicMessagesTransport
from providers.base import ProviderConfig

ANTHROPIC_GENERIC_DEFAULT_BASE = "https://api.anthropic.com"
_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicGenericProvider(AnthropicMessagesTransport):
    """Generic native Anthropic Messages upstream with ``x-api-key`` auth."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="ANTHROPIC",
            default_base_url=ANTHROPIC_GENERIC_DEFAULT_BASE,
        )

    def _request_headers(self) -> dict[str, str]:
        return {
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
        }

    def _model_list_headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
        }
