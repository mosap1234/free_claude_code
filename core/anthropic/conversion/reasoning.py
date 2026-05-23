"""Reasoning / thinking text normalization for Anthropic ⇄ OpenAI conversion."""

from __future__ import annotations

from typing import Any


def _clean_reasoning_content(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value if value else None


def _think_tag_content(reasoning: str) -> str:
    return f"<think>\n{reasoning}\n</think>"
