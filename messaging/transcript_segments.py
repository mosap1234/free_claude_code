"""Segment types + render contexts for messenger transcripts."""

import json
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


def _safe_json_dumps(obj: Any) -> str:
    try:
        return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(obj)


@dataclass
class Segment(ABC):
    kind: str

    @abstractmethod
    def render(self, ctx: RenderCtx) -> str: ...


@dataclass
class ThinkingSegment(Segment):
    def __init__(self) -> None:
        super().__init__(kind="thinking")
        self._parts: list[str] = []

    def append(self, t: str) -> None:
        if t:
            self._parts.append(t)

    @property
    def text(self) -> str:
        return "".join(self._parts)

    def render(self, ctx: RenderCtx) -> str:
        raw = self.text or ""
        if ctx.thinking_tail_max is not None and len(raw) > ctx.thinking_tail_max:
            raw = "..." + raw[-(ctx.thinking_tail_max - 3) :]
        inner = ctx.escape_code(raw)
        return f"\U0001f4ad {ctx.bold('Thinking')}\n```\n{inner}\n```"


@dataclass
class TextSegment(Segment):
    def __init__(self) -> None:
        super().__init__(kind="text")
        self._parts: list[str] = []

    def append(self, t: str) -> None:
        if t:
            self._parts.append(t)

    @property
    def text(self) -> str:
        return "".join(self._parts)

    def render(self, ctx: RenderCtx) -> str:
        raw = self.text or ""
        if ctx.text_tail_max is not None and len(raw) > ctx.text_tail_max:
            raw = "..." + raw[-(ctx.text_tail_max - 3) :]
        return ctx.render_markdown(raw)


@dataclass
class ToolCallSegment(Segment):
    tool_use_id: str
    name: str
    closed: bool = False
    indent_level: int = 0

    def __init__(self, tool_use_id: str, name: str, *, indent_level: int = 0) -> None:
        super().__init__(kind="tool_call")
        self.tool_use_id = str(tool_use_id or "")
        self.name = str(name or "tool")
        self.indent_level = max(0, int(indent_level))

    def render(self, ctx: RenderCtx) -> str:
        name = ctx.code_inline(self.name)
        # Per UX requirement: do not display tool args/results, only the tool call.
        prefix = "  " * self.indent_level
        return f"{prefix}\U0001f6e0 {ctx.bold('Tool call:')} {name}"


@dataclass
class ToolResultSegment(Segment):
    tool_use_id: str
    name: str | None
    content_text: str
    is_error: bool = False

    def __init__(
        self,
        tool_use_id: str,
        content: Any,
        *,
        name: str | None = None,
        is_error: bool = False,
    ) -> None:
        super().__init__(kind="tool_result")
        self.tool_use_id = str(tool_use_id or "")
        self.name = str(name) if name is not None else None
        self.is_error = bool(is_error)
        if isinstance(content, str):
            self.content_text = content
        else:
            self.content_text = _safe_json_dumps(content)

    def render(self, ctx: RenderCtx) -> str:
        raw = self.content_text or ""
        if ctx.tool_output_tail_max is not None and len(raw) > ctx.tool_output_tail_max:
            raw = "..." + raw[-(ctx.tool_output_tail_max - 3) :]
        inner = ctx.escape_code(raw)
        label = "Tool error:" if self.is_error else "Tool result:"
        maybe_name = f" {ctx.code_inline(self.name)}" if self.name else ""
        return f"\U0001f4e4 {ctx.bold(label)}{maybe_name}\n```\n{inner}\n```"


@dataclass
class SubagentSegment(Segment):
    description: str
    tool_calls: int = 0
    tools_used: set[str] = field(default_factory=set)
    current_tool: ToolCallSegment | None = None

    def __init__(self, description: str) -> None:
        super().__init__(kind="subagent")
        self.description = str(description or "Subagent")
        self.tool_calls = 0
        self.tools_used = set()
        self.current_tool = None

    def set_current_tool_call(self, tool_use_id: str, name: str) -> ToolCallSegment:
        tool_use_id = str(tool_use_id or "")
        name = str(name or "tool")
        self.tools_used.add(name)
        self.tool_calls += 1
        self.current_tool = ToolCallSegment(tool_use_id, name, indent_level=1)
        return self.current_tool

    def render(self, ctx: RenderCtx) -> str:
        inner_prefix = "  "

        lines: list[str] = [
            f"\U0001f916 {ctx.bold('Subagent:')} {ctx.code_inline(self.description)}"
        ]

        if self.current_tool is not None:
            try:
                rendered = self.current_tool.render(ctx)
            except Exception:
                rendered = ""
            if rendered:
                lines.append(rendered)

        tools_used = sorted(self.tools_used)
        tools_set_raw = "{{{}}}".format(", ".join(tools_used)) if tools_used else "{}"

        # Keep braces inside a code entity so MarkdownV2 doesn't require escaping them.
        lines.append(
            f"{inner_prefix}{ctx.bold('Tools used:')} {ctx.code_inline(tools_set_raw)}"
        )
        lines.append(
            f"{inner_prefix}{ctx.bold('Tool calls:')} {ctx.code_inline(str(self.tool_calls))}"
        )
        return "\n".join(lines)


@dataclass
class ErrorSegment(Segment):
    message: str

    def __init__(self, message: str) -> None:
        super().__init__(kind="error")
        self.message = str(message or "Unknown error")

    def render(self, ctx: RenderCtx) -> str:
        return f"\u26a0\ufe0f {ctx.bold('Error:')} {ctx.code_inline(self.message)}"


@dataclass
class RenderCtx:
    bold: Callable[[str], str]
    code_inline: Callable[[str], str]
    escape_code: Callable[[str], str]
    escape_text: Callable[[str], str]
    render_markdown: Callable[[str], str]

    thinking_tail_max: int | None = 1000
    tool_input_tail_max: int | None = 1200
    tool_output_tail_max: int | None = 1600
    text_tail_max: int | None = 2000
