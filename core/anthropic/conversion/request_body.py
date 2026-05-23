"""Build OpenAI-format request payloads from Anthropic-shaped requests."""

from typing import Any

from core.anthropic.utils import set_if_not_none

from .converter import AnthropicToOpenAIConverter
from .types import ReasoningReplayMode
from .validation import _openai_reject_native_only_top_level_fields


def build_base_request_body(
    request_data: Any,
    *,
    default_max_tokens: int | None = None,
    reasoning_replay: ReasoningReplayMode = ReasoningReplayMode.THINK_TAGS,
) -> dict[str, Any]:
    """Build the common parts of an OpenAI-format request body."""
    _openai_reject_native_only_top_level_fields(request_data)
    messages = AnthropicToOpenAIConverter.convert_messages(
        request_data.messages,
        reasoning_replay=reasoning_replay,
    )

    system = getattr(request_data, "system", None)
    if system:
        system_msg = AnthropicToOpenAIConverter.convert_system_prompt(system)
        if system_msg:
            messages.insert(0, system_msg)

    body: dict[str, Any] = {"model": request_data.model, "messages": messages}

    max_tokens = getattr(request_data, "max_tokens", None)
    set_if_not_none(body, "max_tokens", max_tokens or default_max_tokens)
    set_if_not_none(body, "temperature", getattr(request_data, "temperature", None))
    set_if_not_none(body, "top_p", getattr(request_data, "top_p", None))

    stop_sequences = getattr(request_data, "stop_sequences", None)
    if stop_sequences:
        body["stop"] = stop_sequences

    tools = getattr(request_data, "tools", None)
    if tools:
        body["tools"] = AnthropicToOpenAIConverter.convert_tools(tools)
    tool_choice = getattr(request_data, "tool_choice", None)
    if tool_choice:
        body["tool_choice"] = AnthropicToOpenAIConverter.convert_tool_choice(
            tool_choice
        )

    return body
