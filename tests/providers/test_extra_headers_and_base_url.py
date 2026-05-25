"""Tests for per-provider base_url override and PROVIDER_EXTRA_HEADERS injection."""

from unittest.mock import MagicMock, patch

import pytest

from config.nim import NimSettings
from config.provider_catalog import PROVIDER_CATALOG
from config.settings import Settings
from providers.base import ProviderConfig
from providers.registry import build_provider_config, create_provider

# ---- Settings layer ---------------------------------------------------------


def _isolate_env(monkeypatch) -> None:
    """Remove ambient env state that would shadow validation_alias defaults."""
    monkeypatch.setitem(Settings.model_config, "env_file", ())
    for key in (
        "PROVIDER_EXTRA_HEADERS",
        "NVIDIA_NIM_BASE_URL",
        "GROQ_BASE_URL",
        "CEREBRAS_BASE_URL",
        "GEMINI_BASE_URL",
        "OPENROUTER_BASE_URL",
        "MISTRAL_BASE_URL",
        "CODESTRAL_BASE_URL",
        "DEEPSEEK_BASE_URL",
        "KIMI_BASE_URL",
        "WAFER_BASE_URL",
        "OPENCODE_BASE_URL",
        "OPENCODE_GO_BASE_URL",
        "FIREWORKS_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_provider_extra_headers_defaults_to_empty(monkeypatch):
    _isolate_env(monkeypatch)
    settings = Settings()
    assert settings.provider_extra_headers == {}


def test_provider_extra_headers_parses_json_object(monkeypatch):
    _isolate_env(monkeypatch)
    monkeypatch.setenv(
        "PROVIDER_EXTRA_HEADERS",
        '{"x-tenant-id": "team-a", "x-feature": "chat"}',
    )
    settings = Settings()
    assert settings.provider_extra_headers == {
        "x-tenant-id": "team-a",
        "x-feature": "chat",
    }


def test_provider_extra_headers_empty_string_is_empty_dict(
    monkeypatch,
):
    _isolate_env(monkeypatch)
    monkeypatch.setenv("PROVIDER_EXTRA_HEADERS", "")
    settings = Settings()
    assert settings.provider_extra_headers == {}


def test_provider_extra_headers_coerces_non_string_values(
    monkeypatch,
):
    _isolate_env(monkeypatch)
    monkeypatch.setenv("PROVIDER_EXTRA_HEADERS", '{"x-rank": 7, "x-flag": true}')
    settings = Settings()
    assert settings.provider_extra_headers == {"x-rank": "7", "x-flag": "True"}


def test_provider_extra_headers_rejects_invalid_json(
    monkeypatch,
):
    _isolate_env(monkeypatch)
    monkeypatch.setenv("PROVIDER_EXTRA_HEADERS", "not-json")
    with pytest.raises(Exception, match="PROVIDER_EXTRA_HEADERS"):
        Settings()


def test_provider_extra_headers_rejects_non_object_json(
    monkeypatch,
):
    _isolate_env(monkeypatch)
    monkeypatch.setenv("PROVIDER_EXTRA_HEADERS", '["not", "an", "object"]')
    with pytest.raises(Exception, match="PROVIDER_EXTRA_HEADERS"):
        Settings()


@pytest.mark.parametrize(
    "env_key, settings_attr, value",
    [
        ("NVIDIA_NIM_BASE_URL", "nvidia_nim_base_url", "http://proxy.local/nim/v1"),
        ("GROQ_BASE_URL", "groq_base_url", "http://proxy.local/groq/v1"),
        ("CEREBRAS_BASE_URL", "cerebras_base_url", "http://proxy.local/cerebras/v1"),
        ("GEMINI_BASE_URL", "gemini_base_url", "http://proxy.local/gemini/v1"),
        ("OPENROUTER_BASE_URL", "open_router_base_url", "http://proxy.local/or/v1"),
        ("MISTRAL_BASE_URL", "mistral_base_url", "http://proxy.local/mistral/v1"),
        ("CODESTRAL_BASE_URL", "codestral_base_url", "http://proxy.local/code/v1"),
        ("DEEPSEEK_BASE_URL", "deepseek_base_url", "http://proxy.local/ds/anthropic"),
        ("KIMI_BASE_URL", "kimi_base_url", "http://proxy.local/kimi/anthropic/v1"),
        ("WAFER_BASE_URL", "wafer_base_url", "http://proxy.local/wafer/v1"),
        ("OPENCODE_BASE_URL", "opencode_base_url", "http://proxy.local/oc/v1"),
        ("OPENCODE_GO_BASE_URL", "opencode_go_base_url", "http://proxy.local/ocg/v1"),
        ("FIREWORKS_BASE_URL", "fireworks_base_url", "http://proxy.local/fw/v1"),
    ],
)
def test_cloud_provider_base_url_env_var_populates_settings(
    monkeypatch,
    env_key: str,
    settings_attr: str,
    value: str,
) -> None:
    _isolate_env(monkeypatch)
    monkeypatch.setenv(env_key, value)
    settings = Settings()
    assert getattr(settings, settings_attr) == value


def test_settings_has_no_zai_base_url_attribute(monkeypatch):
    """Z.ai endpoint is intentionally pinned; ZAI_BASE_URL must not exist."""
    _isolate_env(monkeypatch)
    monkeypatch.setenv("ZAI_BASE_URL", "http://stale.zai.invalid/v1")
    settings = Settings()
    assert not hasattr(settings, "zai_base_url")


# ---- Descriptor + registry layer --------------------------------------------


@pytest.mark.parametrize(
    "provider_id, expected_attr",
    [
        ("nvidia_nim", "nvidia_nim_base_url"),
        ("open_router", "open_router_base_url"),
        ("gemini", "gemini_base_url"),
        ("deepseek", "deepseek_base_url"),
        ("mistral", "mistral_base_url"),
        ("mistral_codestral", "codestral_base_url"),
        ("opencode", "opencode_base_url"),
        ("opencode_go", "opencode_go_base_url"),
        ("wafer", "wafer_base_url"),
        ("kimi", "kimi_base_url"),
        ("cerebras", "cerebras_base_url"),
        ("groq", "groq_base_url"),
        ("fireworks", "fireworks_base_url"),
    ],
)
def test_cloud_descriptors_wire_base_url_attr(
    provider_id: str, expected_attr: str
) -> None:
    descriptor = PROVIDER_CATALOG[provider_id]
    assert descriptor.base_url_attr == expected_attr


def _make_settings(**overrides) -> MagicMock:
    """Minimal mock Settings shaped like tests/providers/test_registry.py."""
    mock = MagicMock()
    mock.nvidia_nim_api_key = "k"
    mock.open_router_api_key = "k"
    mock.mistral_api_key = "k"
    mock.codestral_api_key = "k"
    mock.deepseek_api_key = "k"
    mock.kimi_api_key = "k"
    mock.wafer_api_key = "k"
    mock.opencode_api_key = "k"
    mock.zai_api_key = "k"
    mock.fireworks_api_key = "k"
    mock.gemini_api_key = "k"
    mock.groq_api_key = "k"
    mock.cerebras_api_key = "k"
    mock.lm_studio_base_url = "http://localhost:1234/v1"
    mock.llamacpp_base_url = "http://localhost:8080/v1"
    mock.ollama_base_url = "http://localhost:11434"
    mock.nvidia_nim_base_url = ""
    mock.open_router_base_url = ""
    mock.mistral_base_url = ""
    mock.codestral_base_url = ""
    mock.deepseek_base_url = ""
    mock.kimi_base_url = ""
    mock.wafer_base_url = ""
    mock.opencode_base_url = ""
    mock.opencode_go_base_url = ""
    mock.fireworks_base_url = ""
    mock.gemini_base_url = ""
    mock.groq_base_url = ""
    mock.cerebras_base_url = ""
    mock.nvidia_nim_proxy = ""
    mock.open_router_proxy = ""
    mock.mistral_proxy = ""
    mock.codestral_proxy = ""
    mock.deepseek_proxy = ""
    mock.kimi_proxy = ""
    mock.wafer_proxy = ""
    mock.opencode_proxy = ""
    mock.opencode_go_proxy = ""
    mock.zai_proxy = ""
    mock.fireworks_proxy = ""
    mock.gemini_proxy = ""
    mock.groq_proxy = ""
    mock.cerebras_proxy = ""
    mock.lmstudio_proxy = ""
    mock.llamacpp_proxy = ""
    mock.provider_rate_limit = 40
    mock.provider_rate_window = 60
    mock.provider_max_concurrency = 5
    mock.http_read_timeout = 300.0
    mock.http_write_timeout = 10.0
    mock.http_connect_timeout = 10.0
    mock.enable_model_thinking = True
    mock.log_raw_sse_events = False
    mock.log_api_error_tracebacks = False
    mock.provider_extra_headers = {}
    mock.nim = NimSettings()
    for key, value in overrides.items():
        setattr(mock, key, value)
    return mock


def test_build_provider_config_respects_base_url_override() -> None:
    descriptor = PROVIDER_CATALOG["groq"]
    settings = _make_settings(groq_base_url="http://proxy.local/groq/v1")

    config = build_provider_config(descriptor, settings)

    assert config.base_url == "http://proxy.local/groq/v1"


def test_build_provider_config_falls_back_to_default_when_unset() -> None:
    descriptor = PROVIDER_CATALOG["groq"]
    settings = _make_settings()

    config = build_provider_config(descriptor, settings)

    assert config.base_url == descriptor.default_base_url


def test_build_provider_config_propagates_extra_headers() -> None:
    descriptor = PROVIDER_CATALOG["groq"]
    headers = {"x-tenant-id": "team-a", "x-feature": "chat"}
    settings = _make_settings(provider_extra_headers=headers)

    config = build_provider_config(descriptor, settings)

    assert config.extra_headers == headers
    # Mutation must not leak back into Settings.provider_extra_headers.
    config.extra_headers["x-injected"] = "via-mutation"
    assert "x-injected" not in settings.provider_extra_headers


# ---- Transport layer --------------------------------------------------------


def test_openai_chat_transport_passes_default_headers_to_async_openai() -> None:
    settings = _make_settings(
        groq_api_key="test-key",
        provider_extra_headers={"x-tenant-id": "team-a"},
    )
    with (
        patch("providers.openai_compat.AsyncOpenAI") as mock_openai,
        patch("httpx.AsyncClient"),
    ):
        create_provider("groq", settings)
        kwargs = mock_openai.call_args.kwargs
        assert kwargs["default_headers"] == {"x-tenant-id": "team-a"}


def test_openai_chat_transport_default_headers_is_none_when_unset() -> None:
    settings = _make_settings(groq_api_key="test-key")
    with (
        patch("providers.openai_compat.AsyncOpenAI") as mock_openai,
        patch("httpx.AsyncClient"),
    ):
        create_provider("groq", settings)
        kwargs = mock_openai.call_args.kwargs
        assert kwargs["default_headers"] is None


def test_anthropic_messages_transport_passes_headers_to_httpx_client() -> None:
    settings = _make_settings(
        kimi_api_key="test-key",
        provider_extra_headers={"x-tenant-id": "team-a", "x-feature": "chat"},
    )
    with patch("providers.anthropic_messages.httpx.AsyncClient") as mock_client:
        create_provider("kimi", settings)
        kwargs = mock_client.call_args.kwargs
        assert kwargs["headers"] == {
            "x-tenant-id": "team-a",
            "x-feature": "chat",
        }


def test_anthropic_messages_transport_headers_is_none_when_unset() -> None:
    settings = _make_settings(kimi_api_key="test-key")
    with patch("providers.anthropic_messages.httpx.AsyncClient") as mock_client:
        create_provider("kimi", settings)
        kwargs = mock_client.call_args.kwargs
        assert kwargs["headers"] is None


def test_provider_config_default_extra_headers_is_empty_dict() -> None:
    config = ProviderConfig(api_key="x")
    assert config.extra_headers == {}
