"""Tests for the generic OpenAI-compatible provider (registry wiring + request body)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from config.provider_catalog import OPENAI_COMPAT_DEFAULT_BASE, PROVIDER_CATALOG
from core.anthropic import ReasoningReplayMode
from providers.base import ProviderConfig
from providers.openai_compat_generic import OpenAICompatProvider
from providers.registry import build_provider_config, create_provider


def _make_settings(**overrides) -> MagicMock:
    settings = MagicMock()
    settings.model = "openai_compat/test-model"
    settings.provider_type = "openai_compat"
    settings.openai_compat_api_key = ""
    settings.openai_compat_base_url = ""
    settings.openai_compat_proxy = ""
    settings.provider_rate_limit = 40
    settings.provider_rate_window = 60
    settings.provider_max_concurrency = 5
    settings.http_read_timeout = 300.0
    settings.http_write_timeout = 10.0
    settings.http_connect_timeout = 10.0
    settings.enable_model_thinking = True
    settings.log_raw_sse_events = False
    settings.log_api_error_tracebacks = False
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def _make_config(api_key: str = "", base_url: str = "") -> ProviderConfig:
    return ProviderConfig(
        api_key=api_key,
        base_url=base_url or None,
        rate_limit=100,
        rate_window=60,
        http_read_timeout=300.0,
        http_write_timeout=10.0,
        http_connect_timeout=10.0,
        enable_thinking=True,
    )


def test_catalog_entry_does_not_require_api_key():
    """OpenAI-compatible local servers often need no key — descriptor must allow it."""
    descriptor = PROVIDER_CATALOG["openai_compat"]
    assert descriptor.credential_env is None
    assert descriptor.credential_attr == "openai_compat_api_key"
    assert descriptor.default_base_url == OPENAI_COMPAT_DEFAULT_BASE


def test_build_provider_config_succeeds_without_api_key():
    """build_provider_config must not raise AuthenticationError when key is missing."""
    descriptor = PROVIDER_CATALOG["openai_compat"]
    settings = _make_settings(openai_compat_api_key="")
    config = build_provider_config(descriptor, settings)
    assert config.api_key == ""
    assert config.base_url == OPENAI_COMPAT_DEFAULT_BASE


def test_create_provider_wires_openai_compat_with_placeholder_key():
    settings = _make_settings()
    with patch("providers.openai_compat.AsyncOpenAI") as mock_openai:
        provider = create_provider("openai_compat", settings)
    assert isinstance(provider, OpenAICompatProvider)
    # AsyncOpenAI must receive a non-empty api_key (placeholder when user has none).
    _, kwargs = mock_openai.call_args
    assert kwargs["api_key"] == "EMPTY"
    assert kwargs["base_url"] == OPENAI_COMPAT_DEFAULT_BASE


def test_create_provider_passes_user_supplied_key_when_set():
    settings = _make_settings(
        openai_compat_api_key="sk-real",
        openai_compat_base_url="https://example.invalid/v1",
    )
    with patch("providers.openai_compat.AsyncOpenAI") as mock_openai:
        create_provider("openai_compat", settings)
    _, kwargs = mock_openai.call_args
    assert kwargs["api_key"] == "sk-real"
    assert kwargs["base_url"] == "https://example.invalid/v1"


def _stub_request(thinking: bool | None = None) -> SimpleNamespace:
    """Minimal Anthropic-style request the conversion layer accepts."""
    return SimpleNamespace(
        model="test-model",
        messages=[{"role": "user", "content": "hi"}],
        system=None,
        tools=None,
        max_tokens=64,
        temperature=None,
        top_p=None,
        stop_sequences=None,
        stream=True,
        thinking=({"type": "enabled"} if thinking else {"type": "disabled"})
        if thinking is not None
        else None,
    )


@pytest.mark.parametrize(
    "thinking_enabled,expected_mode",
    [
        (True, ReasoningReplayMode.REASONING_CONTENT),
        (False, ReasoningReplayMode.DISABLED),
    ],
)
def test_build_request_body_passes_reasoning_replay_for_thinking(
    thinking_enabled, expected_mode
):
    """``_build_request_body`` must propagate the thinking flag to the converter."""
    with patch("providers.openai_compat.AsyncOpenAI"):
        provider = OpenAICompatProvider(_make_config(api_key="k"))

    captured: dict = {}

    def fake_build(request, *, reasoning_replay):  # noqa: ARG001
        captured["mode"] = reasoning_replay
        return {"model": request.model, "messages": []}

    with patch(
        "providers.openai_compat_generic.client.build_base_request_body",
        side_effect=fake_build,
    ):
        provider._build_request_body(
            _stub_request(thinking=thinking_enabled),
            thinking_enabled=thinking_enabled,
        )

    assert captured["mode"] is expected_mode
