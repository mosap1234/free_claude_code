"""Astraflow provider implementation."""

from __future__ import annotations

from typing import Any

from providers.base import ProviderConfig
from providers.defaults import ASTRAFLOW_DEFAULT_BASE, ASTRAFLOW_CN_DEFAULT_BASE
from providers.openai_compat import OpenAIChatTransport

from .request import build_request_body


class AstraflowProvider(OpenAIChatTransport):
    """Astraflow global provider (OpenAI-compatible, endpoint: api-us-ca.umodelverse.ai)."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="ASTRAFLOW",
            base_url=config.base_url or ASTRAFLOW_DEFAULT_BASE,
            api_key=config.api_key,
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        return build_request_body(
            request,
            thinking_enabled=self._is_thinking_enabled(request, thinking_enabled),
        )


class AstraflowCNProvider(OpenAIChatTransport):
    """Astraflow China provider (OpenAI-compatible, endpoint: api.modelverse.cn)."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="ASTRAFLOW_CN",
            base_url=config.base_url or ASTRAFLOW_CN_DEFAULT_BASE,
            api_key=config.api_key,
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        return build_request_body(
            request,
            thinking_enabled=self._is_thinking_enabled(request, thinking_enabled),
        )
