"""Tests for AgentRouter native Anthropic Messages provider."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from api.models.anthropic import Message, MessagesRequest, Tool
from providers.agentrouter import AGENTROUTER_DEFAULT_BASE, AgentRouterProvider
from providers.base import ProviderConfig


class FakeResponse:
    def __init__(self, *, lines=None):
        self.status_code = 200
        self._lines = lines or []
        self.is_closed = False
        self.headers = httpx.Headers()
        self.request = httpx.Request("POST", "https://agentrouter.org/v1/messages")

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aclose(self):
        self.is_closed = True

    def raise_for_status(self):
        return None


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
def agentrouter_provider():
    return AgentRouterProvider(
        ProviderConfig(
            api_key="test-agentrouter-key",
            base_url=AGENTROUTER_DEFAULT_BASE,
            rate_limit=10,
            rate_window=60,
        )
    )


def test_default_base_url():
    assert AGENTROUTER_DEFAULT_BASE == "https://agentrouter.org/v1"


def test_init_uses_default_base_url_and_provider_name():
    config = ProviderConfig(api_key="test-agentrouter-key", base_url=None)
    with patch("httpx.AsyncClient"):
        provider = AgentRouterProvider(config)

    assert provider._api_key == "test-agentrouter-key"
    assert provider._base_url == AGENTROUTER_DEFAULT_BASE
    assert provider._provider_name == "AGENTROUTER"


def test_request_headers_match_claude_code_client_shape(agentrouter_provider):
    headers = agentrouter_provider._request_headers()

    assert headers["x-api-key"] == "test-agentrouter-key"
    assert headers["Accept"] == "application/json"
    assert headers["Content-Type"] == "application/json"
    assert headers["anthropic-version"] == "2023-06-01"
    assert headers["anthropic-dangerous-direct-browser-access"] == "true"
    assert headers["x-app"] == "cli"
    assert headers["User-Agent"].startswith("claude-cli/")
    assert "claude-code-20250219" in headers["anthropic-beta"]
    assert "Authorization" not in headers


def test_build_request_body_native_shape(agentrouter_provider):
    request = MessagesRequest.model_validate(
        {
            "model": "deepseek-v4-pro",
            "messages": [Message(role="user", content="Hello")],
            "tools": [
                Tool(
                    name="echo",
                    description="Echo input",
                    input_schema={"type": "object", "properties": {}},
                )
            ],
            "thinking": {"type": "enabled", "budget_tokens": 2048},
        }
    )

    body = agentrouter_provider._build_request_body(request)

    assert body["model"] == "deepseek-v4-pro"
    assert body["messages"][0]["role"] == "user"
    assert body["tools"][0]["name"] == "echo"
    assert body["thinking"] == {"type": "enabled", "budget_tokens": 2048}
    assert body["stream"] is True
    assert body["system"][0]["type"] == "text"
    assert "x-anthropic-billing-header:" in body["system"][0]["text"]


@pytest.mark.asyncio
async def test_lists_static_supported_models(agentrouter_provider):
    assert await agentrouter_provider.list_model_ids() == frozenset({"deepseek-v4-pro"})


@pytest.mark.asyncio
async def test_stream_uses_post_messages_path(agentrouter_provider):
    request = MessagesRequest(
        model="deepseek-v4-pro",
        messages=[Message(role="user", content="hi")],
    )
    response = FakeResponse(
        lines=[
            "event: message_start",
            'data: {"type":"message_start"}',
            "",
        ]
    )

    with (
        patch.object(
            agentrouter_provider._client, "build_request", return_value=MagicMock()
        ) as mock_build,
        patch.object(
            agentrouter_provider._client,
            "send",
            new_callable=AsyncMock,
            return_value=response,
        ),
    ):
        events = [
            event async for event in agentrouter_provider.stream_response(request)
        ]

    assert events == [
        "event: message_start\n",
        'data: {"type":"message_start"}\n',
        "\n",
        'event: message_delta\ndata: {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": null}, "usage": {"input_tokens": 0, "output_tokens": 0}}\n\n',
        'event: message_stop\ndata: {"type": "message_stop"}\n\n',
    ]
    assert response.is_closed
    assert mock_build.call_args.args[:2] == ("POST", "/messages?beta=true")
    assert mock_build.call_args.kwargs["headers"]["x-api-key"] == (
        "test-agentrouter-key"
    )
