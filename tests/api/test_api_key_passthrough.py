"""Tests for API key pass-through (ENABLE_API_KEY_PASSTHROUGH)."""

from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.applications import Starlette
from starlette.datastructures import State

from api.dependencies import (
    require_api_key,
    resolve_provider,
)
from config.provider_catalog import PROVIDER_CATALOG
from providers.nvidia_nim import NvidiaNimProvider
from providers.registry import ProviderRegistry, build_provider_config, create_provider


def _make_settings(**overrides):
    """Create a mock settings object with all required fields."""
    mock = MagicMock()
    mock.model = "nvidia_nim/meta/llama3"
    mock.provider_type = "nvidia_nim"
    mock.nvidia_nim_api_key = "test_key"
    mock.open_router_api_key = "test_openrouter_key"
    mock.deepseek_api_key = "test_deepseek_key"
    mock.wafer_api_key = "test_wafer_key"
    mock.opencode_api_key = "test_opencode_key"
    mock.zai_api_key = "test_zai_key"
    mock.openai_api_key = "test_openai_key"
    mock.kimi_api_key = "test_kimi_key"
    mock.lm_studio_base_url = "http://localhost:1234/v1"
    mock.llamacpp_base_url = "http://localhost:8080/v1"
    mock.ollama_base_url = "http://localhost:11434"
    mock.llamacpp_api_key = ""
    mock.ollama_api_key = ""
    mock.nvidia_nim_proxy = ""
    mock.open_router_proxy = ""
    mock.lmstudio_proxy = ""
    mock.llamacpp_proxy = ""
    mock.kimi_proxy = ""
    mock.wafer_proxy = ""
    mock.opencode_proxy = ""
    mock.zai_proxy = ""
    mock.openai_proxy = ""
    mock.provider_rate_limit = 40
    mock.provider_rate_window = 60
    mock.provider_max_concurrency = 5
    mock.http_read_timeout = 300.0
    mock.http_write_timeout = 10.0
    mock.http_connect_timeout = 10.0
    mock.enable_model_thinking = True
    mock.log_raw_sse_events = False
    mock.log_api_error_tracebacks = False
    mock.enable_api_key_passthrough = False
    mock.anthropic_auth_token = ""
    for key, value in overrides.items():
        setattr(mock, key, value)
    return mock


class TestBuildProviderConfigPassthrough:
    """Tests for build_provider_config with passthrough_api_key."""

    def test_passthrough_disabled_uses_configured_credential(self):
        """When passthrough is disabled, the configured provider key is used."""
        settings = _make_settings(enable_api_key_passthrough=False)
        descriptor = PROVIDER_CATALOG["nvidia_nim"]
        config = build_provider_config(descriptor, settings)
        assert config.api_key == "test_key"

    def test_passthrough_enabled_uses_passthrough_key(self):
        """When passthrough is enabled and key provided, it overrides credential."""
        settings = _make_settings(enable_api_key_passthrough=True)
        descriptor = PROVIDER_CATALOG["nvidia_nim"]
        config = build_provider_config(
            descriptor, settings, passthrough_api_key="sk-passthrough-123"
        )
        assert config.api_key == "sk-passthrough-123"

    def test_passthrough_enabled_empty_key_raises(self):
        """When passthrough is enabled but key is empty, raises AuthenticationError."""
        from providers.exceptions import AuthenticationError

        settings = _make_settings(enable_api_key_passthrough=True)
        descriptor = PROVIDER_CATALOG["nvidia_nim"]
        with pytest.raises(AuthenticationError, match="ENABLE_API_KEY_PASSTHROUGH"):
            build_provider_config(descriptor, settings, passthrough_api_key="")

    def test_passthrough_enabled_key_present_but_passthrough_disabled(self):
        """Passthrough key is ignored when enable_api_key_passthrough is False."""
        settings = _make_settings(enable_api_key_passthrough=False)
        descriptor = PROVIDER_CATALOG["nvidia_nim"]
        config = build_provider_config(
            descriptor, settings, passthrough_api_key="sk-ignored"
        )
        assert config.api_key == "test_key"

    def test_passthrough_skips_credential_validation(self):
        """With passthrough active, missing per-provider key does not raise."""
        settings = _make_settings(
            enable_api_key_passthrough=True, nvidia_nim_api_key=""
        )
        descriptor = PROVIDER_CATALOG["nvidia_nim"]
        config = build_provider_config(
            descriptor, settings, passthrough_api_key="sk-valid"
        )
        assert config.api_key == "sk-valid"

    def test_passthrough_disabled_missing_key_raises(self):
        """Without passthrough, missing required credential still raises."""
        from providers.exceptions import AuthenticationError

        settings = _make_settings(
            enable_api_key_passthrough=False, nvidia_nim_api_key=""
        )
        descriptor = PROVIDER_CATALOG["nvidia_nim"]
        with pytest.raises(AuthenticationError, match="NVIDIA_NIM_API_KEY"):
            build_provider_config(descriptor, settings)

    def test_passthrough_with_static_credential_provider(self):
        """Passthrough overrides even static credentials (e.g. lmstudio)."""
        settings = _make_settings(enable_api_key_passthrough=True)
        descriptor = PROVIDER_CATALOG["lmstudio"]
        config = build_provider_config(
            descriptor, settings, passthrough_api_key="sk-lmstudio-passthrough"
        )
        assert config.api_key == "sk-lmstudio-passthrough"


