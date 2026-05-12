"""Generic OpenAI-compatible chat-completions provider.

Use this for any local or hosted server that exposes the OpenAI
``/v1/chat/completions`` API (vLLM, SGLang, TGI, LiteLLM, LocalAI, etc.).
Configure via ``OPENAI_COMPAT_BASE_URL`` and ``OPENAI_COMPAT_API_KEY``.
"""

from __future__ import annotations

from typing import Any

from core.anthropic import build_base_request_body
from core.anthropic.conversion import OpenAIConversionError
from providers.base import ProviderConfig
from providers.exceptions import InvalidRequestError
from providers.openai_compat import OpenAIChatTransport

OPENAI_COMPAT_DEFAULT_BASE = "http://localhost:8000/v1"


class OpenAICompatProvider(OpenAIChatTransport):
    """Generic OpenAI chat-completions adapter with a user-supplied base URL."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="OPENAI_COMPAT",
            base_url=config.base_url or OPENAI_COMPAT_DEFAULT_BASE,
            api_key=config.api_key,
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        try:
            return build_base_request_body(request)
        except OpenAIConversionError as exc:
            raise InvalidRequestError(str(exc)) from exc
