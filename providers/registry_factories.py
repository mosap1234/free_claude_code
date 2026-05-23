"""Catalog-driven provider factory registrations for :mod:`providers.registry`."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

from config.provider_catalog import PROVIDER_CATALOG, SUPPORTED_PROVIDER_IDS
from config.settings import Settings
from providers.base import BaseProvider, ProviderConfig

ProviderFactory = Callable[[ProviderConfig, Settings], BaseProvider]


def _create_nvidia_nim(config: ProviderConfig, settings: Settings) -> BaseProvider:
    from providers.nvidia_nim import NvidiaNimProvider

    return NvidiaNimProvider(config, nim_settings=settings.nim)


def _create_open_router(config: ProviderConfig, _settings: Settings) -> BaseProvider:
    from providers.open_router import OpenRouterProvider

    return OpenRouterProvider(config)


def _create_deepseek(config: ProviderConfig, _settings: Settings) -> BaseProvider:
    from providers.deepseek import DeepSeekProvider

    return DeepSeekProvider(config)


def _create_lmstudio(config: ProviderConfig, _settings: Settings) -> BaseProvider:
    from providers.lmstudio import LMStudioProvider

    return LMStudioProvider(config)


def _create_llamacpp(config: ProviderConfig, _settings: Settings) -> BaseProvider:
    from providers.llamacpp import LlamaCppProvider

    return LlamaCppProvider(config)


def _create_ollama(config: ProviderConfig, _settings: Settings) -> BaseProvider:
    from providers.ollama import OllamaProvider

    return OllamaProvider(config)


def _create_wafer(config: ProviderConfig, _settings: Settings) -> BaseProvider:
    from providers.wafer import WaferProvider

    return WaferProvider(config)


def _instantiate_catalog_openai_chat(
    provider_id: str, config: ProviderConfig, _settings: Settings
) -> BaseProvider:
    """Construct catalog-backed OpenAI chat providers (see ``openai_request_module``)."""
    if provider_id == "opencode_go":
        from providers.opencode import OpenCodeProvider

        return OpenCodeProvider(config, provider_name="OPENCODE_GO")
    if provider_id == "opencode":
        from providers.opencode import OpenCodeProvider

        return OpenCodeProvider(config)
    if provider_id == "kimi":
        from providers.kimi import KimiProvider

        return KimiProvider(config)
    if provider_id == "fireworks":
        from providers.fireworks import FireworksProvider

        return FireworksProvider(config)
    if provider_id == "zai":
        from providers.zai import ZaiProvider

        return ZaiProvider(config)
    from providers.openai_chat_adapter import CatalogOpenAIChatProvider

    return CatalogOpenAIChatProvider(provider_id, config)


def _create_catalog_openai_chat(
    _config: ProviderConfig, _settings: Settings
) -> BaseProvider:
    """Catalog marker; per-id factories use :func:`_instantiate_catalog_openai_chat`."""
    raise AssertionError(
        "OpenAI catalog providers must bind via functools.partial(_instantiate_catalog_openai_chat, pid)"
    )


_MOD = globals()
PROVIDER_FACTORIES: dict[str, ProviderFactory] = {}
for pid, desc in PROVIDER_CATALOG.items():
    if desc.openai_request_module is not None:
        if desc.transport_type != "openai_chat":
            raise AssertionError(
                f"provider {pid!r}: openai_request_module requires transport_type "
                f"'openai_chat', got {desc.transport_type!r}"
            )
        PROVIDER_FACTORIES[pid] = partial(_instantiate_catalog_openai_chat, pid)
        continue
    try:
        factory_fn = _MOD[desc.registry_factory]
    except KeyError as exc:
        raise AssertionError(
            f"registry_factory {desc.registry_factory!r} missing from "
            f"providers.registry_factories "
            f"for provider {pid}"
        ) from exc
    if not callable(factory_fn):
        raise AssertionError(
            f"registry_factory {desc.registry_factory!r} for {pid} is not callable"
        )
    PROVIDER_FACTORIES[pid] = factory_fn

if set(PROVIDER_FACTORIES) != set(SUPPORTED_PROVIDER_IDS):
    raise AssertionError(
        "PROVIDER_FACTORIES and SUPPORTED_PROVIDER_IDS are out of sync: "
        f"factories={set(PROVIDER_FACTORIES)!r} "
        f"ids={set(SUPPORTED_PROVIDER_IDS)!r}"
    )
