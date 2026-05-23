"""OpenAI-chat transports constructed from :class:`ProviderDescriptor` metadata."""

import importlib
from collections.abc import Callable
from typing import Any

from config.provider_catalog import PROVIDER_CATALOG
from providers.base import ProviderConfig
from providers.openai_compat import OpenAIChatTransport


def load_request_builder(module_path: str) -> Callable[..., dict[str, Any]]:
    """Import ``build_request_body`` from ``module_path`` (dotted Python module).

    Raises:
        AssertionError: when ``build_request_body`` export is missing.
    """
    module = importlib.import_module(module_path)
    fn = getattr(module, "build_request_body", None)
    if not callable(fn):
        raise AssertionError(
            f"{module_path!r} must expose a callable build_request_body (got {fn!r})"
        )
    return fn


class CatalogOpenAIChatProvider(OpenAIChatTransport):
    """Thin OpenAI-compat adapter parameterized by catalog id + request builder module."""

    def __init__(self, provider_id: str, config: ProviderConfig) -> None:
        descriptor = PROVIDER_CATALOG[provider_id]
        label = descriptor.openai_chat_provider_label
        mod_path = descriptor.openai_request_module
        if label is None or mod_path is None:
            raise AssertionError(
                f"provider_id={provider_id!r} missing openai_chat fields in catalog "
                f"(label={label!r}, module={mod_path!r})"
            )
        if descriptor.transport_type != "openai_chat":
            raise AssertionError(
                "CatalogOpenAIChatProvider expects openai_chat transport, got "
                f"{descriptor.transport_type!r} ({provider_id!r})"
            )
        builder_fn = load_request_builder(mod_path)
        default_base = descriptor.default_base_url or ""
        super().__init__(
            config,
            provider_name=label,
            base_url=config.base_url or default_base,
            api_key=config.api_key,
        )
        self._catalog_request_builder = builder_fn

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict[str, Any]:
        return self._catalog_request_builder(
            request,
            thinking_enabled=self._is_thinking_enabled(request, thinking_enabled),
        )
