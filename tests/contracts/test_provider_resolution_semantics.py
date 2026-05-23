"""Behavioral parity for :func:`api.dependencies.resolve_provider` code paths."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from starlette.applications import Starlette
from starlette.datastructures import State

import api.dependencies as deps
import api.provider_process_cache as ppc
from api.dependencies import resolve_provider
from api.resolver_exceptions import ResolverProviderAuthUnavailable
from config.nim import NimSettings
from providers.exceptions import UnknownProviderTypeError
from providers.registry import ProviderRegistry


def _mock_settings(**overrides):
    mock = MagicMock()
    mock.model = "nvidia_nim/meta/llama3"
    mock.provider_type = "nvidia_nim"
    mock.nvidia_nim_api_key = "test_key"
    mock.provider_rate_limit = 40
    mock.provider_rate_window = 60
    mock.provider_max_concurrency = 5
    mock.http_read_timeout = 300.0
    mock.http_write_timeout = 10.0
    mock.http_connect_timeout = 10.0
    mock.enable_model_thinking = True
    mock.nim = NimSettings()
    for key, value in overrides.items():
        setattr(mock, key, value)
    return mock


def test_unknown_provider_type_par_app_vs_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same backing cache → identical unknown-id exception."""
    shared: dict = {}
    monkeypatch.setattr(ppc, "PROCESS_PROVIDERS", shared)
    monkeypatch.setattr(deps, "_process_registry", None)
    monkeypatch.setattr(deps, "_process_providers_dict_id", None)

    settings = _mock_settings()
    starlette_app = Starlette()
    starlette_app.state = State()
    starlette_app.state.provider_registry = ProviderRegistry(shared)

    with pytest.raises(UnknownProviderTypeError):
        resolve_provider("__not_registered__", app=None, settings=settings)
    with pytest.raises(UnknownProviderTypeError):
        resolve_provider("__not_registered__", app=starlette_app, settings=settings)


def test_resolver_provider_auth_unavailable_par_app_vs_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing upstream credential surfaces the same resolver HTTP error type."""
    shared: dict = {}
    monkeypatch.setattr(ppc, "PROCESS_PROVIDERS", shared)
    monkeypatch.setattr(deps, "_process_registry", None)
    monkeypatch.setattr(deps, "_process_providers_dict_id", None)

    settings = _mock_settings(nvidia_nim_api_key="")
    starlette_app = Starlette()
    starlette_app.state = State()
    starlette_app.state.provider_registry = ProviderRegistry(shared)

    with pytest.raises(ResolverProviderAuthUnavailable) as pc:
        resolve_provider("nvidia_nim", app=None, settings=settings)
    with pytest.raises(ResolverProviderAuthUnavailable) as app_exc:
        resolve_provider(
            "nvidia_nim",
            app=starlette_app,
            settings=settings,
        )
    assert pc.value.status_code == app_exc.value.status_code == 503
    assert pc.value.detail == app_exc.value.detail
