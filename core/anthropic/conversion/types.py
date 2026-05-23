"""Types for Anthropic ⇄ OpenAI message conversion."""

from enum import StrEnum


class OpenAIConversionError(Exception):
    """Raised when Anthropic content cannot be converted to OpenAI chat without data loss."""


class ReasoningReplayMode(StrEnum):
    """How assistant reasoning history is replayed to OpenAI-compatible providers."""

    DISABLED = "disabled"
    THINK_TAGS = "think_tags"
    REASONING_CONTENT = "reasoning_content"
