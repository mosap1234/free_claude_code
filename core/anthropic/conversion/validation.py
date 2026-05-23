"""OpenAI conversion validation helpers."""

from typing import Any

from pydantic import BaseModel

from core.anthropic.content import get_block_type

from .types import OpenAIConversionError


def _openai_reject_native_only_top_level_fields(request_data: Any) -> None:
    """OpenAI chat providers may only convert known top-level request fields.

    First-class model fields (e.g. ``context_management``) are not forwarded to
    the OpenAI API but are allowed so clients do not hit spurious 400s.
    Unknown extra keys (``__pydantic_extra__``) are still rejected.
    """
    if not isinstance(request_data, BaseModel):
        return
    extra = getattr(request_data, "__pydantic_extra__", None)
    if not extra:
        return
    raise OpenAIConversionError(
        "OpenAI chat conversion does not support these top-level request fields: "
        f"{sorted(str(k) for k in extra)}. Use a native Anthropic transport provider."
    )


def _assert_no_forbidden_assistant_block(block: Any) -> None:
    block_type = get_block_type(block)
    if block_type == "image":
        raise OpenAIConversionError(
            "Assistant image blocks are not supported for OpenAI chat conversion."
        )
    if block_type in (
        "server_tool_use",
        "web_search_tool_result",
        "web_fetch_tool_result",
    ):
        raise OpenAIConversionError(
            "OpenAI chat conversion does not support Anthropic server tool blocks "
            f"({block_type!r} in an assistant message). Use a native Anthropic transport provider."
        )
