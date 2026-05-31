"""Tests for MiniMax native Anthropic Messages provider."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.models.anthropic import Message, MessagesRequest
from config.constants import ANTHROPIC_DEFAULT_MAX_OUTPUT_TOKENS
from providers.base import ProviderConfig
from providers.defaults import MINIMAX_DEFAULT_BASE
from providers.minimax import MiniMaxProvider


@pytest.fixture
def minimax_config():
    return ProviderConfig(
        api_key="test_minimax_key",
        base_url=MINIMAX_DEFAULT_BASE,
        rate_limit=10,
        rate_window=60,
        enable_thinking=True,
    )


@pytest.fixture(autouse=True)
def mock_rate_limiter():
    @asynccontextmanager
    async def _slot():
        yield

    with patch("providers.anthropic_messages.GlobalRateLimiter") as mock:
        instance = mock.get_scoped_instance.return_value

        async def _passthrough(fn, *args, **kwargs):
            return await fn(*args, **kwargs)

        instance.execute_with_retry = AsyncMock(side_effect=_passthrough)
        instance.concurrency_slot.side_effect = _slot
        yield instance


@pytest.fixture
def minimax_provider(minimax_config):
    return MiniMaxProvider(minimax_config)


def test_init(minimax_config):
    with patch("httpx.AsyncClient") as mock_client:
        provider = MiniMaxProvider(minimax_config)
    assert provider._api_key == "test_minimax_key"
    assert provider._base_url == MINIMAX_DEFAULT_BASE
    assert mock_client.called


def test_request_headers_use_x_api_key_not_bearer(minimax_provider):
    h = minimax_provider._request_headers()
    assert h["X-Api-Key"] == "test_minimax_key"
    assert "Authorization" not in h
    assert h["Content-Type"] == "application/json"


def test_build_request_body_native(minimax_provider):
    request = MessagesRequest(
        model="MiniMax-M2.7",
        max_tokens=50,
        messages=[Message(role="user", content="hi")],
    )
    body = minimax_provider._build_request_body(request)
    assert body["model"] == "MiniMax-M2.7"
    assert body["stream"] is True
    assert body["messages"][0]["role"] == "user"


def test_build_request_body_default_max_tokens(minimax_provider):
    request = MessagesRequest(
        model="m",
        messages=[Message(role="user", content="x")],
    )
    body = minimax_provider._build_request_body(request)
    assert body["max_tokens"] == ANTHROPIC_DEFAULT_MAX_OUTPUT_TOKENS


@pytest.mark.asyncio
async def test_model_list_uses_minimax_models_url(minimax_provider):
    called: dict[str, object] = {}

    async def fake_get(url: str, **kwargs):
        called["url"] = url
        called["headers"] = kwargs.get("headers")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = lambda: None
        mock_resp.json = lambda: {"data": [{"id": "MiniMax-M2.7"}]}
        mock_resp.aclose = AsyncMock()
        return mock_resp

    minimax_provider._client.get = fake_get

    await minimax_provider.list_model_infos()

    assert called["url"] == "https://api.minimax.io/models"
    assert called["headers"] == {"X-Api-Key": "test_minimax_key"}


@pytest.mark.asyncio
async def test_cleanup_aclose(minimax_provider):
    minimax_provider._client = AsyncMock()

    await minimax_provider.cleanup()

    minimax_provider._client.aclose.assert_awaited_once()
