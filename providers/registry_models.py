"""Model-list discovery helpers for :class:`~providers.registry.ProviderRegistry`."""

import asyncio
from collections import defaultdict
from typing import Any

import httpx
from loguru import logger

from config.provider_catalog import PROVIDER_CATALOG, ProviderDescriptor
from config.settings import ConfiguredChatModelRef, Settings
from providers.exceptions import (
    AuthenticationError,
    ModelListResponseError,
    ProviderError,
    ServiceUnavailableError,
)
from providers.model_listing import ProviderModelInfo


def _string_attr(settings: Settings, attr_name: str | None, default: str = "") -> str:
    if attr_name is None:
        return default
    value = getattr(settings, attr_name, default)
    return value if isinstance(value, str) else default


def _credential_for(descriptor: ProviderDescriptor, settings: Settings) -> str:
    if descriptor.static_credential is not None:
        return descriptor.static_credential
    if descriptor.credential_attr:
        return _string_attr(settings, descriptor.credential_attr)
    return ""


def referenced_provider_ids(settings: Settings) -> frozenset[str]:
    return frozenset(ref.provider_id for ref in settings.configured_chat_model_refs())


def model_list_provider_ids_for_settings(settings: Settings) -> tuple[str, ...]:
    """Return providers worth discovering for this process configuration."""
    configured_refs = referenced_provider_ids(settings)
    provider_ids: list[str] = []
    for provider_id, descriptor in PROVIDER_CATALOG.items():
        if descriptor.static_credential is not None:
            if provider_id in configured_refs:
                provider_ids.append(provider_id)
            continue
        if (
            descriptor.credential_env is not None
            and _credential_for(descriptor, settings).strip()
        ):
            provider_ids.append(provider_id)
    return tuple(provider_ids)


def _format_model_validation_failure(ref: ConfiguredChatModelRef, problem: str) -> str:
    return (
        f"sources={','.join(ref.sources)} provider={ref.provider_id} "
        f"model={ref.model_id} problem={problem}"
    )


def _provider_query_failure_reason(exc: BaseException, settings: Settings) -> str:
    if isinstance(exc, ModelListResponseError):
        return f"malformed model-list response: {exc.message}"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"query failure: HTTP {exc.response.status_code}"
    if isinstance(exc, AuthenticationError):
        return f"query failure: {exc.message}"
    if isinstance(exc, ProviderError) and settings.log_api_error_tracebacks:
        return f"query failure: {exc.message}"
    return f"query failure: {type(exc).__name__}"


def _format_provider_query_failures(
    refs: list[ConfiguredChatModelRef],
    exc: BaseException,
    settings: Settings,
) -> list[str]:
    reason = _provider_query_failure_reason(exc, settings)
    return [_format_model_validation_failure(ref, reason) for ref in refs]


def _format_missing_model_failure(ref: ConfiguredChatModelRef) -> str:
    return _format_model_validation_failure(ref, "missing model")


def log_model_discovery_failure(
    provider_id: str, exc: BaseException, settings: Settings
) -> None:
    logger.warning(
        "Provider model discovery skipped: provider={} reason={}",
        provider_id,
        _provider_query_failure_reason(exc, settings),
    )


async def refresh_model_infos(
    registry: Any,
    settings: Settings,
    provider_ids: tuple[str, ...],
) -> None:
    tasks: dict[str, asyncio.Task[frozenset[ProviderModelInfo]]] = {}
    for provider_id in provider_ids:
        try:
            provider = registry.get(provider_id, settings)
        except Exception as exc:
            log_model_discovery_failure(provider_id, exc, settings)
            continue
        tasks[provider_id] = asyncio.create_task(provider.list_model_infos())

    if not tasks:
        return

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    for (provider_id, _task), result in zip(tasks.items(), results, strict=True):
        if isinstance(result, BaseException):
            if isinstance(result, asyncio.CancelledError):
                raise result
            log_model_discovery_failure(provider_id, result, settings)
            continue
        registry.cache_model_infos(provider_id, result)
        logger.info(
            "Provider model discovery cached: provider={} models={}",
            provider_id,
            len(result),
        )


async def validate_configured_chat_models(registry: Any, settings: Settings) -> None:
    """Fail fast unless every configured chat model exists upstream."""
    refs = settings.configured_chat_model_refs()
    refs_by_provider: dict[str, list[ConfiguredChatModelRef]] = defaultdict(list)
    for ref in refs:
        refs_by_provider[ref.provider_id].append(ref)

    failures: list[str] = []
    tasks: dict[str, asyncio.Task[frozenset[ProviderModelInfo]]] = {}
    for provider_id, provider_refs in refs_by_provider.items():
        try:
            provider = registry.get(provider_id, settings)
        except Exception as exc:
            failures.extend(
                _format_provider_query_failures(provider_refs, exc, settings)
            )
            continue
        tasks[provider_id] = asyncio.create_task(provider.list_model_infos())

    if tasks:
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for (provider_id, _task), result in zip(tasks.items(), results, strict=True):
            provider_refs = refs_by_provider[provider_id]
            if isinstance(result, BaseException):
                if isinstance(result, asyncio.CancelledError):
                    raise result
                failures.extend(
                    _format_provider_query_failures(provider_refs, result, settings)
                )
                continue
            registry.cache_model_infos(provider_id, result)
            model_ids = registry._model_ids_by_provider[provider_id]
            failures.extend(
                _format_missing_model_failure(ref)
                for ref in provider_refs
                if ref.model_id not in model_ids
            )

    if failures:
        message = "Configured model validation failed:\n" + "\n".join(
            f"- {failure}" for failure in failures
        )
        raise ServiceUnavailableError(message)

    logger.info(
        "Configured provider models validated: models={} providers={}",
        len(refs),
        len(refs_by_provider),
    )