class TestCreateProviderPassthrough:
    """Tests for create_provider with passthrough_api_key."""

    def test_create_provider_with_passthrough(self):
        """create_provider passes passthrough key through to provider config."""
        settings = _make_settings(enable_api_key_passthrough=True)
        with patch("providers.openai_compat.AsyncOpenAI"):
            provider = create_provider(
                "nvidia_nim", settings, passthrough_api_key="sk-nim-passthrough"
            )
        assert isinstance(provider, NvidiaNimProvider)
        assert provider._api_key == "sk-nim-passthrough"

    def test_create_provider_without_passthrough(self):
        """create_provider uses configured key when passthrough is empty."""
        settings = _make_settings(enable_api_key_passthrough=False)
        with patch("providers.openai_compat.AsyncOpenAI"):
            provider = create_provider("nvidia_nim", settings)
        assert isinstance(provider, NvidiaNimProvider)
        assert provider._api_key == "test_key"


class TestProviderRegistryPassthrough:
    """Tests for ProviderRegistry.get with passthrough_api_key."""

    def test_different_passthrough_keys_get_distinct_instances(self):
        """Different passthrough keys produce separate cached provider instances."""
        registry = ProviderRegistry()
        settings = _make_settings(enable_api_key_passthrough=True)

        with patch("providers.openai_compat.AsyncOpenAI"):
            p1 = registry.get("nvidia_nim", settings, passthrough_api_key="sk-key-1")
            p2 = registry.get("nvidia_nim", settings, passthrough_api_key="sk-key-2")

        assert p1 is not p2
        assert isinstance(p1, NvidiaNimProvider)
        assert isinstance(p2, NvidiaNimProvider)
        assert p1._api_key == "sk-key-1"
        assert p2._api_key == "sk-key-2"

    def test_same_passthrough_key_returns_cached_instance(self):
        """Same passthrough key returns the cached provider instance."""
        registry = ProviderRegistry()
        settings = _make_settings(enable_api_key_passthrough=True)

        with patch("providers.openai_compat.AsyncOpenAI"):
            p1 = registry.get("nvidia_nim", settings, passthrough_api_key="sk-same")
            p2 = registry.get("nvidia_nim", settings, passthrough_api_key="sk-same")

        assert p1 is p2

    def test_no_passthrough_caches_by_provider_id(self):
        """Without passthrough, caching works by provider_id as before."""
        registry = ProviderRegistry()
        settings = _make_settings(enable_api_key_passthrough=False)

        with patch("providers.openai_compat.AsyncOpenAI"):
            p1 = registry.get("nvidia_nim", settings)
            p2 = registry.get("nvidia_nim", settings)

        assert p1 is p2

    def test_passthrough_empty_key_raises_in_registry(self):
        """A passthrough-enabled registry raises when no client token given."""
        from providers.exceptions import AuthenticationError

        registry = ProviderRegistry()
        settings = _make_settings(enable_api_key_passthrough=True)

        with (
            pytest.raises(AuthenticationError, match="ENABLE_API_KEY_PASSTHROUGH"),
            patch("providers.openai_compat.AsyncOpenAI"),
        ):
            registry.get("nvidia_nim", settings)

    def test_different_passthrough_keys_are_distinct(self):
        """Providers with different passthrough keys are separate instances."""
        registry = ProviderRegistry()
        settings = _make_settings(enable_api_key_passthrough=True)

        with patch("providers.openai_compat.AsyncOpenAI"):
            p_a = registry.get("nvidia_nim", settings, passthrough_api_key="sk-aaa")
            p_b = registry.get("nvidia_nim", settings, passthrough_api_key="sk-bbb")

        assert p_a is not p_b


