"""Anthropic Messages ⇄ OpenAI chat conversation conversion."""

import json
from typing import Any

from core.anthropic.content import get_block_attr, get_block_type

from .pending import PendingAfterTools
from .reasoning import _clean_reasoning_content, _think_tag_content
from .tool_helpers import (
    _serialize_tool_result_content,
    _tool_input_schema,
)
from .tool_helpers import (
    deferred_post_tool_blocks as _deferred_post_tool_blocks,
)
from .tool_helpers import (
    index_first_tool_use as _index_first_tool_use,
)
from .tool_helpers import (
    iter_tool_uses_in_order as _iter_tool_uses_in_order,
)
from .types import OpenAIConversionError, ReasoningReplayMode
from .validation import _assert_no_forbidden_assistant_block


class AnthropicToOpenAIConverter:
    """Convert Anthropic message format to OpenAI-compatible format."""

    @staticmethod
    def convert_messages(
        messages: list[Any],
        *,
        reasoning_replay: ReasoningReplayMode = ReasoningReplayMode.THINK_TAGS,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        pending: PendingAfterTools | None = None

        for msg in messages:
            role = msg.role
            content = msg.content
            reasoning_content = _clean_reasoning_content(
                getattr(msg, "reasoning_content", None)
            )

            if role == "assistant" and isinstance(content, list):
                if pending is not None and pending.needs_deferred():
                    # Orphan: expected tool result; emit deferred to avoid a stuck session.
                    result.extend(
                        AnthropicToOpenAIConverter._deferred_post_tool_to_messages(
                            pending,
                        )
                    )
                    pending.deferred_emitted = True
                    pending = None

                if (first_i := _index_first_tool_use(content)) is not None:
                    for block in content:
                        if get_block_type(block) == "tool_use":
                            continue
                        _assert_no_forbidden_assistant_block(block)
                    out, new_pending = (
                        AnthropicToOpenAIConverter._convert_assistant_message_with_split(
                            content,
                            first_tool_index=first_i,
                            reasoning_content=reasoning_content,
                            reasoning_replay=reasoning_replay,
                        )
                    )
                    result.extend(out)
                    if new_pending is not None:
                        pending = new_pending
                else:
                    for block in content:
                        _assert_no_forbidden_assistant_block(block)
                    result.extend(
                        AnthropicToOpenAIConverter._convert_assistant_message(
                            content,
                            reasoning_content=reasoning_content,
                            reasoning_replay=reasoning_replay,
                        )
                    )
            elif isinstance(content, str):
                if role == "user" and pending is not None and pending.needs_deferred():
                    result.extend(
                        AnthropicToOpenAIConverter._deferred_post_tool_to_messages(
                            pending
                        )
                    )
                    pending.deferred_emitted = True
                    pending = None
                converted = {"role": role, "content": content}
                if role == "assistant" and reasoning_content:
                    if reasoning_replay == ReasoningReplayMode.REASONING_CONTENT:
                        converted["reasoning_content"] = reasoning_content
                    elif reasoning_replay == ReasoningReplayMode.THINK_TAGS:
                        content_parts = [_think_tag_content(reasoning_content)]
                        if content:
                            content_parts.append(content)
                        converted["content"] = "\n\n".join(content_parts)
                result.append(converted)
            elif isinstance(content, list):
                if role == "user":
                    if pending is not None and pending.needs_deferred():
                        if not pending.remaining_tool_ids:
                            result.extend(
                                AnthropicToOpenAIConverter._deferred_post_tool_to_messages(
                                    pending
                                )
                            )
                            pending.deferred_emitted = True
                            pending = None
                            result.extend(
                                AnthropicToOpenAIConverter._convert_user_message(
                                    content
                                )
                            )
                        else:
                            pieces = AnthropicToOpenAIConverter._convert_user_message_with_injection(
                                content, pending
                            )
                            result.extend(pieces["messages"])
                            if pieces["cleared_pending"]:
                                pending = None
                    else:
                        result.extend(
                            AnthropicToOpenAIConverter._convert_user_message(content)
                        )
            else:
                if role == "user" and pending is not None and pending.needs_deferred():
                    result.extend(
                        AnthropicToOpenAIConverter._deferred_post_tool_to_messages(
                            pending
                        )
                    )
                    pending.deferred_emitted = True
                    pending = None
                result.append({"role": role, "content": str(content)})

        if pending is not None and pending.needs_deferred():
            result.extend(
                AnthropicToOpenAIConverter._deferred_post_tool_to_messages(pending)
            )

        return result

    @staticmethod
    def _convert_assistant_message_with_split(
        content: list[Any],
        *,
        first_tool_index: int,
        reasoning_content: str | None,
        reasoning_replay: ReasoningReplayMode,
    ) -> tuple[list[dict[str, Any]], PendingAfterTools | None]:
        pre = content[:first_tool_index]
        tool_calls = _iter_tool_uses_in_order(content)
        if not tool_calls:
            return (
                AnthropicToOpenAIConverter._convert_assistant_message(
                    content,
                    reasoning_content=reasoning_content,
                    reasoning_replay=reasoning_replay,
                ),
                None,
            )
        deferred_blks = _deferred_post_tool_blocks(
            content, first_tool_index=first_tool_index
        )

        pre_msg: dict[str, Any]
        if not pre:
            pre_msg = {
                "role": "assistant",
                "content": "",
            }
            if reasoning_replay == ReasoningReplayMode.REASONING_CONTENT:
                replay = reasoning_content
                if replay:
                    pre_msg["reasoning_content"] = replay
        else:
            pre_msg = AnthropicToOpenAIConverter._convert_assistant_message(
                pre,
                reasoning_content=reasoning_content,
                reasoning_replay=reasoning_replay,
            )[0]
        pre_msg["tool_calls"] = tool_calls
        if tool_calls and pre_msg.get("content") == " ":
            pre_msg["content"] = ""
        pnd: PendingAfterTools | None = None
        if deferred_blks:
            res_ids: set[str] = set()
            for tc in tool_calls:
                tid = tc.get("id")
                if tid is not None and str(tid).strip() != "":
                    res_ids.add(str(tid))
            pnd = PendingAfterTools(
                remaining_tool_ids=res_ids,
                deferred_blocks=deferred_blks,
                top_level_reasoning=reasoning_content,
                reasoning_replay=reasoning_replay,
            )
        return [pre_msg], pnd

    @staticmethod
    def _convert_assistant_message(
        content: list[Any],
        *,
        reasoning_content: str | None = None,
        reasoning_replay: ReasoningReplayMode = ReasoningReplayMode.THINK_TAGS,
    ) -> list[dict[str, Any]]:
        content_parts: list[str] = []
        thinking_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for block in content:
            block_type = get_block_type(block)
            if block_type == "text":
                content_parts.append(get_block_attr(block, "text", ""))
            elif block_type == "thinking":
                if reasoning_replay == ReasoningReplayMode.DISABLED:
                    continue
                thinking = get_block_attr(block, "thinking", "")
                if reasoning_replay == ReasoningReplayMode.THINK_TAGS:
                    content_parts.append(_think_tag_content(thinking))
                elif reasoning_content is None:
                    thinking_parts.append(thinking)
            elif block_type == "redacted_thinking":
                # Opaque provider continuation data; do not materialize as model-visible text
                # or reasoning_content for OpenAI chat upstreams.
                continue
            elif block_type == "tool_use":
                tool_input = get_block_attr(block, "input", {})
                tool_calls.append(
                    {
                        "id": get_block_attr(block, "id"),
                        "type": "function",
                        "function": {
                            "name": get_block_attr(block, "name"),
                            "arguments": json.dumps(tool_input)
                            if isinstance(tool_input, dict)
                            else str(tool_input),
                        },
                    }
                )
            else:
                _assert_no_forbidden_assistant_block(block)

        content_str = "\n\n".join(content_parts)
        if not content_str and not tool_calls:
            content_str = " "

        msg: dict[str, Any] = {
            "role": "assistant",
            "content": content_str,
        }
        if tool_calls:
            msg["tool_calls"] = tool_calls
        if reasoning_replay == ReasoningReplayMode.REASONING_CONTENT:
            replay_reasoning = reasoning_content or "\n".join(thinking_parts)
            if replay_reasoning:
                msg["reasoning_content"] = replay_reasoning

        return [msg]

    @staticmethod
    def _deferred_post_tool_to_messages(
        pending: PendingAfterTools,
    ) -> list[dict[str, Any]]:
        if not pending.deferred_blocks:
            return []
        return AnthropicToOpenAIConverter._convert_assistant_message(
            pending.deferred_blocks,
            reasoning_content=pending.top_level_reasoning,
            reasoning_replay=pending.reasoning_replay,
        )

    @staticmethod
    def _convert_user_message_with_injection(
        content: list[Any], pending: PendingAfterTools
    ) -> dict[str, Any]:
        """Convert user list blocks, emitting deferred assistant after all tool results."""
        if not pending.needs_deferred() or not pending.remaining_tool_ids:
            return {
                "messages": AnthropicToOpenAIConverter._convert_user_message(content),
                "cleared_pending": False,
            }

        result: list[dict[str, Any]] = []
        text_parts: list[str] = []
        cleared = False

        def flush_text() -> None:
            if text_parts:
                result.append({"role": "user", "content": "\n".join(text_parts)})
                text_parts.clear()

        for block in content:
            block_type = get_block_type(block)
            if block_type == "text":
                text_parts.append(get_block_attr(block, "text", ""))
            elif block_type == "image":
                raise OpenAIConversionError(
                    "User message image blocks are not supported for OpenAI chat "
                    "conversion; use a vision-capable native Anthropic provider or "
                    "extend the converter."
                )
            elif block_type == "tool_result":
                flush_text()
                tool_content = get_block_attr(block, "content", "")
                serialized = _serialize_tool_result_content(tool_content)
                tuid = get_block_attr(block, "tool_use_id")
                tuid_s = str(tuid) if tuid is not None else ""
                result.append(
                    {
                        "role": "tool",
                        "tool_call_id": tuid,
                        "content": serialized if serialized else "",
                    }
                )
                if tuid_s in pending.remaining_tool_ids:
                    pending.remaining_tool_ids.discard(tuid_s)
                if not pending.remaining_tool_ids:
                    result.extend(
                        AnthropicToOpenAIConverter._deferred_post_tool_to_messages(
                            pending
                        )
                    )
                    pending.deferred_emitted = True
                    cleared = True
            else:
                pass

        flush_text()
        return {"messages": result, "cleared_pending": cleared}

    @staticmethod
    def _convert_user_message(content: list[Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        text_parts: list[str] = []

        def flush_text() -> None:
            if text_parts:
                result.append({"role": "user", "content": "\n".join(text_parts)})
                text_parts.clear()

        for block in content:
            block_type = get_block_type(block)

            if block_type == "text":
                text_parts.append(get_block_attr(block, "text", ""))
            elif block_type == "image":
                raise OpenAIConversionError(
                    "User message image blocks are not supported for OpenAI chat "
                    "conversion; use a vision-capable native Anthropic provider or "
                    "extend the converter."
                )
            elif block_type == "tool_result":
                flush_text()
                tool_content = get_block_attr(block, "content", "")
                serialized = _serialize_tool_result_content(tool_content)
                result.append(
                    {
                        "role": "tool",
                        "tool_call_id": get_block_attr(block, "tool_use_id"),
                        "content": serialized if serialized else "",
                    }
                )

        flush_text()
        return result

    @staticmethod
    def convert_tools(tools: list[Any]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": _tool_input_schema(tool),
                },
            }
            for tool in tools
        ]

    @staticmethod
    def convert_tool_choice(tool_choice: Any) -> Any:
        if not isinstance(tool_choice, dict):
            return tool_choice

        choice_type = tool_choice.get("type")
        if choice_type == "tool":
            name = tool_choice.get("name")
            if name:
                return {"type": "function", "function": {"name": name}}
        if choice_type == "any":
            return "required"
        if choice_type in {"auto", "none", "required"}:
            return choice_type
        if choice_type == "function" and isinstance(tool_choice.get("function"), dict):
            return tool_choice

        return tool_choice

    @staticmethod
    def convert_system_prompt(system: Any) -> dict[str, str] | None:
        if isinstance(system, str):
            return {"role": "system", "content": system}
        if isinstance(system, list):
            text_parts = [
                get_block_attr(block, "text", "")
                for block in system
                if get_block_type(block) == "text"
            ]
            if text_parts:
                return {"role": "system", "content": "\n\n".join(text_parts).strip()}
        return None
