"""Request builder for OpenAI provider."""

from typing import Any

from core.anthropic import ReasoningReplayMode, build_base_request_body
from core.anthropic.conversion import OpenAIConversionError
from providers.exceptions import InvalidRequestError


def build_request_body(request_data: Any) -> dict:
    try:
        body = build_base_request_body(
            request_data,
            reasoning_replay=ReasoningReplayMode.DISABLED,
        )
    except OpenAIConversionError as exc:
        raise InvalidRequestError(str(exc)) from exc

    if "max_tokens" in body:
        body["max_completion_tokens"] = body.pop("max_tokens")

    return body