class TestRequireApiKeyReturnsToken:
    """Tests that require_api_key returns the extracted client token."""

    def test_returns_token_on_valid_x_api_key(self):
        """Valid x-api-key header returns the extracted token."""
        request = MagicMock()
        request.headers = {"x-api-key": "my-secret-key"}
        settings = _make_settings(anthropic_auth_token="my-secret-key")
        token = require_api_key(request, settings)
        assert token == "my-secret-key"

    def test_returns_token_on_valid_bearer(self):
        """Valid Bearer authorization returns the token (without Bearer prefix)."""
        request = MagicMock()
        request.headers = {"authorization": "Bearer my-bearer-key"}
        settings = _make_settings(anthropic_auth_token="my-bearer-key")
        token = require_api_key(request, settings)
        assert token == "my-bearer-key"

    def test_returns_empty_string_when_no_auth_configured(self):
        """When ANTHROPIC_AUTH_TOKEN is empty, returns empty string."""
        request = MagicMock()
        request.headers = {}
        settings = _make_settings(anthropic_auth_token="")
        token = require_api_key(request, settings)
        assert token == ""

    def test_raises_401_on_invalid_key(self):
        """Invalid API key raises 401."""
        request = MagicMock()
        request.headers = {"x-api-key": "wrong-key"}
        settings = _make_settings(anthropic_auth_token="correct-key")
        with pytest.raises(HTTPException) as exc_info:
            require_api_key(request, settings)
        assert exc_info.value.status_code == 401

    def test_strips_colon_suffix(self):
        """Token with colon suffix (model name append) gets stripped."""
        request = MagicMock()
        request.headers = {"x-api-key": "my-key:claude-3-opus"}
        settings = _make_settings(anthropic_auth_token="my-key")
        token = require_api_key(request, settings)
        assert token == "my-key"


class TestResolveProviderPassthrough:
    """Tests for resolve_provider with passthrough_api_key."""

    def test_resolve_provider_passes_passthrough_key(self):
        """resolve_provider forwards passthrough_api_key to the registry."""
        settings = _make_settings(enable_api_key_passthrough=True)
        app = SimpleNamespace(state=State())
        registry = ProviderRegistry()
        app.state.provider_registry = registry

        with patch("providers.openai_compat.AsyncOpenAI"):
            provider = resolve_provider(
                "nvidia_nim",
                app=cast(Starlette, app),
                settings=settings,
                passthrough_api_key="sk-resolve-test",
            )

        assert isinstance(provider, NvidiaNimProvider)
        assert provider._api_key == "sk-resolve-test"
