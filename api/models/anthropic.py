"""Pydantic models for Anthropic-compatible requests."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, overload

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Content Block Types
# =============================================================================
class Role(StrEnum):
    user = "user"
    assistant = "assistant"
    system = "system"


class _AnthropicBlockBase(BaseModel):
    """Pass through provider fields (e.g. `cache_control`) for native transports."""

    model_config = ConfigDict(extra="allow")


class ContentBlockText(_AnthropicBlockBase):
    type: Literal["text"]
    text: str


class ContentBlockImage(_AnthropicBlockBase):
    type: Literal["image"]
    source: dict[str, Any]


class ContentBlockDocument(_AnthropicBlockBase):
    """Anthropic document block (e.g. PDF files via the Files API)."""

    type: Literal["document"]
    source: dict[str, Any]


class ContentBlockToolUse(_AnthropicBlockBase):
    type: Literal["tool_use"]
    id: str
    name: str
    input: dict[str, Any]


class ContentBlockToolResult(_AnthropicBlockBase):
    type: Literal["tool_result"]
    tool_use_id: str
    content: str | list[Any] | dict[str, Any]


class ContentBlockThinking(_AnthropicBlockBase):
    type: Literal["thinking"]
    thinking: str
    signature: str | None = None


class ContentBlockRedactedThinking(_AnthropicBlockBase):
    type: Literal["redacted_thinking"]
    data: str


class ContentBlockServerToolUse(_AnthropicBlockBase):
    """Anthropic server-side tool invocation (e.g. `web_search`, `web_fetch`)."""

    type: Literal["server_tool_use"]
    id: str
    name: str
    input: dict[str, Any]


class ContentBlockWebSearchToolResult(_AnthropicBlockBase):
    type: Literal["web_search_tool_result"]
    tool_use_id: str
    content: Any


class ContentBlockWebFetchToolResult(_AnthropicBlockBase):
    type: Literal["web_fetch_tool_result"]
    tool_use_id: str
    content: Any


class SystemContent(_AnthropicBlockBase):
    type: Literal["text"]
    text: str


# =============================================================================
# Message Types
# =============================================================================
class Message(BaseModel):
    """Message with optional system role for backward compatibility.

    Standard Anthropic API uses role: user|assistant. Some clients incorrectly
    send role: system in the messages array. We accept it here and handle it
    by extracting to the system field during request processing.
    """

    role: Literal["user", "assistant", "system"]
    content: (
        str
        | list[
            ContentBlockText
            | ContentBlockImage
            | ContentBlockDocument
            | ContentBlockToolUse
            | ContentBlockToolResult
            | ContentBlockThinking
            | ContentBlockRedactedThinking
            | ContentBlockServerToolUse
            | ContentBlockWebSearchToolResult
            | ContentBlockWebFetchToolResult
        ]
    )
    reasoning_content: str | None = None


class Tool(_AnthropicBlockBase):
    name: str
    # Anthropic server tools (e.g. web_search beta tools) include a `type` and
    # may omit `input_schema` because the provider owns the schema.
    type: str | None = None
    description: str | None = None
    input_schema: dict[str, Any] | None = None


class ThinkingConfig(BaseModel):
    enabled: bool | None = True
    type: str | None = None
    budget_tokens: int | None = None


# =============================================================================
# Request Models
# =============================================================================
class MessagesRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str
    # Internal routing / debug: accepted on parse but not serialized to providers.
    original_model: str | None = Field(default=None, exclude=True)
    resolved_provider_model: str | None = Field(default=None, exclude=True)
    max_tokens: int | None = None
    messages: list[Message]
    system: str | list[SystemContent] | None = None
    stop_sequences: list[str] | None = None
    stream: bool | None = True
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    metadata: dict[str, Any] | None = None
    tools: list[Tool] | None = None
    tool_choice: dict[str, Any] | None = None
    thinking: ThinkingConfig | None = None
    # Native Anthropic / SDK client hints: ignored (not forwarded) for OpenAI Chat conversion.
    context_management: dict[str, Any] | None = None
    output_config: dict[str, Any] | None = None
    mcp_servers: list[dict[str, Any]] | None = None
    extra_body: dict[str, Any] | None = None
    # Beta feature flags sent by Claude Code as a body field; accepted but never forwarded.
    betas: list[str] | None = Field(default=None, exclude=True)


class TokenCountRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str
    original_model: str | None = Field(default=None, exclude=True)
    resolved_provider_model: str | None = Field(default=None, exclude=True)
    messages: list[Message]
    system: str | list[SystemContent] | None = None
    tools: list[Tool] | None = None
    thinking: ThinkingConfig | None = None
    tool_choice: dict[str, Any] | None = None
    context_management: dict[str, Any] | None = None
    output_config: dict[str, Any] | None = None
    mcp_servers: list[dict[str, Any]] | None = None
    betas: list[str] | None = Field(default=None, exclude=True)


# =============================================================================
# Request Helpers
# =============================================================================


def _extract_text_from_content_block(block: Any) -> str:
    """Extract text from a content block or dict."""
    if isinstance(block, dict):
        return block.get("text", "")
    if hasattr(block, "text"):
        return str(block.text)
    return ""


def _extract_text_from_message_content(content: Any) -> list[str]:
    """Extract text parts from message content."""
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        return [_extract_text_from_content_block(block) for block in content]
    return []


def _merge_system_content(
    existing_system: str | list[SystemContent] | None,
    combined_system: str,
) -> str | list[SystemContent]:
    """Merge new system content with existing system field."""
    if existing_system is None:
        return combined_system
    if isinstance(existing_system, str):
        return f"{existing_system}\n\n{combined_system}"
    # existing_system is list[SystemContent]
    existing_text = "\n".join(_extract_text_from_content_block(block) for block in existing_system)
    return f"{existing_text}\n\n{combined_system}"


@overload
def normalize_system_messages(request: MessagesRequest) -> MessagesRequest: ...


@overload
def normalize_system_messages(request: TokenCountRequest) -> TokenCountRequest: ...


def normalize_system_messages(request: MessagesRequest | TokenCountRequest) -> MessagesRequest | TokenCountRequest:
    """Extract role: system messages from the messages array to the system field.

    Some clients incorrectly send system prompts as messages with role: system
    instead of using the dedicated system field. This function normalizes such
    requests by moving system messages to the system field.

    Returns a copy of the request with system messages extracted.
    """
    system_messages = [msg for msg in request.messages if msg.role == "system"]
    non_system_messages = [msg for msg in request.messages if msg.role != "system"]

    if not system_messages:
        return request

    # Combine system message contents
    system_parts: list[str] = []
    for msg in system_messages:
        system_parts.extend(_extract_text_from_message_content(msg.content))

    combined_system = "\n\n".join(system_parts).strip()
    new_system = _merge_system_content(request.system, combined_system)

    return request.model_copy(
        update={
            "messages": non_system_messages,
            "system": new_system,
        },
        deep=True,
    )