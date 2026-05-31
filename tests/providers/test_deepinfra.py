"""Tests for DeepInfra (OpenAI-compatible) provider."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from providers.base import ProviderConfig
from providers.deepinfra import DEEPINFRA_DEFAULT_BASE, DeepInfraProvider


class MockMessage:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class MockRequest:
    def __init__(self, **kwargs):
        self.model = "meta-llama/Meta-Llama-3.1-8B-Instruct"
        self.messages = [MockMessage("user", "Hello")]
        self.max_tokens = 100
        self.temperature = 0.5
        self.top_p = 0.9
        self.system = "System prompt"
        self.stop_sequences = None
        self.tools = []
        self.thinking = MagicMock()
        self.thinking.enabled = True
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture
def deepinfra_config():
    return ProviderConfig(
        api_key="test_deepinfra_key",
        base_url=DEEPINFRA_DEFAULT_BASE,
        rate_limit=10,
        rate_window=60,
        enable_thinking=True,
    )


@pytest.fixture(autouse=True)
def mock_rate_limiter():
    """Mock the global rate limiter to prevent waiting."""

    @asynccontextmanager
    async def _slot():
        yield

    with patch("providers.openai_compat.GlobalRateLimiter") as mock:
        instance = mock.get_scoped_instance.return_value

        async def _passthrough(fn, *args, **kwargs):
            return await fn(*args, **kwargs)

        instance.execute_with_retry = AsyncMock(side_effect=_passthrough)
        instance.concurrency_slot.side_effect = _slot
        yield instance


@pytest.fixture
def deepinfra_provider(deepinfra_config):
    return DeepInfraProvider(deepinfra_config)


def test_init(deepinfra_config):
    """Test provider initialization."""
    with patch("providers.openai_compat.AsyncOpenAI") as mock_openai:
        provider = DeepInfraProvider(deepinfra_config)
        assert provider._api_key == "test_deepinfra_key"
        assert provider._base_url == DEEPINFRA_DEFAULT_BASE
        mock_openai.assert_called_once()


def test_default_base_url_constant():
    assert DEEPINFRA_DEFAULT_BASE == "https://api.deepinfra.com/v1/openai"


def test_build_request_body_basic(deepinfra_provider):
    """Basic request body conversion attaches system message from Claude request."""
    req = MockRequest()
    body = deepinfra_provider._build_request_body(req)

    assert body["model"] == "meta-llama/Meta-Llama-3.1-8B-Instruct"
    assert body["messages"][0]["role"] == "system"


def test_build_request_body_preserves_native_max_tokens(deepinfra_provider):
    """DeepInfra accepts standard OpenAI ``max_tokens`` (no remap)."""
    with patch("providers.deepinfra.request.build_base_request_body") as mock_convert:
        mock_convert.return_value = {
            "model": "meta-llama/Meta-Llama-3.1-8B-Instruct",
            "messages": [{"role": "user", "name": "alice", "content": "hi"}],
            "max_tokens": 42,
        }
        body = deepinfra_provider._build_request_body(MockRequest())

    assert body["max_tokens"] == 42
    assert "max_completion_tokens" not in body
    assert body["messages"][0].get("name") == "alice"


def test_build_request_body_global_disable_blocks_reasoning_mapping():
    provider = DeepInfraProvider(
        ProviderConfig(
            api_key="test_deepinfra_key",
            base_url=DEEPINFRA_DEFAULT_BASE,
            rate_limit=10,
            rate_window=60,
            enable_thinking=False,
        )
    )
    req = MockRequest()
    body = provider._build_request_body(req)

    roles = [m.get("role") for m in body.get("messages", [])]
    assert "assistant_reasoning_content" not in roles


def test_build_request_body_preserves_caller_extra_body(deepinfra_provider):
    req = MockRequest(extra_body={"clear_thinking": False})

    body = deepinfra_provider._build_request_body(req)

    eb = body.get("extra_body")
    assert isinstance(eb, dict)
    assert eb.get("clear_thinking") is False


@pytest.mark.asyncio
async def test_stream_response_text(deepinfra_provider):
    """Text content deltas are emitted as text blocks."""
    req = MockRequest()

    mock_chunk = MagicMock()
    mock_chunk.choices = [
        MagicMock(
            delta=MagicMock(
                content="Hello back!",
                reasoning_content=None,
                tool_calls=None,
            ),
            finish_reason="stop",
        )
    ]
    mock_chunk.usage = MagicMock(completion_tokens=5, prompt_tokens=10)

    async def mock_stream():
        yield mock_chunk

    with patch.object(
        deepinfra_provider._client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_stream()

        events = [event async for event in deepinfra_provider.stream_response(req)]

        assert any(
            '"text_delta"' in event and "Hello back!" in event for event in events
        )


@pytest.mark.asyncio
async def test_stream_response_reasoning_content(deepinfra_provider):
    """reasoning_content deltas are emitted as thinking blocks."""
    req = MockRequest()

    mock_chunk = MagicMock()
    mock_chunk.choices = [
        MagicMock(
            delta=MagicMock(
                content=None,
                reasoning_content="Thinking...",
                tool_calls=None,
            ),
            finish_reason="stop",
        )
    ]
    mock_chunk.usage = MagicMock(completion_tokens=2, prompt_tokens=10)

    async def mock_stream():
        yield mock_chunk

    with patch.object(
        deepinfra_provider._client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_stream()

        events = [event async for event in deepinfra_provider.stream_response(req)]

        assert any(
            '"thinking_delta"' in event and "Thinking..." in event for event in events
        )


@pytest.mark.asyncio
async def test_cleanup(deepinfra_provider):
    deepinfra_provider._client = AsyncMock()

    await deepinfra_provider.cleanup()

    deepinfra_provider._client.close.assert_called_once()
