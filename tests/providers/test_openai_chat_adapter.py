"""Tests for :mod:`providers.openai_chat_adapter`."""

from types import SimpleNamespace

import pytest

from config.constants import HTTP_CONNECT_TIMEOUT_DEFAULT
from config.provider_catalog import PROVIDER_CATALOG, provider_ids_for_transport
from providers.base import ProviderConfig
from providers.openai_chat_adapter import (
    CatalogOpenAIChatProvider,
    load_request_builder,
)


def test_load_request_builder_resolves_providers_kimi_request() -> None:
    builder_fn = load_request_builder("providers.kimi.request")
    dummy = SimpleNamespace(
        model="gpt-test", messages=[SimpleNamespace(role="user", content="hello")]
    )
    body = builder_fn(dummy, thinking_enabled=False)
    assert isinstance(body, dict)
    assert body.get("model") == "gpt-test"


def test_catalog_openai_descriptors_have_request_modules() -> None:
    nim_only = frozenset({"nvidia_nim"})
    for pid in sorted(provider_ids_for_transport("openai_chat") - nim_only):
        desc = PROVIDER_CATALOG[pid]
        assert desc.openai_chat_provider_label
        assert desc.openai_request_module


def test_load_request_builder_rejects_bad_module_path() -> None:
    # This module exposes no ``build_request_body``.
    with pytest.raises(AssertionError):
        load_request_builder("providers.openai_chat_adapter")


@pytest.mark.parametrize("pid", ("kimi", "fireworks", "zai", "opencode", "opencode_go"))
def test_catalog_openai_provider_labels_match_descriptor(pid: str) -> None:
    desc = PROVIDER_CATALOG[pid]
    cfg = ProviderConfig(api_key="k", http_connect_timeout=HTTP_CONNECT_TIMEOUT_DEFAULT)
    inst = CatalogOpenAIChatProvider(pid, cfg)
    assert inst._provider_name == desc.openai_chat_provider_label
