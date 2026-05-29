"""Pydantic passthrough of Anthropic protocol fields (e.g. `cache_control`)."""

from __future__ import annotations

from api.models.anthropic import (
    ContentBlockServerToolUse,
    ContentBlockText,
    ContentBlockWebSearchToolResult,
    Message,
    MessagesRequest,
    SystemContent,
    Tool,
    normalize_system_messages,
)
from config.constants import ANTHROPIC_DEFAULT_MAX_OUTPUT_TOKENS
from core.anthropic.native_messages_request import (
    build_base_native_anthropic_request_body,
)


def test_cache_control_preserved_on_parsed_user_text_system_and_tool() -> None:
    raw = {
        "model": "m",
        "max_tokens": 20,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "hi",
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        ],
        "system": [
            {
                "type": "text",
                "text": "be brief",
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "tools": [
            {
                "name": "alpha",
                "input_schema": {"type": "object"},
                "cache_control": {"type": "ephemeral"},
            }
        ],
    }
    req = MessagesRequest.model_validate(raw)
    block = req.messages[0].content[0]
    assert isinstance(block, ContentBlockText)
    assert block.model_dump()["cache_control"] == {"type": "ephemeral"}
    s0 = req.system[0] if isinstance(req.system, list) else None
    assert isinstance(s0, SystemContent)
    assert s0.model_dump()["cache_control"] == {"type": "ephemeral"}
    t0 = req.tools[0] if req.tools else None
    assert isinstance(t0, Tool)
    assert t0.model_dump()["cache_control"] == {"type": "ephemeral"}


def test_build_base_native_body_includes_cache_control() -> None:
    req = MessagesRequest(
        model="m",
        max_tokens=20,
        messages=[
            Message(
                role="user",
                content=[
                    ContentBlockText.model_validate(
                        {
                            "type": "text",
                            "text": "x",
                            "cache_control": {"type": "ephemeral"},
                        }
                    )
                ],
            )
        ],
        system=[
            SystemContent.model_validate(
                {
                    "type": "text",
                    "text": "s",
                    "cache_control": {"type": "ephemeral"},
                }
            )
        ],
        tools=[
            Tool.model_validate(
                {
                    "name": "n",
                    "input_schema": {"type": "object"},
                    "cache_control": {"type": "ephemeral"},
                }
            )
        ],
    )
    body = build_base_native_anthropic_request_body(
        req,
        default_max_tokens=ANTHROPIC_DEFAULT_MAX_OUTPUT_TOKENS,
        thinking_enabled=False,
    )
    assert body["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert body["tools"][0]["cache_control"] == {"type": "ephemeral"}


def test_build_base_native_body_drops_unknown_top_level_client_hints() -> None:
    raw = {
        "model": "m",
        "max_tokens": 20,
        "messages": [{"role": "user", "content": "x"}],
        "reasoning_effort": "none",
        "unknown_client_hint": {"mode": "local"},
    }
    req = MessagesRequest.model_validate(raw)
    body = build_base_native_anthropic_request_body(
        req,
        default_max_tokens=ANTHROPIC_DEFAULT_MAX_OUTPUT_TOKENS,
        thinking_enabled=False,
    )
    assert "reasoning_effort" not in body
    assert "unknown_client_hint" not in body


def test_pydantic_discriminator_still_distinguishes_blocks() -> None:
    m = Message.model_validate(
        {
            "role": "user",
            "content": [{"type": "text", "text": "a", "z": 1}],
        }
    )
    b = m.content[0]
    assert isinstance(b, ContentBlockText)
    assert b.model_dump()["z"] == 1


def test_server_tool_assistant_blocks_round_trip_in_native_body() -> None:
    """Local server-tool responses must parse as valid history for a follow-up request."""
    raw = {
        "model": "m",
        "max_tokens": 20,
        "messages": [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "server_tool_use",
                        "id": "srvtoolu_1",
                        "name": "web_search",
                        "input": {"query": "q"},
                    },
                    {
                        "type": "web_search_tool_result",
                        "tool_use_id": "srvtoolu_1",
                        "content": [
                            {
                                "type": "web_search_result",
                                "title": "T",
                                "url": "https://example.com",
                            }
                        ],
                    },
                ],
            }
        ],
        "mcp_servers": [{"type": "url", "url": "https://example.com/mcp"}],
    }
    req = MessagesRequest.model_validate(raw)
    assert len(req.messages) == 1
    blocks = req.messages[0].content
    assert isinstance(blocks, list)
    assert isinstance(blocks[0], ContentBlockServerToolUse)
    assert isinstance(blocks[1], ContentBlockWebSearchToolResult)
    body = build_base_native_anthropic_request_body(
        req,
        default_max_tokens=ANTHROPIC_DEFAULT_MAX_OUTPUT_TOKENS,
        thinking_enabled=False,
    )
    assert body["mcp_servers"][0]["type"] == "url"
    assert body["messages"][0]["content"][0]["type"] == "server_tool_use"
    assert body["messages"][0]["content"][1]["type"] == "web_search_tool_result"


