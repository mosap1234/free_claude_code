"""Sequential pipeline for :meth:`~api.services.ClaudeProxyService.create_message`."""

import uuid
from collections.abc import Callable
from typing import Any

from fastapi.responses import StreamingResponse
from loguru import logger

from config.provider_catalog import provider_ids_for_transport
from config.settings import Settings
from core.anthropic import get_token_count
from core.anthropic.sse import ANTHROPIC_SSE_RESPONSE_HEADERS
from core.trace import api_messages_request_snapshot, trace_event, traced_async_stream
from providers.base import BaseProvider
from providers.exceptions import InvalidRequestError

from .model_router import ModelRouter, RoutedMessagesRequest
from .models.anthropic import MessagesRequest
from .optimization_handlers import try_optimizations
from .web_tools.egress import WebFetchEgressPolicy
from .web_tools.request import (
    is_web_server_tool_request,
    openai_chat_upstream_server_tool_error,
)
from .web_tools.streaming import stream_web_server_tool_response

TokenCounter = Callable[[list[Any], str | list[Any] | None, list[Any] | None], int]
ProviderGetter = Callable[[str], BaseProvider]

OPENAI_CHAT_UPSTREAM_IDS = provider_ids_for_transport("openai_chat")


def anthropic_sse_streaming_response(
    body: Any,
) -> StreamingResponse:
    """Return a :class:`StreamingResponse` for Anthropic-style SSE streams."""
    return StreamingResponse(
        body,
        media_type="text/event-stream",
        headers=ANTHROPIC_SSE_RESPONSE_HEADERS,
    )


def require_messages_non_empty(messages: list[Any]) -> None:
    if not messages:
        raise InvalidRequestError("messages cannot be empty")


def _enforce_openai_chat_server_tools_guard(
    routed: RoutedMessagesRequest, settings: Settings
) -> None:
    if routed.resolved.provider_id not in OPENAI_CHAT_UPSTREAM_IDS:
        return
    tool_err = openai_chat_upstream_server_tool_error(
        routed.request,
        web_tools_enabled=settings.enable_web_server_tools,
    )
    if tool_err is not None:
        raise InvalidRequestError(tool_err)


def _try_web_server_tool_branch(
    routed: RoutedMessagesRequest,
    *,
    settings: Settings,
    token_counter: TokenCounter,
) -> StreamingResponse | None:
    if not (
        settings.enable_web_server_tools and is_web_server_tool_request(routed.request)
    ):
        return None

    input_tokens = token_counter(
        routed.request.messages, routed.request.system, routed.request.tools
    )
    trace_event(
        stage="routing",
        event="api.optimization.web_server_tool",
        source="api",
        model=routed.request.model,
    )
    egress = WebFetchEgressPolicy(
        allow_private_network_targets=settings.web_fetch_allow_private_networks,
        allowed_schemes=settings.web_fetch_allowed_scheme_set(),
    )
    return anthropic_sse_streaming_response(
        stream_web_server_tool_response(
            routed.request,
            input_tokens=input_tokens,
            web_fetch_egress=egress,
            verbose_client_errors=settings.log_api_error_tracebacks,
        ),
    )


def _try_optimization_branch(
    routed: RoutedMessagesRequest, settings: Settings
) -> object | None:
    optimized = try_optimizations(routed.request, settings)
    if optimized is None:
        return None
    trace_event(
        stage="routing",
        event="api.optimization.short_circuit",
        source="api",
        model=routed.request.model,
    )
    return optimized


def _stream_provider_branch(
    routed: RoutedMessagesRequest,
    *,
    settings: Settings,
    provider_getter: ProviderGetter,
    token_counter: TokenCounter,
) -> StreamingResponse:
    logger.debug("No optimization matched, routing to provider")

    provider = provider_getter(routed.resolved.provider_id)
    provider.preflight_stream(
        routed.request,
        thinking_enabled=routed.resolved.thinking_enabled,
    )

    trace_event(
        stage="routing",
        event="api.route.resolved",
        source="api",
        provider_id=routed.resolved.provider_id,
        provider_model=routed.resolved.provider_model,
        provider_model_ref=routed.resolved.provider_model_ref,
        gateway_model=routed.request.model,
        thinking_enabled=routed.resolved.thinking_enabled,
    )

    request_id = f"req_{uuid.uuid4().hex[:12]}"
    with logger.contextualize(request_id=request_id):
        trace_event(
            stage="ingress",
            event="api.request.received",
            source="api",
            message_count=len(routed.request.messages),
            snapshot=api_messages_request_snapshot(routed.request),
        )

        if settings.log_raw_api_payloads:
            logger.debug(
                "FULL_PAYLOAD [{}]: {}", request_id, routed.request.model_dump()
            )

        input_tokens = token_counter(
            routed.request.messages,
            routed.request.system,
            routed.request.tools,
        )

        streamed = traced_async_stream(
            provider.stream_response(
                routed.request,
                input_tokens=input_tokens,
                request_id=request_id,
                thinking_enabled=routed.resolved.thinking_enabled,
            ),
            stage="egress",
            source="api",
            complete_event="api.response.stream_completed",
            interrupted_event="api.response.stream_interrupted",
            chunk_event=None,
            extra={
                "request_id": request_id,
                "provider_id": routed.resolved.provider_id,
                "gateway_model": routed.request.model,
            },
        )
        return anthropic_sse_streaming_response(streamed)


def run_create_message_pipeline(
    request_data: MessagesRequest,
    *,
    settings: Settings,
    model_router: ModelRouter,
    provider_getter: ProviderGetter,
    token_counter: TokenCounter = get_token_count,
) -> object:
    """Resolve model, apply guards, optional web-tool and optimization paths, then upstream stream."""
    require_messages_non_empty(request_data.messages)
    routed = model_router.resolve_messages_request(request_data)
    _enforce_openai_chat_server_tools_guard(routed, settings)
    web = _try_web_server_tool_branch(
        routed, settings=settings, token_counter=token_counter
    )
    if web is not None:
        return web
    optimized = _try_optimization_branch(routed, settings)
    if optimized is not None:
        return optimized
    return _stream_provider_branch(
        routed,
        settings=settings,
        provider_getter=provider_getter,
        token_counter=token_counter,
    )
