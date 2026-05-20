"""AgentRouter provider implementation (native Anthropic-compatible Messages)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import httpx

from core.anthropic.emitted_sse_tracker import EmittedNativeSseTracker
from core.anthropic.sse import format_sse_event
from providers.anthropic_messages import AnthropicMessagesTransport
from providers.base import ProviderConfig
from providers.defaults import AGENTROUTER_DEFAULT_BASE
from providers.model_listing import ProviderModelInfo, model_infos_from_ids

_ANTHROPIC_VERSION = "2023-06-01"
_CLAUDE_CODE_BETAS = (
    "claude-code-20250219,"
    "interleaved-thinking-2025-05-14,"
    "context-management-2025-06-27,"
    "prompt-caching-scope-2026-01-05,"
    "advisor-tool-2026-03-01,"
    "effort-2025-11-24"
)
_CLAUDE_CODE_BILLING_MARKER = (
    "x-anthropic-billing-header: "
    "cc_version=2.1.145.560; cc_entrypoint=sdk-cli; cch=00000;"
)
_SUPPORTED_MODEL_INFOS = model_infos_from_ids(
    {"deepseek-v4-pro"}, supports_thinking=True
)


class AgentRouterProvider(AnthropicMessagesTransport):
    """AgentRouter using ``https://agentrouter.org/v1/messages``."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="AGENTROUTER",
            default_base_url=AGENTROUTER_DEFAULT_BASE,
        )
        self._session_id = str(uuid4())

    def _request_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "claude-cli/2.1.145 (external, sdk-cli)",
            "X-Claude-Code-Session-Id": self._session_id,
            "X-Stainless-Arch": "x64",
            "X-Stainless-Lang": "js",
            "X-Stainless-OS": "Windows",
            "X-Stainless-Package-Version": "0.93.0",
            "X-Stainless-Retry-Count": "0",
            "X-Stainless-Runtime": "node",
            "X-Stainless-Runtime-Version": "v24.3.0",
            "X-Stainless-Timeout": str(int(self._config.http_read_timeout)),
            "anthropic-beta": _CLAUDE_CODE_BETAS,
            "anthropic-dangerous-direct-browser-access": "true",
            "anthropic-version": _ANTHROPIC_VERSION,
            "x-api-key": self._api_key,
            "x-app": "cli",
        }

    def _model_list_headers(self) -> dict[str, str]:
        return self._request_headers()

    async def list_model_ids(self) -> frozenset[str]:
        """AgentRouter does not expose a usable ``/models`` endpoint for this flow."""
        return frozenset(info.model_id for info in _SUPPORTED_MODEL_INFOS)

    async def list_model_infos(self) -> frozenset[ProviderModelInfo]:
        """Return the verified AgentRouter model ids supported by this provider."""
        return _SUPPORTED_MODEL_INFOS

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        body = super()._build_request_body(request, thinking_enabled=thinking_enabled)
        _ensure_billing_system_marker(body)
        return body

    async def _send_stream_request(self, body: dict) -> httpx.Response:
        """AgentRouter accepts the Claude Code beta Messages route shape."""
        request = self._client.build_request(
            "POST",
            "/messages?beta=true",
            json=body,
            headers=self._request_headers(),
        )
        return await self._client.send(request, stream=True)

    async def _iter_stream_chunks(
        self,
        response: httpx.Response,
        *,
        state: Any,
        thinking_enabled: bool,
    ) -> AsyncIterator[str]:
        tracker = EmittedNativeSseTracker()
        saw_message_stop = False
        async for chunk in super()._iter_stream_chunks(
            response,
            state=state,
            thinking_enabled=thinking_enabled,
        ):
            if "event: message_stop" in chunk:
                saw_message_stop = True
            tracker.feed(chunk)
            yield chunk

        if saw_message_stop:
            return
        for event in tracker.iter_close_unclosed_blocks():
            yield event
        yield _message_delta_tail()
        yield format_sse_event("message_stop", {"type": "message_stop"})


def _ensure_billing_system_marker(body: dict[str, Any]) -> None:
    system = body.get("system")
    if _contains_billing_marker(system):
        return

    marker_block = {"type": "text", "text": _CLAUDE_CODE_BILLING_MARKER}
    if system is None:
        body["system"] = [marker_block]
        return
    if isinstance(system, list):
        body["system"] = [marker_block, *system]
        return
    if isinstance(system, str):
        body["system"] = [marker_block, {"type": "text", "text": system}]
        return
    body["system"] = [marker_block, {"type": "text", "text": str(system)}]


def _message_delta_tail() -> str:
    return format_sse_event(
        "message_delta",
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": {"input_tokens": 0, "output_tokens": 0},
        },
    )


def _contains_billing_marker(system: Any) -> bool:
    if isinstance(system, str):
        return "x-anthropic-billing-header:" in system
    if not isinstance(system, list):
        return False
    for block in system:
        if isinstance(block, dict):
            text = block.get("text")
        else:
            text = getattr(block, "text", None)
        if isinstance(text, str) and "x-anthropic-billing-header:" in text:
            return True
    return False
