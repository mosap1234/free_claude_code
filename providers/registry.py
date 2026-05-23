"""Provider descriptors, factory, and runtime registry."""

import asyncio
from collections.abc import Iterable, MutableMapping
from contextlib import suppress

from loguru import logger

from config.provider_catalog import (
    PROVIDER_CATALOG,
    SUPPORTED_PROVIDER_IDS,
    ProviderDescriptor,
)
from config.settings import Settings
from providers.base import BaseProvider
from providers.exceptions import UnknownProviderTypeError
from providers.model_listing import ProviderModelInfo, model_infos_from_ids
from providers.registry_config import build_provider_config
from providers.registry_factories import PROVIDER_FACTORIES, ProviderFactory
from providers.registry_models import (
    model_list_provider_ids_for_settings,
    refresh_model_infos,
    validate_configured_chat_models,
)

# Backwards-compatible name for the catalog (single source: ``config.provider_catalog``).
PROVIDER_DESCRIPTORS: dict[str, ProviderDescriptor] = PROVIDER_CATALOG


def create_provider(provider_id: str, settings: Settings) -> BaseProvider:
    descriptor = PROVIDER_DESCRIPTORS.get(provider_id)
    if descriptor is None:
        supported = "', '".join(PROVIDER_DESCRIPTORS)
        raise UnknownProviderTypeError(
            f"Unknown provider_type: '{provider_id}'. Supported: '{supported}'"
        )

    config = build_provider_config(descriptor, settings)
    factory = PROVIDER_FACTORIES.get(provider_id)
    if factory is None:
        raise AssertionError(f"Unhandled provider descriptor: {provider_id}")
    return factory(config, settings)


class ProviderRegistry:
    """Cache and clean up provider instances by provider id."""

    def __init__(self, providers: MutableMapping[str, BaseProvider] | None = None):
        self._providers = providers if providers is not None else {}
        self._model_ids_by_provider: dict[str, frozenset[str]] = {}
        self._model_infos_by_provider: dict[str, dict[str, ProviderModelInfo]] = {}
        self._model_list_refresh_task: asyncio.Task[None] | None = None

    def is_cached(self, provider_id: str) -> bool:
        """Return whether a provider for this id is already in the cache."""
        return provider_id in self._providers

    def get(self, provider_id: str, settings: Settings) -> BaseProvider:
        if provider_id not in self._providers:
            self._providers[provider_id] = create_provider(provider_id, settings)
        return self._providers[provider_id]

    def cache_model_ids(self, provider_id: str, model_ids: Iterable[str]) -> None:
        """Store a provider model-list result for later instant API responses."""
        self.cache_model_infos(provider_id, model_infos_from_ids(model_ids))

    def cache_model_infos(
        self, provider_id: str, model_infos: Iterable[ProviderModelInfo]
    ) -> None:
        """Store provider model metadata for later instant API responses."""
        clean_infos = {
            info.model_id: info for info in model_infos if info.model_id.strip()
        }
        self._model_infos_by_provider[provider_id] = clean_infos
        self._model_ids_by_provider[provider_id] = frozenset(clean_infos)

    def cached_model_ids(self) -> dict[str, frozenset[str]]:
        """Return a copy of cached raw provider model ids."""
        return dict(self._model_ids_by_provider)

    def cached_model_supports_thinking(
        self, provider_id: str, model_id: str
    ) -> bool | None:
        """Return cached thinking support when a provider exposes it."""
        info = self._model_infos_by_provider.get(provider_id, {}).get(model_id)
        if info is None:
            return None
        return info.supports_thinking

    def cached_prefixed_model_refs(self) -> tuple[str, ...]:
        """Return cached provider models in user-selectable ``provider/model`` form."""
        return tuple(info.model_id for info in self.cached_prefixed_model_infos())

    def cached_prefixed_model_infos(self) -> tuple[ProviderModelInfo, ...]:
        """Return cached provider models with user-selectable prefixed ids."""
        infos: list[ProviderModelInfo] = []
        for provider_id in SUPPORTED_PROVIDER_IDS:
            provider_infos = self._model_infos_by_provider.get(provider_id, {})
            infos.extend(
                ProviderModelInfo(
                    model_id=f"{provider_id}/{info.model_id}",
                    supports_thinking=info.supports_thinking,
                )
                for info in sorted(
                    provider_infos.values(), key=lambda item: item.model_id
                )
            )
        return tuple(infos)

    async def refresh_model_list_cache(
        self, settings: Settings, *, only_missing: bool = False
    ) -> None:
        """Best-effort refresh of model lists for providers usable in this process."""
        provider_ids = model_list_provider_ids_for_settings(settings)
        if only_missing:
            provider_ids = tuple(
                provider_id
                for provider_id in provider_ids
                if provider_id not in self._model_ids_by_provider
            )
        await refresh_model_infos(self, settings, provider_ids)

    def start_model_list_refresh(self, settings: Settings) -> None:
        """Start a non-blocking cache warmup for missing eligible provider lists."""
        if (
            self._model_list_refresh_task is not None
            and not self._model_list_refresh_task.done()
        ):
            return

        provider_ids = tuple(
            provider_id
            for provider_id in model_list_provider_ids_for_settings(settings)
            if provider_id not in self._model_ids_by_provider
        )
        if not provider_ids:
            logger.info(
                "Provider model discovery cache already warm: providers={}",
                len(self._model_ids_by_provider),
            )
            return

        self._model_list_refresh_task = asyncio.create_task(
            self._run_model_list_refresh(settings, provider_ids)
        )

    async def _run_model_list_refresh(
        self, settings: Settings, provider_ids: tuple[str, ...]
    ) -> None:
        try:
            await refresh_model_infos(self, settings, provider_ids)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "Provider model discovery task failed: exc_type={}",
                type(exc).__name__,
            )

    async def validate_configured_models(self, settings: Settings) -> None:
        """Fail fast unless every configured chat model exists upstream."""
        await validate_configured_chat_models(self, settings)

    async def cleanup(self) -> None:
        """Call ``cleanup`` on every cached provider, then clear the cache.

        Attempts all providers even if one fails. A single failure is re-raised
        as-is; multiple failures are wrapped in :exc:`ExceptionGroup`.
        """
        if (
            self._model_list_refresh_task is not None
            and not self._model_list_refresh_task.done()
        ):
            self._model_list_refresh_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._model_list_refresh_task

        items = list(self._providers.items())
        errors: list[Exception] = []
        try:
            for _pid, provider in items:
                try:
                    await provider.cleanup()
                except Exception as e:
                    errors.append(e)
        finally:
            self._providers.clear()
            self._model_ids_by_provider.clear()
            self._model_infos_by_provider.clear()
        if len(errors) == 1:
            raise errors[0]
        if len(errors) > 1:
            msg = "One or more provider cleanups failed"
            raise ExceptionGroup(msg, errors)


__all__ = (
    "PROVIDER_DESCRIPTORS",
    "PROVIDER_FACTORIES",
    "ProviderFactory",
    "ProviderRegistry",
    "build_provider_config",
    "create_provider",
)
