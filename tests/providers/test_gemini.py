"""Tests for Google AI Studio Gemini (OpenAI-compatible) provider."""

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from providers.base import ProviderConfig
from providers.gemini import GEMINI_DEFAULT_BASE, GeminiProvider
from providers.gemini.request import _inject_thought_signatures


class MockMessage:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class MockRequest:
    def __init__(self, **kwargs):
        self.model = "gemini-3-flash-preview"
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
def gemini_config():
    return ProviderConfig(
        api_key="test_gemini_key",
        base_url=GEMINI_DEFAULT_BASE,
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
def gemini_provider(gemini_config):
    return GeminiProvider(gemini_config)


def test_init(gemini_config):
    """Test provider initialization."""
    with patch("providers.openai_compat.AsyncOpenAI") as mock_openai:
        provider = GeminiProvider(gemini_config)
        assert provider._api_key == "test_gemini_key"
        assert (
            provider._base_url
            == "https://generativelanguage.googleapis.com/v1beta/openai"
        )
        mock_openai.assert_called_once()


def test_default_base_url_constant():
    assert GEMINI_DEFAULT_BASE == (
        "https://generativelanguage.googleapis.com/v1beta/openai/"
    )


# ── reasoning_effort tests ──────────────────────────────────────────────


def test_build_request_body_default_reasoning_effort(gemini_provider):
    """Default reasoning_effort is 'low' when thinking is enabled."""
    req = MockRequest()
    body = gemini_provider._build_request_body(req)

    assert body["model"] == "gemini-3-flash-preview"
    assert body["messages"][0]["role"] == "system"
    assert body["reasoning_effort"] == "low"


def test_build_request_body_budget_maps_to_effort(gemini_provider):
    """Explicit budget_tokens maps to the correct reasoning_effort."""
    # budget <= 1024 → "minimal"
    req = MockRequest()
    req.thinking.budget_tokens = 512
    assert gemini_provider._build_request_body(req)["reasoning_effort"] == "minimal"

    # 1024 < budget <= 2048 → "low"
    req.thinking.budget_tokens = 2048
    assert gemini_provider._build_request_body(req)["reasoning_effort"] == "low"

    # 2048 < budget <= 8192 → "medium"
    req.thinking.budget_tokens = 4096
    assert gemini_provider._build_request_body(req)["reasoning_effort"] == "medium"

    # budget > 8192 → "high"
    req.thinking.budget_tokens = 16384
    assert gemini_provider._build_request_body(req)["reasoning_effort"] == "high"


def test_build_request_body_reasoning_effort_none_when_disabled():
    """reasoning_effort is 'none' when thinking is disabled -- for Gemini 2.5
    models that default to thinking-on.  Gemini 3.x ignores the field."""
    provider = GeminiProvider(
        ProviderConfig(
            api_key="test_gemini_key",
            base_url=GEMINI_DEFAULT_BASE,
            rate_limit=10,
            rate_window=60,
            enable_thinking=False,
        )
    )
    req = MockRequest(model="gemini-2.5-flash")
    body = provider._build_request_body(req)

    assert body["reasoning_effort"] == "none"
    roles = [m.get("role") for m in body.get("messages", [])]
    assert "assistant_reasoning_content" not in roles


def test_build_request_body_preserves_caller_extra_body(gemini_provider):
    """Caller's extra_body metadata is preserved."""
    req = MockRequest(extra_body={"metadata": {"user": "u1"}})

    body = gemini_provider._build_request_body(req)

    eb = body.get("extra_body")
    assert isinstance(eb, dict)
    assert eb.get("metadata") == {"user": "u1"}


def test_build_request_body_preserves_caller_google_keys(gemini_provider):
    """Caller's extra_body.google keys pass through alongside reasoning_effort."""
    req = MockRequest(
        extra_body={
            "metadata": {"user": "u1"},
            "extra_body": {
                "google": {
                    "cached_content": "cachedContents/example",
                }
            },
        }
    )

    body = gemini_provider._build_request_body(req)

    assert body["reasoning_effort"] == "low"
    eb = body.get("extra_body")
    assert isinstance(eb, dict)
    assert eb.get("metadata") == {"user": "u1"}
    literal = eb.get("extra_body")
    assert isinstance(literal, dict)
    assert literal["google"]["cached_content"] == "cachedContents/example"


# ── sampling parameters ─────────────────────────────────────────────────


def test_strips_temperature_and_top_p_when_thinking_enabled(gemini_provider):
    """temperature and top_p are removed when thinking is active."""
    req = MockRequest()
    req.model = "gemini-3.5-flash"
    req.temperature = 0.5
    req.top_p = 0.9

    body = gemini_provider._build_request_body(req)

    assert "temperature" not in body
    assert "top_p" not in body
    assert body["reasoning_effort"] == "low"


def test_preserves_temperature_and_top_p_when_thinking_disabled():
    """temperature and top_p are kept when thinking is off."""
    provider = GeminiProvider(
        ProviderConfig(
            api_key="test_key",
            base_url=GEMINI_DEFAULT_BASE,
            enable_thinking=False,
        )
    )
    req = MockRequest()
    req.model = "gemini-3.5-flash"
    req.temperature = 0.5
    req.top_p = 0.9

    body = provider._build_request_body(req)

    assert body.get("temperature") == 0.5
    assert body.get("top_p") == 0.9


# ── misc body fields ────────────────────────────────────────────────────


def test_parallel_tool_calls_disabled(gemini_provider):
    """parallel_tool_calls is always False."""
    req = MockRequest()
    body = gemini_provider._build_request_body(req)
    assert body["parallel_tool_calls"] is False


def test_parallel_tool_calls_disabled_no_thinking():
    """parallel_tool_calls is False even with thinking disabled."""
    provider = GeminiProvider(
        ProviderConfig(
            api_key="test_key",
            base_url=GEMINI_DEFAULT_BASE,
            enable_thinking=False,
        )
    )
    body = provider._build_request_body(MockRequest())
    assert body["parallel_tool_calls"] is False


# ── thought signatures ──────────────────────────────────────────────────


class TestInjectThoughtSignatures:
    """Tests for :func:`_inject_thought_signatures`."""

    def test_injects_into_tool_calls(self):
        """thought_signature is added to every tool call in the message list."""
        messages: list[Any] = [
            {"role": "system", "content": "You are helpful."},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "Read",
                            "arguments": '{"file_path": "/tmp/x"}',
                        },
                    },
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "Bash",
                            "arguments": '{"command": "ls"}',
                        },
                    },
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "ok"},
        ]

        _inject_thought_signatures(messages)

        for tc_raw in messages[1]["tool_calls"]:
            tc: Any = tc_raw
            assert tc["extra_content"]["google"]["thought_signature"] == (
                "skip_thought_signature_validator"
            )

    def test_no_tool_calls_is_noop(self):
        """Messages without tool_calls are not modified."""
        import json

        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        before = json.loads(json.dumps(messages))
        _inject_thought_signatures(messages)
        assert messages == before

    def test_preserves_existing_thought_signature(self):
        """An existing thought_signature is not overwritten."""
        messages = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "Read", "arguments": "{}"},
                        "extra_content": {
                            "google": {"thought_signature": "original_signature"}
                        },
                    },
                ],
            },
        ]

        _inject_thought_signatures(messages)

        assert (
            messages[0]["tool_calls"][0]["extra_content"]["google"]["thought_signature"]
            == "original_signature"
        )

    def test_preserves_existing_extra_content(self):
        """Other extra_content fields are preserved alongside thought_signature."""
        messages = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "Read", "arguments": "{}"},
                        "extra_content": {
                            "google": {"cached_content": "cachedContents/example"}
                        },
                    },
                ],
            },
        ]

        _inject_thought_signatures(messages)

        google = messages[0]["tool_calls"][0]["extra_content"]["google"]
        assert google["cached_content"] == "cachedContents/example"
        assert google["thought_signature"] == "skip_thought_signature_validator"

    def test_tool_calls_not_list_is_noop(self):
        """tool_calls that is not a list is skipped."""
        messages = [{"role": "assistant", "content": None, "tool_calls": None}]
        _inject_thought_signatures(messages)
        assert messages[0]["tool_calls"] is None

    def test_empty_list_is_noop(self):
        """Empty tool_calls list is not modified."""
        messages = [{"role": "assistant", "content": None, "tool_calls": []}]
        _inject_thought_signatures(messages)
        assert messages[0]["tool_calls"] == []

    def test_build_request_body_injects_when_thinking_enabled(self, gemini_provider):
        """_build_request_body injects thought_signatures when thinking=True."""
        req = MockRequest(
            messages=[
                MockMessage("user", "Hello"),
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_1",
                            "name": "Read",
                            "input": {"file_path": "/x"},
                        }
                    ],
                },
            ],
        )
        req.messages = [
            MagicMock(role="user", content=[{"type": "text", "text": "Hello"}]),
            MagicMock(
                role="assistant",
                content=[
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "Read",
                        "input": {"file_path": "/x"},
                    }
                ],
            ),
        ]

        body = gemini_provider._build_request_body(req)

        for msg in body.get("messages", []):
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    assert (
                        tc["extra_content"]["google"]["thought_signature"]
                        == "skip_thought_signature_validator"
                    )

    def test_build_request_body_skips_when_thinking_disabled(self):
        """_build_request_body does NOT inject thought_signatures when thinking=False."""
        provider = GeminiProvider(
            ProviderConfig(
                api_key="test_key",
                base_url=GEMINI_DEFAULT_BASE,
                enable_thinking=False,
            )
        )
        req = MockRequest()
        req.messages = [
            MagicMock(role="user", content=[{"type": "text", "text": "Hello"}]),
            MagicMock(
                role="assistant",
                content=[
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "Read",
                        "input": {"file_path": "/x"},
                    }
                ],
            ),
        ]

        body = provider._build_request_body(req)

        for msg in body.get("messages", []):
            if msg.get("role") == "assistant":
                tool_calls = msg.get("tool_calls", [])
                for tc in tool_calls:
                    assert "extra_content" not in tc


# ── stream response ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stream_response_text(gemini_provider):
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
        gemini_provider._client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_stream()

        events = [event async for event in gemini_provider.stream_response(req)]

        assert any(
            '"text_delta"' in event and "Hello back!" in event for event in events
        )


@pytest.mark.asyncio
async def test_stream_response_reasoning_content(gemini_provider):
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
        gemini_provider._client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_stream()

        events = [event async for event in gemini_provider.stream_response(req)]

        assert any(
            '"thinking_delta"' in event and "Thinking..." in event for event in events
        )


@pytest.mark.asyncio
async def test_cleanup(gemini_provider):
    gemini_provider._client = AsyncMock()

    await gemini_provider.cleanup()

    gemini_provider._client.close.assert_called_once()
