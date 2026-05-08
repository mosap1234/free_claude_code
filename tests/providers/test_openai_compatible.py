from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from providers.base import ProviderConfig
from providers.defaults import OPENAI_COMPATIBLE_DEFAULT_BASE
from providers.openai_compatible import OpenAICompatibleProvider
from providers.openai_compatible.request import build_request_body


class MockMessage:
    def __init__(self, role, content, reasoning_content: str | None = None):
        self.role = role
        self.content = content
        self.reasoning_content = reasoning_content


class MockRequest:
    def __init__(self, **overrides):
        self.model = "qwen2.5-coder"
        self.messages = [MockMessage("user", "Hello")]
        self.max_tokens = 100
        self.temperature = 0.2
        self.top_p = 0.9
        self.system = "You are concise."
        self.stop_sequences = None
        self.tools = None
        self.tool_choice = None
        self.extra_body = None
        self.thinking = MagicMock()
        self.thinking.enabled = False
        for key, value in overrides.items():
            setattr(self, key, value)


def test_provider_initializes_with_local_defaults():
    config = ProviderConfig(api_key="", base_url=None)

    with patch("providers.openai_compat.AsyncOpenAI") as mock_openai:
        provider = OpenAICompatibleProvider(config)

    assert provider._api_key == "local"
    assert provider._base_url == OPENAI_COMPATIBLE_DEFAULT_BASE
    mock_openai.assert_called_once()


def test_provider_uses_configured_api_key_and_base_url():
    config = ProviderConfig(
        api_key="token",
        base_url="http://127.0.0.1:30000/v1",
    )

    with patch("providers.openai_compat.AsyncOpenAI"):
        provider = OpenAICompatibleProvider(config)

    assert provider._api_key == "token"
    assert provider._base_url == "http://127.0.0.1:30000/v1"


def test_build_request_body_converts_to_openai_chat_shape():
    req = MockRequest()

    body = build_request_body(req, thinking_enabled=False)

    assert body["model"] == "qwen2.5-coder"
    assert body["messages"][0] == {"role": "system", "content": "You are concise."}
    assert body["messages"][1] == {"role": "user", "content": "Hello"}
    assert body["max_tokens"] == 100
    assert body["temperature"] == 0.2
    assert body["top_p"] == 0.9
    assert body["parallel_tool_calls"] is False


def test_build_request_body_replays_reasoning_only_when_enabled():
    assistant = MockMessage("assistant", "Done", reasoning_content="private reasoning")
    req = MockRequest(messages=[assistant])

    disabled = build_request_body(req, thinking_enabled=False)
    enabled = build_request_body(req, thinking_enabled=True)

    disabled_assistant = next(
        m for m in disabled["messages"] if m["role"] == "assistant"
    )
    enabled_assistant = next(m for m in enabled["messages"] if m["role"] == "assistant")
    assert "reasoning_content" not in disabled_assistant
    assert enabled_assistant["reasoning_content"] == "private reasoning"


@pytest.mark.asyncio
async def test_list_model_ids_uses_openai_models_endpoint():
    config = ProviderConfig(api_key="", base_url=None)

    with patch("providers.openai_compat.AsyncOpenAI") as mock_openai:
        provider = OpenAICompatibleProvider(config)
        mock_openai.return_value.models.list = AsyncMock(
            return_value={"data": [{"id": "qwen2.5-coder"}]}
        )

        model_ids = await provider.list_model_ids()

    assert model_ids == frozenset({"qwen2.5-coder"})
