"""Deferred assistant segments after ``tool_calls``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .types import ReasoningReplayMode


@dataclass
class PendingAfterTools:
    """Assistant content that appears after ``tool_use`` in an Anthropic message.

    OpenAI ``chat.completions`` cannot place assistant text after ``tool_calls`` in the
    same message, so it is deferred until the corresponding ``role: tool`` results have
    been replayed in order.
    """

    # Tool use IDs still missing a ``role: tool`` result before post-tool text may be replayed.
    remaining_tool_ids: set[str] = field(default_factory=set)
    deferred_blocks: list[Any] = field(default_factory=list)
    top_level_reasoning: str | None = None
    reasoning_replay: ReasoningReplayMode = ReasoningReplayMode.THINK_TAGS
    # True after deferred assistant text has been added to the OpenAI transcript.
    deferred_emitted: bool = False

    def needs_deferred(self) -> bool:
        return bool(self.deferred_blocks) and not self.deferred_emitted
