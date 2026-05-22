"""Cloudflare provider implementation."""

from typing import TYPE_CHECKING, Any

from providers.base import ProviderConfig
from providers.openai_compat import OpenAIChatTransport

from .request import build_request_body

if TYPE_CHECKING:
    from providers.registry import Settings


class CloudflareProvider(OpenAIChatTransport):
    """Cloudflare provider using OpenAI-compatible chat completions."""

    def __init__(self, config: ProviderConfig, settings: Settings):
        # Construct the base URL with account ID
        base_url = (
            config.base_url
            or f"https://api.cloudflare.com/client/v4/accounts/{settings.cloudflare_account_id}/ai/v1"
        )
        super().__init__(
            config,
            provider_name="CLOUDFLARE",
            base_url=base_url,
            api_key=config.api_key,
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        """Build request body for Cloudflare."""
        if thinking_enabled is None:
            thinking_enabled = self._is_thinking_enabled(request)
        return build_request_body(
            request,
            thinking_enabled=thinking_enabled,
        )

    async def list_model_ids(self) -> frozenset[str]:
        """List available models from Cloudflare."""
        return frozenset(
            [
                "@cf/google/gemma-4-26b-a4b-it",
                "@cf/meta/llama-4-scout-17b-16e-instruct",
                "@cf/qwen/qwen2.5-coder-32b-instruct",
            ]
        )  # Cloudflare does not have a public model listing endpoint
