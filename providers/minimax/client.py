"""MiniMax provider implementation (native Anthropic-compatible Messages)."""

from __future__ import annotations

import httpx

from providers.anthropic_messages import AnthropicMessagesTransport
from providers.base import ProviderConfig
from providers.defaults import MINIMAX_DEFAULT_BASE


class MiniMaxProvider(AnthropicMessagesTransport):
    """MiniMax using ``https://api.minimax.io/anthropic`` (Anthropic Messages API).

    Auth: ``X-Api-Key: <key>`` — MiniMax explicitly rejects Authorization: Bearer
    with "login fail: Please carry the API secret key in the X-Api-Key field".
    Path requires ``/v1/`` prefix (404 without it).
    """

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="MINIMAX",
            default_base_url=MINIMAX_DEFAULT_BASE,
        )

    def _request_headers(self) -> dict[str, str]:
        return {
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "X-Api-Key": self._api_key,
        }

    async def _send_model_list_request(self) -> httpx.Response:
        """MiniMax lists models from /models on the same base."""
        url = str(
            httpx.URL(self._base_url).copy_with(
                path="/models", query=None, fragment=None
            )
        )
        return await self._client.get(url, headers=self._model_list_headers())

    def _model_list_headers(self) -> dict[str, str]:
        return {"X-Api-Key": self._api_key}
