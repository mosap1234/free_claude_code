"""Heuristic SSE helpers for translating OpenAI tool_use into Anthropic SSE blocks."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from core.anthropic import SSEBuilder


def iter_heuristic_tool_use_sse(
    sse: SSEBuilder, tool_use: dict[str, Any]
) -> Iterator[str]:
    """Emit SSE for one heuristic tool_use block (closes open text/thinking first)."""
    if tool_use.get("name") == "Task" and isinstance(tool_use.get("input"), dict):
        task_input = tool_use["input"]
        if task_input.get("run_in_background") is not False:
            task_input["run_in_background"] = False
    yield from sse.close_content_blocks()
    block_idx = sse.blocks.allocate_index()
    yield sse.content_block_start(
        block_idx,
        "tool_use",
        id=tool_use["id"],
        name=tool_use["name"],
    )
    yield sse.content_block_delta(
        block_idx,
        "input_json_delta",
        json.dumps(tool_use["input"]),
    )
    yield sse.content_block_stop(block_idx)
