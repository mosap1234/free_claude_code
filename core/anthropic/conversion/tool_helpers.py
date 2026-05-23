"""Tool block helpers for Anthropic ⇄ OpenAI conversion."""

import json
from typing import Any

from core.anthropic.content import get_block_attr, get_block_type


def _tool_name(tool: Any) -> str:
    return str(getattr(tool, "name", "") or "")


def _tool_input_schema(tool: Any) -> dict[str, Any]:
    schema = getattr(tool, "input_schema", None)
    if isinstance(schema, dict):
        return schema
    return {"type": "object", "properties": {}}


def _serialize_tool_result_content(tool_content: Any) -> str:
    """Serialize tool_result content for OpenAI ``role: tool`` messages (stable JSON for structured values)."""
    if tool_content is None:
        return ""
    if isinstance(tool_content, str):
        return tool_content
    if isinstance(tool_content, dict):
        return json.dumps(tool_content, ensure_ascii=False)
    if isinstance(tool_content, list):
        parts: list[str] = []
        for item in tool_content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            elif isinstance(item, dict):
                parts.append(json.dumps(item, ensure_ascii=False))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(tool_content)


def index_first_tool_use(blocks: list[Any]) -> int | None:
    for i, block in enumerate(blocks):
        if get_block_type(block) == "tool_use":
            return i
    return None


def iter_tool_uses_in_order(blocks: list[Any]) -> list[dict[str, Any]]:
    tool_calls: list[dict[str, Any]] = []
    for block in blocks:
        if get_block_type(block) == "tool_use":
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
    return tool_calls


def deferred_post_tool_blocks(
    content: list[Any], *, first_tool_index: int
) -> list[Any]:
    return [
        b
        for i, b in enumerate(content)
        if i > first_tool_index and get_block_type(b) != "tool_use"
    ]
