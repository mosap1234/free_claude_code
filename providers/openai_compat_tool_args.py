"""Tool-argument buffering and aliasing for OpenAI-compatible streaming."""

import json
import uuid
from collections.abc import Iterator
from typing import Any

from core.anthropic import SSEBuilder


def restore_aliased_tool_arguments(
    argument_json: str, aliases: dict[str, str]
) -> str | None:
    try:
        parsed = json.loads(argument_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return argument_json
    restored = restore_aliased_tool_argument_value(parsed, aliases)
    return json.dumps(restored)


def restore_aliased_tool_argument_value(value: Any, aliases: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {
            aliases.get(key, key): restore_aliased_tool_argument_value(item, aliases)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [restore_aliased_tool_argument_value(item, aliases) for item in value]
    return value


def emit_tool_arg_delta(
    sse: SSEBuilder,
    tc_index: int,
    args: str,
    *,
    tool_argument_aliases: dict[str, dict[str, str]] | None = None,
    tool_argument_alias_buffers: dict[int, str] | None = None,
) -> Iterator[str]:
    """Emit one argument fragment for a started tool block (Task buffer or raw JSON)."""
    if not args:
        return
    state = sse.blocks.tool_states.get(tc_index)
    if state is None:
        return
    if state.name == "Task":
        parsed = sse.blocks.buffer_task_args(tc_index, args)
        if parsed is not None:
            yield sse.emit_tool_delta(tc_index, json.dumps(parsed))
        return
    aliases = tool_argument_aliases.get(state.name, {}) if tool_argument_aliases else {}
    if aliases:
        if tool_argument_alias_buffers is None:
            restored = restore_aliased_tool_arguments(args, aliases)
            if restored is not None:
                yield sse.emit_tool_delta(tc_index, restored)
            return

        buffered_args = tool_argument_alias_buffers.get(tc_index, "") + args
        restored = restore_aliased_tool_arguments(buffered_args, aliases)
        if restored is None:
            tool_argument_alias_buffers[tc_index] = buffered_args
            return
        tool_argument_alias_buffers.pop(tc_index, None)
        yield sse.emit_tool_delta(tc_index, restored)
        return
    yield sse.emit_tool_delta(tc_index, args)


def process_tool_call_delta(
    tc: dict,
    sse: SSEBuilder,
    *,
    tool_argument_aliases: dict[str, dict[str, str]] | None = None,
    tool_argument_alias_buffers: dict[int, str] | None = None,
) -> Iterator[str]:
    """Process a single tool call delta and yield SSE events."""
    tc_index = tc.get("index", 0)
    if tc_index < 0:
        tc_index = len(sse.blocks.tool_states)

    fn_delta = tc.get("function", {})
    incoming_name = fn_delta.get("name")
    arguments = fn_delta.get("arguments", "") or ""

    if tc.get("id") is not None:
        sse.blocks.set_stream_tool_id(tc_index, tc.get("id"))

    if incoming_name is not None:
        sse.blocks.register_tool_name(tc_index, incoming_name)

    state = sse.blocks.tool_states.get(tc_index)
    resolved_id = (state.tool_id if state and state.tool_id else None) or tc.get("id")
    resolved_name = (state.name if state else "") or ""

    if not state or not state.started:
        name_ok = bool((resolved_name or "").strip())
        if name_ok:
            tool_id = str(resolved_id) if resolved_id else f"tool_{uuid.uuid4()}"
            display_name = (resolved_name or "").strip() or "tool_call"
            yield sse.start_tool_block(tc_index, tool_id, display_name)
            state = sse.blocks.tool_states[tc_index]
            if state.pre_start_args:
                pre = state.pre_start_args
                state.pre_start_args = ""
                yield from emit_tool_arg_delta(
                    sse,
                    tc_index,
                    pre,
                    tool_argument_aliases=tool_argument_aliases,
                    tool_argument_alias_buffers=tool_argument_alias_buffers,
                )

    state = sse.blocks.tool_states.get(tc_index)
    if not arguments:
        return
    if state is None or not state.started:
        state = sse.blocks.ensure_tool_state(tc_index)
        if not (resolved_name or "").strip():
            state.pre_start_args += arguments
            return

    yield from emit_tool_arg_delta(
        sse,
        tc_index,
        arguments,
        tool_argument_aliases=tool_argument_aliases,
        tool_argument_alias_buffers=tool_argument_alias_buffers,
    )


def flush_tool_argument_alias_buffers(
    sse: SSEBuilder,
    tool_argument_aliases: dict[str, dict[str, str]],
    tool_argument_alias_buffers: dict[int, str],
) -> Iterator[str]:
    """Emit remaining aliased tool args without losing data on malformed JSON."""
    for tool_index, buffered_args in list(tool_argument_alias_buffers.items()):
        if not buffered_args:
            tool_argument_alias_buffers.pop(tool_index, None)
            continue
        state = sse.blocks.tool_states.get(tool_index)
        if state is None or state.name == "Task":
            continue
        aliases = tool_argument_aliases.get(state.name, {})
        if not aliases:
            continue
        restored = restore_aliased_tool_arguments(buffered_args, aliases)
        yield sse.emit_tool_delta(
            tool_index,
            restored if restored is not None else buffered_args,
        )
        tool_argument_alias_buffers.pop(tool_index, None)