def test_native_body_preserves_context_and_output_config() -> None:
    raw = {
        "model": "m",
        "max_tokens": 20,
        "messages": [{"role": "user", "content": "x"}],
        "context_management": {"edits": [{"type": "clear"}]},
        "output_config": {"some": "hint"},
    }
    req = MessagesRequest.model_validate(raw)
    body = build_base_native_anthropic_request_body(
        req,
        default_max_tokens=ANTHROPIC_DEFAULT_MAX_OUTPUT_TOKENS,
        thinking_enabled=False,
    )
    assert body["context_management"] == raw["context_management"]
    assert body["output_config"] == raw["output_config"]


# =============================================================================
# System Role Message Tests
# =============================================================================


def test_message_accepts_system_role() -> None:
    """Message model should accept role: system for backward compatibility."""
    msg = Message.model_validate({
        "role": "system",
        "content": "You are a helpful assistant.",
    })
    assert msg.role == "system"
    assert msg.content == "You are a helpful assistant."


def test_message_accepts_system_role_with_content_blocks() -> None:
    """Message model should accept role: system with content blocks."""
    msg = Message.model_validate({
        "role": "system",
        "content": [{"type": "text", "text": "You are helpful."}],
    })
    assert msg.role == "system"
    assert isinstance(msg.content, list)
    block = msg.content[0]
    assert isinstance(block, ContentBlockText)
    assert block.text == "You are helpful."


def test_normalize_system_messages_extracts_system_role() -> None:
    """normalize_system_messages should extract role: system messages to system field."""
    raw = {
        "model": "m",
        "max_tokens": 20,
        "messages": [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Hello"},
        ],
    }
    req = MessagesRequest.model_validate(raw)
    normalized = normalize_system_messages(req)

    # System message should be extracted
    assert len(normalized.messages) == 1
    assert normalized.messages[0].role == "user"
    assert normalized.messages[0].content == "Hello"

    # System field should contain the extracted content
    assert normalized.system == "System prompt"


def test_normalize_system_messages_merges_with_existing_system() -> None:
    """normalize_system_messages should merge with existing system field."""
    raw = {
        "model": "m",
        "max_tokens": 20,
        "messages": [
            {"role": "system", "content": "Additional system prompt"},
            {"role": "user", "content": "Hello"},
        ],
        "system": "Original system prompt",
    }
    req = MessagesRequest.model_validate(raw)
    normalized = normalize_system_messages(req)

    assert len(normalized.messages) == 1
    assert normalized.system == "Original system prompt\n\nAdditional system prompt"


def test_normalize_system_messages_handles_multiple_system_messages() -> None:
    """normalize_system_messages should combine multiple role: system messages."""
    raw = {
        "model": "m",
        "max_tokens": 20,
        "messages": [
            {"role": "system", "content": "System 1"},
            {"role": "system", "content": "System 2"},
            {"role": "user", "content": "Hello"},
        ],
    }
    req = MessagesRequest.model_validate(raw)
    normalized = normalize_system_messages(req)

    assert len(normalized.messages) == 1
    assert isinstance(normalized.system, str)
    assert "System 1" in normalized.system
    assert "System 2" in normalized.system


def test_normalize_system_messages_no_op_when_no_system_role() -> None:
    """normalize_system_messages should return unchanged when no role: system."""
    raw = {
        "model": "m",
        "max_tokens": 20,
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ],
    }
    req = MessagesRequest.model_validate(raw)
    normalized = normalize_system_messages(req)

    # Should be the same object (no copy needed)
    assert len(normalized.messages) == 2
    assert normalized.system is None


def test_normalize_system_messages_with_content_blocks() -> None:
    """normalize_system_messages should handle system messages with content blocks."""
    raw = {
        "model": "m",
        "max_tokens": 20,
        "messages": [
            {
                "role": "system",
                "content": [{"type": "text", "text": "System from blocks"}],
            },
            {"role": "user", "content": "Hello"},
        ],
    }
    req = MessagesRequest.model_validate(raw)
    normalized = normalize_system_messages(req)

    assert len(normalized.messages) == 1
    assert normalized.system == "System from blocks"


def test_normalize_system_messages_returns_copy() -> None:
    """normalize_system_messages should return a copy when changes are made."""
    raw = {
        "model": "m",
        "max_tokens": 20,
        "messages": [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Hello"},
        ],
    }
    req = MessagesRequest.model_validate(raw)
    normalized = normalize_system_messages(req)

    # Should be a different object
    assert normalized is not req
    # Original should be unchanged
    assert len(req.messages) == 2
    assert req.system is None